"""Cliente HTTP del origen A con caché en disco y pausas."""
from __future__ import annotations

import gzip
import hashlib
import json
import os
import re
import time
from pathlib import Path

import requests

from datosdep.models import Acta, Competicion, FilaClasificacion, JugadorTemporada
from datosdep.scraper import acta_api, acta_pdf, parsers
from datosdep.scraper import api as modelos_api
from datosdep.scraper.enlaces import resolver
from datosdep.scraper.texto import limpiar

BASE = os.environ.get("ORIGEN_A_URL", "").rstrip("/")  # secreto: no se escribe en el código
PAUSA_S = 0.25
PAUSA_LENTA_S = 1.5  # peticiones de una en una por partido (previo y acta): muchas seguidas provocan un 429
TTL_PAGINAS_S = 120  # las páginas que cambian se reutilizan 2 minutos
RAIZ_DATOS = Path(__file__).resolve().parents[2] / "data"
ESPERA_CAMBIO_S = 6 * 3600  # si la web redirige a otra versión, no se vuelve a probar hasta pasado un buen rato
ESPERA_BLOQUEO_S = 3600  # tras un 403/429 no volvemos a pedir durante 1 hora (cada sondeo puede alargar el castigo)


def temporada_actual_id() -> int:
    """Id de la temporada en curso ("2026/27" -> 2627), de config/competiciones.yaml."""
    from datosdep.rutas import CONFIG, leer_yaml

    a, b = str((leer_yaml(CONFIG / "competiciones.yaml") or {}).get("temporada", "0000/00")).split("/")
    return int(a[-2:] + b[-2:])


def url_acta_pdf() -> str:
    """Dirección del acta en PDF: se lee del secreto ORIGEN_A_ACTA_URL para no publicarla en el repositorio."""
    return os.environ.get("ORIGEN_A_ACTA_URL", "").strip()


REINTENTO_ILEGIBLE_S = 6 * 3600  # un acta que no se pudo leer se vuelve a pedir a las 6 h, no en cada pasada
MAX_INTENTOS_EXTRA = 3  # veces que se intenta completar un acta con sus cambios antes de dejarla sin minutos


class AccesoRestringido(RuntimeError):
    """el origen A rechaza la petición (403 o 429): no se reintenta ni se esquiva."""


class FuenteCambiada(AccesoRestringido):
    """La web de origen ya no sirve las páginas de siempre (redirige a otra versión): se trata como acceso cerrado."""


class OrigenA:
    def __init__(self, cache_dir: Path | str = ".cache/origen_a2", usar_cache: bool = True):
        self.cache_dir = Path(cache_dir)
        self.usar_cache = usar_cache
        self.sesion = requests.Session()
        self.sesion.headers["User-Agent"] = "rugby-es-datos/0.1"
        self._ultima = 0.0
        self._memoria: dict[str, tuple[float, bytes]] = {}
        self._bloqueos: dict[str, float] = {}  # "json" / "todo" -> instante (monotonic) hasta el que no se pide
        self.actas_bloqueadas = False
        self.ultimo_codigo: int | None = None  # último 403/429 recibido, para el aviso al dueño
        self.ultimo_motivo = ""
        self.extras_fallidos: dict[int, str] = {}  # id de partido -> por qué no se pudieron leer sus cambios (minutos)
        self._ilegible_hasta: dict[int, float] = {}
        self.actas_ilegibles: dict[int, str] = {}  # id de partido -> por qué no se pudo leer su acta (esta pasada)
        self.lento = False  # ritmo de 1,5 s entre peticiones (rellenar histórico de golpe)
        self._token_valor: str | None = None  # clave temporal (12 h) que trae la página nueva
        self._token_caduca = 0.0
        self._equipos: dict[int, dict] = {}  # id de grupo -> {id de equipo: (nombre, escudo)}

    @property
    def detalle_bloqueo(self) -> str:
        """Texto para el dueño: código recibido y qué respondió el origen A."""
        return f"{self.ultimo_codigo or 'sin confirmar en esta ejecución'}" + (
            f", el origen A dice: {self.ultimo_motivo}" if self.ultimo_motivo else "")

    def _zona(self, path: str) -> str:
        if path == url_acta_pdf():
            return "pdf"
        if path.startswith("api/"):
            return "api"
        return "json" if path.startswith("json/") else "web"  # ("todo" queda para el 429, que vale para todo el sitio)

    def bloqueado_ahora(self) -> bool:
        return time.monotonic() < max(self._bloqueos.values(), default=0)

    def _comprobar_bloqueo(self, path: str) -> None:
        ahora = time.monotonic()
        if ahora < self._bloqueos.get("todo", 0) or ahora < self._bloqueos.get(self._zona(path), 0):
            raise AccesoRestringido(f"{path}: el origen A ha rechazado las peticiones; no se insiste hasta pasados unos minutos")

    def _cambiada(self, path: str, r: requests.Response) -> None:
        """La web redirige a una versión nueva: se avisa, no se guarda nada y se espera un buen rato."""
        self.ultimo_codigo = r.status_code
        self.ultimo_motivo = "la web de origen ha cambiado (redirige a una versión nueva)"
        self._bloqueos[self._zona(path)] = time.monotonic() + ESPERA_CAMBIO_S
        raise FuenteCambiada(f"{path}: HTTP {r.status_code} (redirige a otra versión de la web)")

    def _bloquear(self, path: str, r: requests.Response) -> None:
        self.ultimo_codigo = r.status_code
        self.ultimo_motivo = " ".join(r.text.split())[:160]  # lo que dice el origen A en su error (no lleva datos privados)
        espera = ESPERA_BLOQUEO_S
        try:
            espera = min(max(int(r.headers.get("Retry-After", "")), 60), 14400)
        except ValueError:
            pass
        # 429 vale para todo el sitio; un 403 solo para esa zona (p. ej. la API JSON de las actas)
        zona = "todo" if r.status_code == 429 else self._zona(path)
        self._bloqueos[zona] = time.monotonic() + espera
        raise AccesoRestringido(f"{path}: HTTP {r.status_code}")

    def _esperar(self, lenta: bool) -> None:
        espera = (PAUSA_LENTA_S if lenta else PAUSA_S) - (time.monotonic() - self._ultima)
        if espera > 0:
            time.sleep(espera)

    def _get(self, path: str, params: dict, cachear: bool, guardar: bool = True, redirecciones: bool = True) -> bytes:
        url = path if path.startswith("http") else f"{BASE}/{path}"
        clave = hashlib.sha1(f"{url}?{sorted(params.items())}".encode()).hexdigest()
        fichero = self.cache_dir / f"{clave}.html.gz"
        if cachear and self.usar_cache and (viejo := self._leer_disco(clave)) is not None:
            return viejo
        if not cachear and clave in self._memoria and time.monotonic() - self._memoria[clave][0] < TTL_PAGINAS_S:
            return self._memoria[clave][1]
        try:
            self._comprobar_bloqueo(path)
        except AccesoRestringido:
            if self.usar_cache and (viejo := self._leer_disco(clave)) is not None:
                return viejo  # bloqueados: mejor el último dato guardado que nada
            raise
        self._esperar(self.lento or path.startswith("previo") or path == url_acta_pdf())
        for intento in range(3):
            try:
                # Las páginas del sitio no deben redirigir: si lo hacen, la web ha cambiado y lo que llegaría al
                # seguirla (una aplicación de JavaScript) no es la página pedida ni se puede leer.
                es_pagina = not path.startswith("http")
                r = self.sesion.get(url, params=params, timeout=30, allow_redirects=redirecciones and not es_pagina)
                if r.status_code in (403, 429):
                    self._bloquear(path, r)  # sin reintentos: insistir solo empeora el bloqueo
                if es_pagina and 300 <= r.status_code < 400:
                    self._cambiada(path, r)
                r.raise_for_status()
                break
            except AccesoRestringido:
                if self.usar_cache and (viejo := self._leer_disco(clave)) is not None:
                    return viejo
                raise
            except requests.RequestException:
                if intento == 2:
                    if self.usar_cache and (viejo := self._leer_disco(clave)) is not None:
                        return viejo  # red caída o error del servidor: último dato guardado
                    raise
                time.sleep(5 * (intento + 1))
        self._ultima = time.monotonic()
        if guardar and self.usar_cache and (cachear or r.content):
            self.cache_dir.mkdir(parents=True, exist_ok=True)
            fichero.write_bytes(gzip.compress(r.content, 9))  # sin pérdida; el HTML comprime ~5-10x
        if not cachear:
            self._memoria[clave] = (time.monotonic(), r.content)
        return r.content

    def _leer_disco(self, clave: str) -> bytes | None:
        gz = self.cache_dir / f"{clave}.html.gz"
        if gz.exists():
            return gzip.decompress(gz.read_bytes())
        viejo = self.cache_dir / f"{clave}.html"  # caché anterior sin comprimir
        return viejo.read_bytes() if viejo.exists() else None

    @staticmethod
    def _params(id_grupo: int) -> dict:
        return {
            "seleccion": 0,
            "id": id_grupo,
            "id_ambito": 0,
            "id_territorial": 9999,
            "id_superficie": 1,
        }

    # ---- API de la web nueva (POST con la clave temporal que da la propia página; método indicado por el origen A) ----

    def _token(self, forzar: bool = False) -> str:
        """Clave temporal de la página: se vuelve a pedir solo cuando está a punto de caducar (dura 12 h)."""
        if not forzar and self._token_valor and self._token_caduca - time.time() > 1800:
            return self._token_valor
        self._comprobar_bloqueo("api/pagina")
        self._esperar(False)
        r = self.sesion.get(f"{BASE}/maqueta/", timeout=30, allow_redirects=False)
        self._ultima = time.monotonic()
        if r.status_code in (403, 429):
            self._bloquear("api/pagina", r)
        if 300 <= r.status_code < 400:
            self._cambiada("api/pagina", r)
        r.raise_for_status()
        m = re.search(r"""<meta\s+name=["']client-token["']\s+content=["']([^"']+)""", r.text)
        if not m:
            self.ultimo_motivo = "la página nueva no trae la clave de acceso"
            raise FuenteCambiada("api/pagina: sin clave de acceso en la página")
        try:
            caduca = float(m.group(1).split(".")[0])  # el primer número de la clave es su caducidad (segundos)
        except ValueError:
            caduca = time.time() + 6 * 3600
        self._token_valor, self._token_caduca = m.group(1), caduca
        return self._token_valor

    @staticmethod
    def _clave_api(tipo: str, params: dict) -> str:
        return hashlib.sha1(f"api|{tipo}|{sorted(params.items())}".encode()).hexdigest()

    def _pedir_api(self, tipo: str, params: dict, lenta: bool) -> bytes:
        ruta = f"api/{tipo}"
        for intento in range(2):  # la segunda vez, con clave nueva si la anterior había caducado
            self._esperar(lenta)
            r = self.sesion.post(
                f"{BASE}/maqueta/json/beta.php", data={"tipo": tipo, **params}, timeout=30, allow_redirects=False,
                headers={"X-Client-Token": self._token(forzar=intento == 1), "Referer": f"{BASE}/maqueta/"})
            self._ultima = time.monotonic()
            if r.status_code == 403 and intento == 0 and "CLIENT_TOKEN_EXPIRED" in r.text:
                continue
            break
        if r.status_code in (403, 429):
            self._bloquear(ruta, r)  # sin reintentos: insistir solo empeora el bloqueo
        if 300 <= r.status_code < 400:
            self._cambiada(ruta, r)
        r.raise_for_status()
        json.loads(r.content)  # si no es JSON válido, ValueError: no se guarda ni se da por bueno
        return r.content

    def _api(self, tipo: str, cachear: bool = False, **params):
        """Consulta `tipo` a la API. cachear=True: lo ya pedido se lee del disco y no se vuelve a pedir."""
        if not BASE:
            self.ultimo_motivo = "falta configurar ORIGEN_A_URL"
            raise AccesoRestringido("ORIGEN_A_URL sin configurar")
        clave = self._clave_api(tipo, params)
        if cachear and self.usar_cache and (viejo := self._leer_disco(clave)) is not None:
            return json.loads(viejo)
        if not cachear and clave in self._memoria and time.monotonic() - self._memoria[clave][0] < TTL_PAGINAS_S:
            return json.loads(self._memoria[clave][1])
        try:
            self._comprobar_bloqueo(f"api/{tipo}")
            contenido = self._pedir_api(tipo, params, self.lento or tipo in ("previo", "acta"))
        except (AccesoRestringido, requests.RequestException, ValueError):
            if self.usar_cache and (viejo := self._leer_disco(clave)) is not None:
                return json.loads(viejo)  # bloqueados o sin red: el último dato guardado
            raise
        if self.usar_cache:
            self.cache_dir.mkdir(parents=True, exist_ok=True)
            (self.cache_dir / f"{clave}.html.gz").write_bytes(gzip.compress(contenido, 9))
        if not cachear:
            self._memoria[clave] = (time.monotonic(), contenido)
        return json.loads(contenido)

    def torneo(self, id_grupo: int, cachear: bool = False) -> dict:
        """Respuesta cruda de `torneo` (todos los partidos del grupo). cachear=True para temporadas pasadas."""
        t = self._api("torneo", cachear=cachear, id=id_grupo)
        self._equipos[id_grupo] = modelos_api.equipos_de_torneo(t)
        return t

    _torneo = torneo

    # Lo que cambia durante la temporada no se cachea en disco (solo 2 minutos en memoria).
    def competicion(self, id_grupo: int) -> Competicion:
        """Partidos del grupo. La tabla de jugadores de temporada no se publica: el bot la calcula con las actas."""
        return Competicion(modelos_api.partidos_de_torneo(self._torneo(id_grupo)), [])

    def clasificacion(self, id_grupo: int) -> list[FilaClasificacion]:
        return self.clasificacion_jornada(id_grupo, modelos_api.ultima_jornada_jugada(self._torneo(id_grupo)))

    def clasificacion_jornada(self, id_grupo: int, jornada: int, cachear: bool = False) -> list[FilaClasificacion]:
        """Clasificación tras esa jornada (las pasadas no cambian: cachear=True)."""
        if id_grupo not in self._equipos:
            self._torneo(id_grupo)
        c = self._api("clasificacion", cachear=cachear, se=0, id=id_grupo, j=jornada)
        return modelos_api.filas_clasificacion(c, self._equipos[id_grupo])

    def arbitro(self, id_partido: int, cachear: bool = True) -> str | None:
        """Árbitro del partido (del previo). cachear=True para partidos ya jugados: no cambia."""
        return modelos_api.arbitro_de_previo(self._api("previo", cachear=cachear, id=id_partido))

    def _selectores(self, id_temp: int, id_comp: int | None = None, id_terr: int = 9999) -> dict:
        """Competiciones de una temporada y, si se da `id_comp`, los grupos (con su fase) de esa competición.
        Lo pasado no cambia (cachear); la temporada en curso sí (puede publicarse una competición nueva)."""
        return self._api("selectores", cachear=id_temp < temporada_actual_id(), id="", t=id_terr, am=0, s=1, se=0,
                         temp=id_temp, cat="", comp=id_comp or "")

    def competiciones_de(self, id_temp: int, id_terr: int = 9999) -> list[tuple[int, str]]:
        return [(int(c["id"]), " ".join(str(c["nombre"]).split()))
                for c in self._selectores(id_temp, None, id_terr).get("competiciones") or []]

    def torneos_de(self, id_temp: int, id_comp: int, id_terr: int = 9999) -> list[dict]:
        """Grupos de una competición: [{id, nombre (del grupo), fase}]."""
        return [{"id": int(t["id"]), "nombre": " ".join(str(t.get("nombre_grupo") or t.get("nombre") or "").split()),
                 "fase": " ".join(str(t.get("nombre_fase") or "").split())}
                for t in self._selectores(id_temp, id_comp, id_terr).get("torneos") or []]

    def descubrir(self, id_temp: int) -> list[dict]:
        """Federaciones, competiciones y grupos publicados en el origen A para una temporada."""
        out = []
        for terr in self._selectores(id_temp).get("territoriales") or []:
            for id_comp, comp in self.competiciones_de(id_temp, int(terr["id"])):
                for g in self.torneos_de(id_temp, id_comp, int(terr["id"])):
                    out.append({"territorial": terr["nombre"], "competicion": comp, "fase": g["fase"],
                                "grupo": g["nombre"], "id_grupo": g["id"]})
        return out

    def candidatos(self, id_comp: int, cachear: bool = False) -> dict:
        """Jugadores que figuran en las actas de una competición: {jugadores: [{id, n, eq, pj}], equipos: {id: nombre}}."""
        return self._api("comparar_candidatos", cachear=cachear, comp=id_comp, s=1)

    def goleadores(self, id_grupo: int, id_comp: int, cachear: bool = False) -> list[dict]:
        """Máximos anotadores de la competición: [{n, eq, g (tantos), pj}]."""
        return self._api("goleadores", cachear=cachear, id=id_grupo, comp=id_comp)

    def jugadores_con_id(self, id_grupo: int) -> list[JugadorTemporada]:
        """Jugadores de la competición del grupo con su id (estable entre temporadas). Sin puntos ni ensayos:
        esos se calculan con las actas."""
        t = self.torneo(id_grupo)
        id_comp = next((int(p["comp"]) for p in t.get("partidos", []) if p.get("comp")), None)
        if not id_comp:
            return []
        c = self.candidatos(id_comp)
        equipos = {int(k): " ".join(str(v).split()) for k, v in (c.get("equipos") or {}).items()}
        return [JugadorTemporada(int(j["id"]), " ".join(str(j["n"]).split()), equipos.get(int(j.get("eq") or 0), ""),
                                 int(j.get("pj") or 0), 0, 0, 0, 0) for j in c.get("jugadores") or []]

    def imagen(self, url: str) -> bytes:
        return self._get(resolver(url), {}, cachear=True)

    def en_cache(self, path: str, params: dict) -> bool:
        clave = hashlib.sha1(f"{BASE}/{path}?{sorted(params.items())}".encode()).hexdigest()
        return self._leer_disco(clave) is not None

    def _manual(self, id_partido: int) -> Path:
        return RAIZ_DATOS / "actas_manuales" / f"{id_partido}.gz"  # en data/: se sube al repo y el bot lo ve

    def guardar_acta_manual(self, id_partido: int, raw: bytes) -> None:
        """Deja un acta guardada a mano (JSON o HTML) para que el bot la use; no hace peticiones."""
        ruta = self._manual(id_partido)
        ruta.parent.mkdir(parents=True, exist_ok=True)
        ruta.write_bytes(gzip.compress(raw, 9))

    def _guardada(self, id_partido: int) -> Path:
        return RAIZ_DATOS / "actas_pdf" / f"{id_partido}.gz"  # acta ya convertida desde el PDF: se pide una sola vez

    def borrar_acta_cache(self, id_partido: int) -> None:
        params = {"recurso": "acta", "id_partido": id_partido}
        clave = hashlib.sha1(f"{BASE}/json/origen_a_proxy.php?{sorted(params.items())}".encode()).hexdigest()
        for ext in ("html", "html.gz"):
            (self.cache_dir / f"{clave}.{ext}").unlink(missing_ok=True)
        self._manual(id_partido).unlink(missing_ok=True)
        self._guardada(id_partido).unlink(missing_ok=True)

    def acta_en_cache(self, id_partido: int) -> bool:
        return self._manual(id_partido).exists() or self._guardada(id_partido).exists() or self.en_cache(
            "json/origen_a_proxy.php", {"recurso": "acta", "id_partido": id_partido})

    def _leer_guardada(self, id_partido: int) -> dict | None:
        """El acta guardada como diccionario, o None si no existe o está corrupta (en ese caso se borra y se vuelve a pedir)."""
        ruta = self._guardada(id_partido)
        if not ruta.exists():
            return None
        try:
            d = json.loads(gzip.decompress(ruta.read_bytes()))
            if not isinstance(d, dict) or not isinstance(d.get("data"), dict):
                raise ValueError("formato desconocido")
            return d
        except (OSError, EOFError, ValueError):
            ruta.unlink(missing_ok=True)
            return None

    def _escribir_guardada(self, id_partido: int, contenido: bytes) -> None:
        """Escritura atómica: si el proceso se corta a medias, no queda un fichero roto."""
        ruta = self._guardada(id_partido)
        ruta.parent.mkdir(parents=True, exist_ok=True)
        tmp = ruta.with_suffix(".tmp")
        tmp.write_bytes(gzip.compress(contenido, 9))
        os.replace(tmp, ruta)

    def extra_acta(self, id_partido: int) -> dict | None:
        """Cambios y tarjetas del acta (para los minutos), si se guardaron."""
        d = self._leer_guardada(id_partido)
        return (d or {}).get("data", {}).get("extra")

    def tiene_extra(self, id_partido: int) -> bool:
        return self.extra_acta(id_partido) is not None

    def puede_extra(self, id_partido: int) -> bool:
        """False si al acta le faltan los cambios pero ya se ha intentado completarla demasiadas veces."""
        d = self._leer_guardada(id_partido)
        return d is None or d.get("fuente") != "api" or int(d.get("extra_intentos") or 0) < MAX_INTENTOS_EXTRA

    def _dorsales(self, d: dict) -> list[set[int]]:
        p = d["data"]["partido"]
        ids = [int(p["local"]["id_equipo"]), int(p["visitante"]["id_equipo"])]
        out: list[set[int]] = [set(), set()]
        for j in d["data"].get("alineaciones") or []:
            if int(j.get("id_equipo", -1)) in ids and int(j.get("dorsal") or 0) > 0:
                out[ids.index(int(j["id_equipo"]))].add(int(j["dorsal"]))
        return out

    def _extra_pdf(self, id_partido: int, d: dict) -> dict | None:
        """Cambios y tarjetas desde el PDF, comprobados contra el acta. None (sin romper nada) si no se puede."""
        url = url_acta_pdf()
        if not url:
            return None
        try:
            p = d["data"]["partido"]
            pdf = self._get(url, {"id_partido": id_partido}, cachear=False, guardar=False, redirecciones=False)
            return acta_pdf.extra_de_pdf(
                pdf, [limpiar(p["local"]["nombre"]), limpiar(p["visitante"]["nombre"])],
                (int(p["local"]["resultado"]), int(p["visitante"]["resultado"])), self._dorsales(d))
        except (ValueError, KeyError, TypeError, AccesoRestringido, requests.RequestException) as e:
            self.extras_fallidos[id_partido] = str(e)[:160]
            return None

    def refrescar_extra(self, id_partido: int) -> bool:
        """Intenta completar con los cambios un acta guardada sin ellos (como mucho MAX_INTENTOS_EXTRA veces)."""
        d = self._leer_guardada(id_partido)
        if d is not None and d.get("fuente") == "api":
            if int(d.get("extra_intentos") or 0) >= MAX_INTENTOS_EXTRA:
                return False
            extra = self._extra_pdf(id_partido, d)
            d["extra_intentos"] = int(d.get("extra_intentos") or 0) + 1
            if extra:
                d["data"]["extra"] = extra
            self._escribir_guardada(id_partido, json.dumps(d, ensure_ascii=False).encode("utf-8"))
            return extra is not None
        try:
            self._acta_desde_pdf(id_partido)  # acta antigua guardada solo desde el PDF
            return True
        except (ValueError, AccesoRestringido, requests.RequestException):
            return False

    def _acta_desde_api(self, id_partido: int) -> bytes:
        """Acta del JSON de la API (validada) más los cambios del PDF si se pueden leer. Se guarda una sola vez."""
        resp = self._api("acta", id=id_partido)
        _, descuadre = acta_api.validar(resp, id_partido)  # ValueError si no es coherente: no se guarda nada
        d = acta_api.limpia(resp, descuadre)
        d["guardado"] = int(time.time())
        extra = self._extra_pdf(id_partido, d)
        if extra:
            d["data"]["extra"] = extra
        d["extra_intentos"] = 1
        raw = json.dumps(d, ensure_ascii=False).encode("utf-8")
        self._escribir_guardada(id_partido, raw)
        return raw

    def _revisar_descuadre(self, id_partido: int, guardada: dict) -> dict:
        """Un acta cuyas jugadas no suman el marcador del árbitro se vuelve a mirar una vez al día, por si la
        federación la corrige. Si no se puede (o sigue igual), se queda como estaba."""
        if not guardada.get("descuadre") or time.time() - float(guardada.get("guardado") or 0) < 24 * 3600:
            return guardada
        try:
            return json.loads(self._acta_desde_api(id_partido))
        except (AccesoRestringido, ValueError, KeyError, TypeError, requests.RequestException):
            guardada["guardado"] = int(time.time())
            self._escribir_guardada(id_partido, json.dumps(guardada, ensure_ascii=False).encode("utf-8"))
            return guardada

    def _acta_nueva(self, id_partido: int) -> bytes:
        """API primero; si falla (bloqueo, red o datos que no cuadran), el PDF entero; si tampoco, ValueError."""
        motivo = ""
        try:
            return self._acta_desde_api(id_partido)
        except AccesoRestringido as e:
            motivo = f"API bloqueada ({e})"
        except (ValueError, KeyError, TypeError, requests.RequestException) as e:
            motivo = str(e)[:100]
        try:
            return self._acta_desde_pdf(id_partido)
        except ValueError as e:
            raise ValueError(f"{motivo} | PDF: {e}") from e
        except requests.RequestException as e:
            raise ValueError(f"{motivo} | PDF: {e!r}"[:200]) from e

    def _acta_desde_pdf(self, id_partido: int) -> bytes:
        """Pide el PDF del acta (una sola vez), lo convierte y deja el resultado en data/actas_pdf."""
        url = url_acta_pdf()
        if not url:
            self.ultimo_motivo = "falta configurar ORIGEN_A_ACTA_URL"
            raise AccesoRestringido("ORIGEN_A_ACTA_URL sin configurar")
        pdf = self._get(url, {"id_partido": id_partido}, cachear=False, guardar=False, redirecciones=False)
        try:
            raw = acta_pdf.pdf_a_json(pdf)  # ValueError si el PDF no cuadra: no se guarda nada
        except ValueError as e:
            raise ValueError(f"acta {id_partido}: {e}") from e
        self._escribir_guardada(id_partido, raw)
        return raw

    def previo_en_cache(self, id_partido: int) -> bool:
        return self._leer_disco(self._clave_api("previo", {"id": id_partido})) is not None

    def _conocido(self, nombre: str) -> str:
        """Si un equipo conocido de la competición tiene las mismas palabras en otro orden, ese nombre."""
        palabras = sorted(nombre.split())
        for equipos in self._equipos.values():
            for conocido, _ in equipos.values():
                if conocido != nombre and sorted(conocido.split()) == palabras:
                    return conocido
        return nombre

    def _unificar_nombres(self, acta: Acta) -> Acta:
        """El acta y la tabla escriben a veces el nombre de un equipo con las palabras en otro orden
        ("…CAJA RURAL BURGOS…" / "…BURGOS CAJA RURAL…"): se usa siempre el de la competición."""
        cambios = {n: self._conocido(n) for n in (acta.local, acta.visitante) if n}
        cambios = {a: b for a, b in cambios.items() if a != b}
        if not cambios:
            return acta
        acta.local, acta.visitante = cambios.get(acta.local, acta.local), cambios.get(acta.visitante, acta.visitante)
        for e in acta.eventos:
            e.equipo = cambios.get(e.equipo, e.equipo)
        return acta

    def acta(self, id_partido: int) -> Acta:
        # Orden: acta guardada a mano > acta ya convertida > acta que bajó antes el proxy JSON (caché) >
        # PDF oficial (dirección en el secreto ORIGEN_A_ACTA_URL). Un acta de partido
        # finalizado ya no cambia: una vez convertida no se vuelve a pedir.
        params = {"recurso": "acta", "id_partido": id_partido}
        clave_json = hashlib.sha1(f"{BASE}/json/origen_a_proxy.php?{sorted(params.items())}".encode()).hexdigest()
        try:
            if self._manual(id_partido).exists():
                raw = gzip.decompress(self._manual(id_partido).read_bytes())
            elif (guardada := self._leer_guardada(id_partido)) is not None:
                guardada = self._revisar_descuadre(id_partido, guardada)
                raw = json.dumps(guardada, ensure_ascii=False).encode("utf-8")
            elif self.usar_cache and (viejo := self._leer_disco(clave_json)) is not None:
                raw = viejo
            elif time.time() < self._ilegible_hasta.get(id_partido, 0):
                return Acta(id_partido, "", "", [], [], [])  # falló hace poco: no se insiste hasta dentro de unas horas
            else:
                try:
                    raw = self._acta_nueva(id_partido)
                except (ValueError, requests.RequestException) as e:
                    self._ilegible_hasta[id_partido] = time.time() + REINTENTO_ILEGIBLE_S
                    # PDF incompleto o que no cuadra, o un corte de red: ese partido queda como "acta pendiente"
                    # (el marcador vale, sus estadísticas no) y se reintenta en la siguiente pasada. No se guarda
                    # nada y no se rompe el resto de la competición.
                    self.actas_ilegibles[id_partido] = str(e)[:160]
                    return Acta(id_partido, "", "", [], [], [])
        except AccesoRestringido:
            # el origen A no deja leer las actas: acta vacía (el partido cuenta como "acta pendiente") y el
            # bot sigue con resultados y clasificaciones; flujo.py avisa al dueño una vez al día.
            self.actas_bloqueadas = True
            return Acta(id_partido, "", "", [], [], [])
        try:
            try:
                acta = parsers.acta_json(raw, id_partido)
            except ValueError:
                if raw.lstrip()[:1] == b"{":
                    raise
                acta = parsers.acta(raw, id_partido)  # página guardada a mano desde el navegador
                if not acta.eventos:
                    raise
            self.actas_bloqueadas = False
            return self._unificar_nombres(acta)
        except (ValueError, KeyError):
            # Respuesta sin datos: no la dejamos cacheada para reintentarla luego.
            clave = hashlib.sha1(f"{BASE}/json/origen_a_proxy.php?{sorted(params.items())}".encode()).hexdigest()
            for ext in ("html", "html.gz"):
                (self.cache_dir / f"{clave}.{ext}").unlink(missing_ok=True)
            raise


_COMPARTIDO: OrigenA | None = None


def compartido() -> OrigenA:
    """Cliente único del proceso, para aprovechar la caché en memoria entre llamadas."""
    global _COMPARTIDO
    if _COMPARTIDO is None:
        _COMPARTIDO = OrigenA()
    return _COMPARTIDO


_ORIGEN_B: dict[str, OrigenA] = {}


def cliente_para(cfg_comp: dict) -> OrigenA:
    """Cliente de la plataforma de esa competición (el origen A por defecto, o OrigenB)."""
    if cfg_comp.get("fuente") == "origen_b":
        from datosdep.scraper.origen_b import OrigenB

        base = cfg_comp["base"]
        if base not in _ORIGEN_B:
            _ORIGEN_B[base] = OrigenB(base)
        return _ORIGEN_B[base]
    return compartido()
