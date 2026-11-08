"""Cliente HTTP del origen A con caché en disco y pausas."""
from __future__ import annotations

import gzip
import hashlib
import os
import time
from pathlib import Path

import requests

from datosdep.models import Acta, Competicion, FilaClasificacion
from datosdep.scraper import acta_pdf, parsers
from datosdep.scraper.enlaces import resolver

BASE = os.environ.get("ORIGEN_A_URL", "").rstrip("/")  # secreto: no se escribe en el código
PAUSA_S = 0.25
PAUSA_LENTA_S = 1.5  # peticiones de una en una por partido (previo y acta): muchas seguidas provocan un 429
TTL_PAGINAS_S = 120  # las páginas que cambian se reutilizan 2 minutos
RAIZ_DATOS = Path(__file__).resolve().parents[2] / "data"
ESPERA_BLOQUEO_S = 3600  # tras un 403/429 no volvemos a pedir durante 1 hora (cada sondeo puede alargar el castigo)


def url_acta_pdf() -> str:
    """Dirección del acta en PDF: se lee del secreto ORIGEN_A_ACTA_URL para no publicarla en el repositorio."""
    return os.environ.get("ORIGEN_A_ACTA_URL", "").strip()


class AccesoRestringido(RuntimeError):
    """el origen A rechaza la petición (403 o 429): no se reintenta ni se esquiva."""


class OrigenA:
    def __init__(self, cache_dir: Path | str = ".cache/origen_a", usar_cache: bool = True):
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
        self.lento = False  # ritmo de 1,5 s entre peticiones (rellenar histórico de golpe)

    @property
    def detalle_bloqueo(self) -> str:
        """Texto para el dueño: código recibido y qué respondió el origen A."""
        return f"{self.ultimo_codigo or 'sin confirmar en esta ejecución'}" + (
            f", el origen A dice: {self.ultimo_motivo}" if self.ultimo_motivo else "")

    def _zona(self, path: str) -> str:
        if path == url_acta_pdf():
            return "pdf"
        return "json" if path.startswith("json/") else "todo"

    def bloqueado_ahora(self) -> bool:
        return time.monotonic() < max(self._bloqueos.values(), default=0)

    def _comprobar_bloqueo(self, path: str) -> None:
        ahora = time.monotonic()
        if ahora < self._bloqueos.get("todo", 0) or ahora < self._bloqueos.get(self._zona(path), 0):
            raise AccesoRestringido(f"{path}: el origen A ha rechazado las peticiones; no se insiste hasta pasados unos minutos")

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
        lenta = self.lento or path.startswith("previo") or path == url_acta_pdf()
        espera = (PAUSA_LENTA_S if lenta else PAUSA_S) - (time.monotonic() - self._ultima)
        if espera > 0:
            time.sleep(espera)
        for intento in range(3):
            try:
                r = self.sesion.get(url, params=params, timeout=30, allow_redirects=redirecciones)
                if r.status_code in (403, 429):
                    self._bloquear(path, r)  # sin reintentos: insistir solo empeora el bloqueo
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

    # Las páginas que cambian durante la temporada no se cachean.
    def competicion(self, id_grupo: int) -> Competicion:
        raw = self._get("mostrar_estadisticas.php", self._params(id_grupo), cachear=False)
        return parsers.estadisticas(raw)

    def clasificacion(self, id_grupo: int) -> list[FilaClasificacion]:
        raw = self._get("clasificacion.php", self._params(id_grupo), cachear=False)
        return parsers.clasificacion(raw)

    def _opciones(self, params: dict, select: str) -> list[tuple[int, str]]:
        import re

        raw = self._get("competicion.php", params, cachear=False).decode("utf-8", "replace")
        m = re.search(rf"<select id='{select}'.*?</select>", raw, re.S)
        if not m:
            return []
        return [(int(v), " ".join(n.split())) for v, n in re.findall(r"<option[^>]*value='(\d+)'[^>]*>([^<]*)", m.group(0))]

    def descubrir(self, id_temp: int) -> list[dict]:
        """regiones, competiciones y grupos publicados en el origen A para una temporada."""
        base = {"seleccion": 0, "id_ambito": 0, "id_temp": id_temp}
        out = []
        for id_terr, terr in self._opciones(base, "territorial"):
            p = {**base, "id_territorial": id_terr}
            for id_comp, comp in self._opciones(p, "competiciones"):
                pc = {**p, "id_competicion": id_comp}
                for id_fase, fase in self._opciones(pc, "fase") or [(0, "")]:
                    pf = {**pc, "id_fase": id_fase} if id_fase else pc
                    for id_grupo, grupo in self._opciones(pf, "grupo"):
                        out.append({"territorial": terr, "competicion": comp, "fase": fase,
                                    "grupo": grupo, "id_grupo": id_grupo})
        return out

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
        ruta = self._guardada(id_partido)
        ruta.parent.mkdir(parents=True, exist_ok=True)
        ruta.write_bytes(gzip.compress(raw, 9))
        return raw

    def previo_en_cache(self, id_partido: int) -> bool:
        return self.en_cache("previo.php", {"id_partido": id_partido})

    def acta(self, id_partido: int) -> Acta:
        # Orden: acta guardada a mano > acta ya convertida > acta que bajó antes el proxy JSON (caché) >
        # PDF oficial (dirección en el secreto ORIGEN_A_ACTA_URL). Un acta de partido
        # finalizado ya no cambia: una vez convertida no se vuelve a pedir.
        params = {"recurso": "acta", "id_partido": id_partido}
        clave_json = hashlib.sha1(f"{BASE}/json/origen_a_proxy.php?{sorted(params.items())}".encode()).hexdigest()
        try:
            if self._manual(id_partido).exists():
                raw = gzip.decompress(self._manual(id_partido).read_bytes())
            elif self._guardada(id_partido).exists():
                raw = gzip.decompress(self._guardada(id_partido).read_bytes())
            elif self.usar_cache and (viejo := self._leer_disco(clave_json)) is not None:
                raw = viejo
            else:
                raw = self._acta_desde_pdf(id_partido)
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
            return acta
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
