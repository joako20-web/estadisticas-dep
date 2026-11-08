"""Fichas bajo pedido de equipo y de jugador (búsqueda difusa por nombre).

- buscar_equipo(texto)  -> candidatos [{id, equipo, corto, liga, comp, grupo, ...}]
- ficha_equipo(candidato_o_id, formato) -> [Path] (una imagen)
- buscar_jugador(texto) -> candidatos [{id, nombre, equipo, liga, comp, grupo, ...}]
- ficha_jugador(candidato_o_id, formato) -> [Path]

Los ids son cortos ("e:1a2b3c4d", "j:1a2b3c4d") para caber en callback_data de
Telegram. El índice de equipos se cachea 12 h; el de jugadores se rehace a partir
de los resúmenes de temporada ya guardados (data/<temporada>/<comp>/<grupo>/
resumen_partidos.json), sin descargar ligas enteras en cada búsqueda.
"""
from __future__ import annotations

import difflib
import json
import re
import tempfile
import time
import unicodedata
import zlib
from collections import Counter
from dataclasses import asdict
from datetime import datetime
from pathlib import Path

from datosdep.core.estadisticas import POSICIONES
from datosdep.pipeline import (
    actualizar_resumen,
    DATA,
    cargar_config,
    jugadores_desde_resumen,
    ruta_jornada,
)
from datosdep.render import nombres
from datosdep.render.render import MESES, con_zonas, renderizar_slides
from datosdep.rutas import RAIZ
from datosdep.scraper.origen_a import cliente_para

CACHE = RAIZ / ".cache" / "origen_a"  # se conserva entre ejecuciones del bot (actions/cache)
INDICE_EQUIPOS = CACHE / "indice_equipos.json"
TTL_INDICE_S = 12 * 3600
ORDEN_CATEGORIA = {"nacional": 0, "regional": 1, "copa": 2}

# Resumen de partidos: [nombre, equipo, puntos, ensayos, conversiones, golpes, drops, amarillas, rojas, dorsal]
NOMBRE, EQUIPO, PUNTOS, ENSAYOS, CONV, GOLPES, DROPS, AMARILLAS, ROJAS, DORSAL = range(10)


# ---------- utilidades ----------

def norm(s: str) -> str:
    """minúsculas, sin tildes y solo letras/números separados por espacios."""
    s = unicodedata.normalize("NFKD", (s or "").lower())
    s = "".join(c for c in s if not unicodedata.combining(c))
    return " ".join(re.sub(r"[^a-z0-9]+", " ", s).split())


def _id(prefijo: str, *partes) -> str:
    return f"{prefijo}:{zlib.crc32('|'.join(map(str, partes)).encode()):08x}"


def _club(escudo: str) -> int | None:
    """Id de club de el origen A (estable entre temporadas aunque cambie el patrocinador)."""
    m = re.search(r"afiliacion_clubs/(\d+)/", escudo or "")
    return int(m.group(1)) if m else None


def _liga(cfg: dict, grupo: str) -> str:
    return cfg["nombre"] + ("" if grupo == "unico" else f" · Grupo {grupo}")


def _puntuar(consulta: str, textos: list[str], exactos: list[str]) -> int:
    """0-100: exacto en nombre corto/abreviatura > todas las palabras > parecido."""
    q = norm(consulta)
    if not q:
        return 0
    if q in (norm(x) for x in exactos if x):
        return 100
    palabras = set(norm(" ".join(textos)).split())
    toks = q.split()
    if all(any(p.startswith(t) for p in palabras) for t in toks):
        completas = sum(t in palabras for t in toks)
        return 70 + min(20, 10 * completas)
    mejor = max((difflib.SequenceMatcher(None, q, norm(x)).ratio() for x in textos if x), default=0)
    return int(mejor * 60) if mejor >= 0.75 else 0


def _mejores(candidatos: list[tuple[int, dict]], max_n: int = 8) -> list[dict]:
    """Solo el nivel de puntuación más alto (si hay uno exacto, no se listan los parecidos)."""
    candidatos = [c for c in candidatos if c[0] > 0]
    if not candidatos:
        return []
    top = max(p for p, _ in candidatos)
    umbral = top if top >= 100 else top - 10
    elegidos = [c for p, c in sorted(candidatos, key=lambda x: -x[0]) if p >= umbral]
    return elegidos[:max_n]


# ---------- equipos ----------

def _construir_indice_equipos() -> list[dict]:
    indice, vistos = [], set()
    comps = cargar_config()["competiciones"]
    orden = sorted(comps.items(), key=lambda kv: ORDEN_CATEGORIA.get(kv[1].get("categoria", "nacional"), 3))
    for comp, cfg in orden:
        cliente = cliente_para(cfg)
        for grupo, id_grupo in cfg["grupos"].items():
            try:
                clasificacion = cliente.clasificacion(id_grupo)
            except Exception:
                continue
            for f in clasificacion:
                if (f.equipo, cfg.get("categoria") == "copa") in vistos:
                    continue
                vistos.add((f.equipo, cfg.get("categoria") == "copa"))
                indice.append({
                    "id": _id("e", comp, grupo, f.equipo), "equipo": f.equipo,
                    "corto": nombres.equipo_corto(f.equipo), "abr": nombres.equipo_abr(f.equipo),
                    "liga": _liga(cfg, grupo), "comp": comp, "grupo": grupo,
                    "categoria": cfg.get("categoria", "nacional"), "region": cfg.get("region", ""),
                    "escudo": f.escudo, "club": _club(f.escudo),
                })
    return indice


def indice_equipos(forzar: bool = False) -> list[dict]:
    if not forzar and INDICE_EQUIPOS.exists() and time.time() - INDICE_EQUIPOS.stat().st_mtime < TTL_INDICE_S:
        return json.loads(INDICE_EQUIPOS.read_text(encoding="utf-8"))
    indice = _construir_indice_equipos()
    CACHE.mkdir(parents=True, exist_ok=True)
    INDICE_EQUIPOS.write_text(json.dumps(indice, ensure_ascii=False), encoding="utf-8")
    return indice


def buscar_equipo(texto: str, indice: list[dict] | None = None) -> list[dict]:
    """Candidatos para `texto` ("vrac", "cisneros", "la vila", "ordizia"...).

    Con una coincidencia exacta (nombre corto o abreviatura) solo vuelve esa;
    la Copa solo aparece si el equipo no juega una liga configurada.
    """
    indice = indice if indice is not None else indice_equipos()
    puntuados = []
    for c in indice:
        p = _puntuar(texto, [c["equipo"], c["corto"]], [c["corto"], c["abr"], c["equipo"]])
        puntuados.append((p - (5 if c["categoria"] == "copa" else 0), c))
    mejores = _mejores(puntuados)
    con_liga = {norm(c["equipo"]) for c in mejores if c["categoria"] != "copa"}
    return [c for c in mejores if c["categoria"] != "copa" or norm(c["equipo"]) not in con_liga]


def equipo_por_id(id_: str) -> dict | None:
    for c in indice_equipos():
        if c["id"] == id_:
            return c
    return None


def _resultado(p, equipo: str) -> str:
    propios, rivales = (p.puntos_local, p.puntos_visitante) if p.local == equipo else (p.puntos_visitante, p.puntos_local)
    return "G" if propios > rivales else "E" if propios == rivales else "P"


def datos_equipo(cand: dict) -> dict:
    """Todo lo que lleva la ficha de un equipo (sin renderizar)."""
    from datosdep.pipeline import resumen_temporada

    cfg = cargar_config()["competiciones"][cand["comp"]]
    cliente = cliente_para(cfg)
    id_grupo = cfg["grupos"][cand["grupo"]]
    clasificacion = cliente.clasificacion(id_grupo)
    competicion = cliente.competicion(id_grupo).filtrar(id_grupo, {f.equipo for f in clasificacion})
    equipo = cand["equipo"]
    filas, leyenda = con_zonas([asdict(f) for f in clasificacion], cand["comp"], cand["grupo"])
    fila = next((f for f in filas if f["equipo"] == equipo), None)
    zona = next((z["texto"] for z in leyenda if fila and z["color"] == fila.get("zona")), "")

    suyos = [p for p in competicion.partidos if equipo in (p.local, p.visitante)]
    jugados = sorted((p for p in suyos if p.jugado), key=lambda p: (p.fecha or datetime.min, p.jornada))
    pendientes = sorted((p for p in suyos if not p.jugado and p.fecha),
                        key=lambda p: p.fecha)
    ahora = datetime.now()
    proximo = next((p for p in pendientes if p.fecha >= ahora), pendientes[0] if pendientes else None)

    ultimos = []
    for p in reversed(jugados[-3:]):
        local = p.local == equipo
        ultimos.append({
            "jornada": p.jornada, "rival": p.visitante if local else p.local, "local": local,
            "pf": p.puntos_local if local else p.puntos_visitante,
            "pc": p.puntos_visitante if local else p.puntos_local,
            "res": _resultado(p, equipo),
        })
    prox = None
    if proximo:
        local = proximo.local == equipo
        f = proximo.fecha
        prox = {"rival": proximo.visitante if local else proximo.local, "local": local, "jornada": proximo.jornada,
                "cuando": f"{f.day} {MESES[f.month - 1]}" + (f" · {f:%H:%M}" if (f.hour, f.minute) != (0, 0) else ""), "campo": (proximo.campo or "").split("(")[0].strip()}

    try:
        resumen = resumen_temporada(cand["comp"], cand["grupo"], competicion, cliente)
    except Exception:
        resumen = {}
    del_equipo = [j for j in jugadores_desde_resumen(resumen) if j.equipo == equipo]
    anotadores = sorted(del_equipo, key=lambda j: (-j.puntos, -j.ensayos))[:3]
    ensayadores = sorted((j for j in del_equipo if j.ensayos), key=lambda j: (-j.ensayos, -j.puntos))[:3]

    return {
        "equipo": equipo, "liga": cand["liga"], "comp": cand["comp"], "grupo": cand["grupo"],
        "fila": fila, "n_equipos": len(filas), "zona": zona,
        "racha": [_resultado(p, equipo) for p in jugados[-5:]],
        "ultimos": ultimos, "proximo": prox,
        "anotadores": [{"nombre": j.nombre, "valor": j.puntos} for j in anotadores if j.puntos],
        "ensayadores": [{"nombre": j.nombre, "valor": j.ensayos} for j in ensayadores],
        "jornada": max((p.jornada for p in jugados), default=None),
        "escudos": {f.equipo: f.escudo for f in clasificacion if f.escudo},
    }


def _renderizar(comp: str, grupo: str, jornada, escudos: dict, slide: dict, formato: str,
                destino: Path | None) -> list[Path]:
    datos = {"competicion": comp, "grupo": grupo, "jornada": jornada,
             "temporada": cargar_config()["temporada"], "escudos": escudos}
    destino = destino or Path(tempfile.mkdtemp(prefix="ficha_"))
    return renderizar_slides(datos, slide if isinstance(slide, list) else [slide], destino, formato)


def ficha_equipo(cand: dict | str, formato: str = "post", destino: Path | None = None) -> list[Path]:
    cand = equipo_por_id(cand) if isinstance(cand, str) else cand
    if not cand:
        return []
    d = datos_equipo(cand)
    slide = {"tipo": "ficha_equipo", "clave": "ficha", **d}
    return _renderizar(d["comp"], d["grupo"], None, d["escudos"], slide, formato, destino)


# ---------- jugadores ----------

def _ficheros_resumen() -> list[tuple[str, str, Path]]:
    temporada = cargar_config()["temporada"].replace("/", "-")
    comps = cargar_config()["competiciones"]
    out = []
    for comp, cfg in comps.items():
        for grupo in cfg["grupos"]:
            ruta = DATA / temporada / comp / grupo / "resumen_partidos.json"
            if ruta.exists():
                out.append((comp, grupo, ruta))
    return out


def asegurar_resumenes(categorias: tuple[str, ...] = ("nacional",)) -> int:
    """Genera los resúmenes de temporada que falten (por defecto solo nacionales).

    Solo descarga actas que no estén ya en caché. Devuelve cuántos ha generado.
    """
    from datosdep.pipeline import resumen_temporada

    hechos = 0
    temporada = cargar_config()["temporada"].replace("/", "-")
    for comp, cfg in cargar_config()["competiciones"].items():
        if cfg.get("categoria", "nacional") not in categorias:
            continue
        cliente = cliente_para(cfg)
        for grupo, id_grupo in cfg["grupos"].items():
            if (DATA / temporada / comp / grupo / "resumen_partidos.json").exists():
                continue
            try:
                clasificacion = cliente.clasificacion(id_grupo)
                competicion = cliente.competicion(id_grupo).filtrar(id_grupo, {f.equipo for f in clasificacion})
                resumen_temporada(comp, grupo, competicion, cliente)
                hechos += 1
            except Exception:
                continue
    return hechos


def indice_jugadores() -> list[dict]:
    comps = cargar_config()["competiciones"]
    indice = []
    for comp, grupo, ruta in _ficheros_resumen():
        try:
            resumen = json.loads(ruta.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if resumen and max(len(js) for js in resumen.values()) < 26:  # formato antiguo: solo anotadores
            try:
                resumen = actualizar_resumen(comp, grupo)
            except Exception:
                pass
        cfg = comps[comp]
        for j in jugadores_desde_resumen(resumen, todos=True):
            indice.append({
                "id": _id("j", comp, grupo, j.nombre, j.equipo), "nombre": j.nombre, "equipo": j.equipo,
                "liga": _liga(cfg, grupo), "comp": comp, "grupo": grupo,
                "categoria": cfg.get("categoria", "nacional"), "puntos": j.puntos,
            })
    return indice


def buscar_jugador(texto: str, indice: list[dict] | None = None) -> list[dict]:
    """Candidatos por nombre o apellidos ("mansilla", "alba garcia", "taibo").

    Solo aparecen jugadores con algún punto o tarjeta esta temporada (los que
    registra el resumen de partidos). Si no hay ningún resumen, se generan los
    de las ligas nacionales una vez.
    """
    if indice is None:
        indice = indice_jugadores()
        if not indice and asegurar_resumenes():
            indice = indice_jugadores()
    puntuados = [(_puntuar(texto, [c["nombre"]], [c["nombre"]]), c) for c in indice]
    # A igualdad, primero quien más puntúa (el más probable)
    mejores = _mejores(puntuados, max_n=50)
    return sorted(mejores, key=lambda c: -c["puntos"])[:8]


def jugador_por_id(id_: str) -> dict | None:
    for c in indice_jugadores():
        if c["id"] == id_:
            return c
    return None


def _id_fuente(jugadores, nombre: str, equipo: str) -> int | None:
    """Id del jugador en la tabla de temporada (por nombre; si hay varios, el de su equipo)."""
    n = norm(nombre)
    candidatos = [j for j in jugadores if norm(j.nombre) == n]
    if len(candidatos) > 1:
        candidatos = [j for j in candidatos if j.equipo == equipo] or candidatos[:1]
    return candidatos[0].id if candidatos else None


def carrera_jugador(d: dict) -> tuple[list[dict], dict]:
    """Filas de temporadas anteriores + totales (con la temporada actual) para la imagen de carrera."""
    from datosdep import historico

    try:
        historico.completar(d["comp"])  # una vez y despacio; si la fuente rechaza, sigue con lo que haya
    except Exception:
        pass
    pasadas = historico.carrera(d.get("id_fuente"))
    if not pasadas:
        return [], {}
    try:  # nombre actual del mismo club (el de entonces lleva patrocinador: "RECOLETAS BURGOS 2031-CAJA RURAL")
        actuales = historico._actuales(d["comp"])
    except Exception:
        actuales = {}
    for f in pasadas:
        if f.get("club") in actuales:
            f["equipo"] = actuales[f["club"]]["equipo"]
    actual = {"temporada": cargar_config()["temporada"], "liga": d["liga"], "equipo": d["equipo"],
              "pj": d["partidos"], "puntos": d["puntos"], "ensayos": d["ensayos"],
              "tarjetas": d["amarillas"] + d["rojas"]}
    filas = [actual, *pasadas]
    total = {k: sum(f[k] for f in filas) for k in ("pj", "puntos", "ensayos", "tarjetas")}
    total["temporadas"] = len({f["temporada"] for f in filas})
    return filas, total


def _partidos_guardados(comp: str, grupo: str) -> dict[int, dict]:
    """Partidos de la temporada ya guardados en data/ (jornada, equipos y marcador), sin pedir nada."""
    carpeta = ruta_jornada(comp, grupo, 0).parent
    for f in sorted(carpeta.glob("j[0-9][0-9].json"), reverse=True):
        try:
            d = json.loads(f.read_text(encoding="utf-8"))
        except ValueError:
            continue
        ps = d.get("partidos_temporada") or d.get("partidos")
        if ps:
            return {p["id"]: p for p in ps}
    return {}


def _ranking_historico(comp: str, actuales: list, id_fuente: int | None) -> dict | None:
    """Puesto por puntos y ensayos desde 2023/24 (temporadas guardadas + la actual) en esa liga."""
    from datosdep import historico

    if not id_fuente or comp not in historico.NACIONALES:
        return None
    try:
        historico.completar(comp)
    except Exception:
        pass
    acum: dict[int, list[int]] = {}
    temporadas = set()
    for ruta in historico.HISTORICO.glob(f"*_{comp}.json"):
        try:
            dd = json.loads(ruta.read_text(encoding="utf-8"))
        except ValueError:
            continue
        if not dd:
            continue
        temporadas.add(dd["id_temp"])
        for pid, filas in (dd.get("jugadores") or {}).items():
            a = acum.setdefault(int(pid), [0, 0, 0])
            for r in filas:
                a[0] += r[3]
                a[1] += r[4]
                a[2] += r[2]
    if not temporadas:
        return None
    for j in actuales:
        a = acum.setdefault(int(j.id), [0, 0, 0])
        a[0] += j.puntos
        a[1] += j.ensayos
        a[2] += j.pj
    yo = acum.get(int(id_fuente))
    if not yo:
        return None
    return {"puntos": yo[0], "ensayos": yo[1], "pj": yo[2], "de": len(acum), "temporadas": len(temporadas) + 1,
            "puesto_puntos": 1 + sum(1 for a in acum.values() if a[0] > yo[0]),
            "puesto_ensayos": (1 + sum(1 for a in acum.values() if a[1] > yo[1])) if yo[1] else None,
            "puesto_pj": 1 + sum(1 for a in acum.values() if a[2] > yo[2])}


def rendimiento_jugador(cand: dict, cfg: dict, resumen: dict, filas: list, cliente, historico_pos: dict | None) -> dict | None:
    """Puntos por partido, peso en su equipo, titular/suplente, minutos y puntos por jornada (todo de datos guardados)."""
    from datosdep.minutos import minutos_jugador

    pj = len(filas)
    if not pj:
        return None
    equipo = cand["equipo"]
    partidos = _partidos_guardados(cand["comp"], cand["grupo"])
    puntos = sum(f[PUNTOS] for _, f in filas)
    dors = [f[DORSAL] or 0 for _, f in filas]
    pts_equipo = 0
    for pid, _ in filas:
        p = partidos.get(int(pid))
        if p:
            pts_equipo += (p["puntos_local"] if p["local"] == equipo else p["puntos_visitante"]) or 0
    suyos = {int(pid): f for pid, f in filas}
    barras = []
    for p in sorted((p for p in partidos.values() if equipo in (p["local"], p["visitante"])
                     and p.get("estado") == "jugado" and p.get("jornada")), key=lambda p: p["jornada"]):
        f = suyos.get(p["id"])
        barras.append({"j": p["jornada"], "pts": f[PUNTOS] if f else None})
    mins = []
    if cfg.get("fuente") != "origen_b":  # los ids de partido de otra plataforma pueden coincidir con los de esta
        for pid, f in filas:
            m = minutos_jugador(cliente.extra_acta(int(pid)), equipo, f[DORSAL] or 0)
            if m is not None:
                mins.append(m)
    todos = [j for j in jugadores_desde_resumen(resumen, todos=True) if j.pj >= 3]
    por_ppp = sorted(todos, key=lambda j: -(j.puntos / j.pj))
    puesto = next((i for i, j in enumerate(por_ppp, 1) if j.nombre == cand["nombre"] and j.equipo == equipo), None)
    return {
        "pj": pj, "puntos": puntos, "ppp": round(puntos / pj, 1), "puesto_ppp": puesto, "de_ppp": len(por_ppp),
        "titular": sum(1 for d in dors if 1 <= d <= 15), "suplente": sum(1 for d in dors if d > 15),
        "pct_equipo": round(100 * puntos / pts_equipo) if pts_equipo else None,
        "barras": barras,
        "minutos": {"total": sum(mins), "partidos": len(mins), "media": round(sum(mins) / len(mins))} if mins else None,
        "historico": historico_pos,
    }


def datos_jugador(cand: dict) -> dict:
    cfg = cargar_config()["competiciones"][cand["comp"]]
    ruta = ruta_jornada(cand["comp"], cand["grupo"], 0).with_name("resumen_partidos.json")
    resumen = json.loads(ruta.read_text(encoding="utf-8"))
    filas = [(pid, f) for pid, fs in resumen.items() for f in fs
             if f[NOMBRE] == cand["nombre"] and f[EQUIPO] == cand["equipo"]]
    tot = lambda i: sum(f[i] for _, f in filas)  # noqa: E731
    dorsales = Counter(f[DORSAL] for _, f in filas if f[DORSAL])
    dorsal = dorsales.most_common(1)[0][0] if dorsales else None
    posicion = POSICIONES.get(dorsal, "Desde el banquillo" if dorsal and dorsal > 15 else "")

    # Puesto en la liga por puntos y por ensayos
    tabla = jugadores_desde_resumen(resumen)
    por_puntos = sorted(tabla, key=lambda j: (-j.puntos, -j.ensayos))
    por_ensayos = sorted(tabla, key=lambda j: (-j.ensayos, -j.puntos))
    yo = lambda j: j.nombre == cand["nombre"] and j.equipo == cand["equipo"]  # noqa: E731
    puesto_p = next((i for i, j in enumerate(por_puntos, 1) if yo(j)), None)
    puesto_e = next((i for i, j in enumerate(por_ensayos, 1) if yo(j)), None) if tot(ENSAYOS) else None

    mejor = None
    escudos = {}
    id_fuente = None
    rend = None
    if filas:
        pid, f = max(filas, key=lambda x: (x[1][PUNTOS], x[1][ENSAYOS]))
        cliente = cliente_para(cfg)
        id_grupo = cfg["grupos"][cand["grupo"]]
        try:
            clasificacion = cliente.clasificacion(id_grupo)
            escudos = {x.equipo: x.escudo for x in clasificacion if x.escudo}
            comp_fuente = cliente.competicion(id_grupo)
            partidos = {p.id: p for p in comp_fuente.partidos}
            p = partidos.get(int(pid))
            id_fuente = _id_fuente(comp_fuente.jugadores, cand["nombre"], cand["equipo"])
            rend_hist = _ranking_historico(cand["comp"], comp_fuente.jugadores, id_fuente)
        except Exception:
            p = None
            rend_hist = None
        rend = rendimiento_jugador(cand, cfg, resumen, filas, cliente, rend_hist)
        if p and f[PUNTOS]:
            local = p.local == cand["equipo"]
            mejor = {"puntos": f[PUNTOS], "ensayos": f[ENSAYOS], "jornada": p.jornada,
                     "rival": p.visitante if local else p.local,
                     "marcador": f"{p.puntos_local}-{p.puntos_visitante}" if local else f"{p.puntos_visitante}-{p.puntos_local}"}
    return {
        "nombre": cand["nombre"], "equipo": cand["equipo"], "liga": cand["liga"],
        "comp": cand["comp"], "grupo": cand["grupo"], "dorsal": dorsal if dorsal and dorsal <= 15 else None,
        "posicion": posicion, "partidos": len(filas),
        "puntos": tot(PUNTOS), "ensayos": tot(ENSAYOS), "conversiones": tot(CONV), "golpes": tot(GOLPES),
        "drops": tot(DROPS), "amarillas": tot(AMARILLAS), "rojas": tot(ROJAS),
        "puesto_puntos": puesto_p, "puesto_ensayos": puesto_e, "mejor": mejor, "escudos": escudos,
        "id_fuente": id_fuente, "rend": rend,
    }


def _resumen_comparable(cand: dict) -> dict:
    """Esta temporada y toda su carrera en ligas nacionales, para compararlo con otro jugador."""
    d = datos_jugador(cand)
    filas, total = carrera_jugador(d)
    actual = {"pj": d["partidos"], "puntos": d["puntos"], "ensayos": d["ensayos"], "tarjetas": d["amarillas"] + d["rojas"]}
    carrera = total or {**actual, "temporadas": 1}
    return {"nombre": d["nombre"], "equipo": d["equipo"], "liga": d["liga"], "comp": d["comp"], "grupo": d["grupo"],
            "escudos": d["escudos"], "esta": {**actual, "ppp": round(actual["puntos"] / actual["pj"], 1) if actual["pj"] else 0.0},
            "carrera": carrera}


def _filas_comparacion(a: dict, b: dict) -> list[dict]:
    """Filas (etiqueta, valor a, valor b, quién gana) de las dos secciones de la comparación."""
    def fila(k, va, vb, menos_es_mejor=False):
        gana = None if va == vb else ("a" if (va < vb) == menos_es_mejor else "b")
        return {"k": k, "a": va, "b": vb, "gana": gana}

    e1, e2, c1, c2 = a["esta"], b["esta"], a["carrera"], b["carrera"]
    return [
        {"seccion": "Esta temporada"},
        fila("Partidos", e1["pj"], e2["pj"]), fila("Puntos", e1["puntos"], e2["puntos"]),
        fila("Puntos / partido", e1["ppp"], e2["ppp"]), fila("Ensayos", e1["ensayos"], e2["ensayos"]),
        {"seccion": "Su carrera · ligas nacionales"},
        fila("Temporadas", c1["temporadas"], c2["temporadas"]), fila("Partidos", c1["pj"], c2["pj"]),
        fila("Puntos", c1["puntos"], c2["puntos"]), fila("Ensayos", c1["ensayos"], c2["ensayos"]),
        fila("Tarjetas", c1["tarjetas"], c2["tarjetas"], menos_es_mejor=True),
    ]


def comparar_jugadores(cand_a: dict | str, cand_b: dict | str, formato: str = "post",
                       destino: Path | None = None) -> list[Path]:
    a = jugador_por_id(cand_a) if isinstance(cand_a, str) else cand_a
    b = jugador_por_id(cand_b) if isinstance(cand_b, str) else cand_b
    if not a or not b:
        return []
    ra, rb = _resumen_comparable(a), _resumen_comparable(b)
    slide = {"tipo": "comparar_jugadores", "clave": "comparar", "a": ra, "b": rb, "filas": _filas_comparacion(ra, rb),
             "liga": ra["liga"], "nombre": ra["nombre"], "equipo": ra["equipo"]}
    return _renderizar(ra["comp"], ra["grupo"], None, {**rb["escudos"], **ra["escudos"]}, slide, formato, destino)


def ficha_jugador(cand: dict | str, formato: str = "post", destino: Path | None = None) -> list[Path]:
    cand = jugador_por_id(cand) if isinstance(cand, str) else cand
    if not cand:
        return []
    d = datos_jugador(cand)
    slides = [{"tipo": "ficha_jugador", "clave": "ficha", **d}]
    filas, total = carrera_jugador(d)
    if len(filas) > 1:  # hay alguna temporada anterior: segunda imagen con su carrera
        slides.append({"tipo": "carrera_jugador", "clave": "carrera", **d, "filas": filas, "total": total})
    if d.get("rend"):  # tercera imagen: su rendimiento esta temporada
        slides.append({"tipo": "rendimiento_jugador", "clave": "rendimiento", **d})
    return _renderizar(d["comp"], d["grupo"], None, d["escudos"], slides, formato, destino)
