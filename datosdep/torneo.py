"""Vista de competición completa: todos los grupos en una imagen y cuadro de
eliminatorias (real, o "si acabara hoy" en las ligas con play-off)."""
from __future__ import annotations

import re
from dataclasses import asdict
from pathlib import Path

from datosdep.models import Partido
from datosdep.pipeline import cargar_config
from datosdep.render.render import con_zonas, renderizar_slides
from datosdep.scraper.origen_a import OrigenA, cliente_para

# Rondas de eliminatoria de menos a más avanzada (por palabra clave).
RONDAS = [("dieciseisavo", "Dieciseisavos"), ("octavo", "Octavos"), ("cuarto", "Cuartos"),
          ("semi", "Semifinales"), ("final", "Final")]


def _orden_ronda(ronda: str) -> int:
    r = ronda.lower()
    return next((i for i, (clave, _) in enumerate(RONDAS) if clave in r), -1)


def _nombre_ronda(i: int) -> str:
    return RONDAS[i][1]


def _p(p: Partido) -> dict:
    d = asdict(p)
    d["fecha"] = p.fecha.isoformat() if p.fecha else None
    return d


def datos_competicion(comp: str, cliente: OrigenA | None = None) -> dict:
    """Clasificación y partidos de todos los grupos de una competición."""
    cfg = cargar_config()["competiciones"][comp]
    cliente = cliente or cliente_para(cfg)
    grupos, escudos, partidos, eliminatorias = [], {}, [], {}
    for g, id_grupo in cfg["grupos"].items():
        clas = cliente.clasificacion(id_grupo)
        comp_g = cliente.competicion(id_grupo)
        filas, leyenda = con_zonas([asdict(f) for f in clas], comp, g)
        grupos.append({"grupo": g, "nombre": "Único" if g == "unico" else f"Grupo {g}",
                       "filas": filas, "leyenda": leyenda})
        escudos.update({f.equipo: f.escudo for f in clas if f.escudo})
        partidos += [_p(p) for p in comp_g.filtrar(id_grupo, set()).partidos if not p.ronda]
        # Las eliminatorias salen en la página de cualquier grupo de la competición
        for p in comp_g.partidos:
            if p.ronda and _orden_ronda(p.ronda) >= 0:
                eliminatorias[p.id] = _p(p)
    return {"grupos": grupos, "escudos": escudos, "partidos": partidos,
            "eliminatorias": list(eliminatorias.values()), "cfg": cfg}


def slide_grupos(dc: dict) -> dict | None:
    if len(dc["grupos"]) < 2:
        return None
    leyenda = []
    for g in dc["grupos"]:
        leyenda += [z for z in g["leyenda"] if z not in leyenda]
    return {"tipo": "grupos", "clave": "grupos", "grupos": dc["grupos"], "leyenda": leyenda,
            "exentos": dc["cfg"].get("exentos", []),
            "compacto": max(len(g["filas"]) for g in dc["grupos"]) > 4}


def _cruce(p: dict | None, a: str | None = None, b: str | None = None) -> dict:
    """Un cruce del cuadro: partido real, o huecos con los equipos previstos."""
    if p:
        jugado = p["puntos_local"] is not None
        gana = None
        if jugado and p["puntos_local"] != p["puntos_visitante"]:
            gana = p["local"] if p["puntos_local"] > p["puntos_visitante"] else p["visitante"]
        return {"local": p["local"], "visitante": p["visitante"], "pl": p["puntos_local"],
                "pv": p["puntos_visitante"], "gana": gana, "fecha": p["fecha"]}
    return {"local": a, "visitante": b, "pl": None, "pv": None, "gana": None, "fecha": None}


def cuadro_real(eliminatorias: list[dict]) -> list[dict] | None:
    """Rondas ordenadas de la primera a la final, con los cruces alineados para
    que los dos de arriba alimenten al primero de la siguiente ronda."""
    por_ronda: dict[int, list[dict]] = {}
    for p in eliminatorias:
        por_ronda.setdefault(_orden_ronda(p["ronda"]), []).append(p)
    if not por_ronda:
        return None
    primera, ultima = min(por_ronda), len(RONDAS) - 1
    rondas = [sorted(por_ronda.get(i, []), key=lambda p: p["fecha"] or "") for i in range(primera, ultima + 1)]

    # Reordenar hacia atrás: cada cruce de la ronda r+1 manda a sus dos "padres".
    for r in range(len(rondas) - 2, -1, -1):
        siguiente, actual = rondas[r + 1], rondas[r]
        ordenados = []
        for s in siguiente:
            for equipo in (s["local"], s["visitante"]):
                padre = next((p for p in actual if equipo in (p["local"], p["visitante"]) and p not in ordenados), None)
                if padre:
                    ordenados.append(padre)
        rondas[r] = ordenados + [p for p in actual if p not in ordenados]

    out = []
    n = max(1, len(rondas[0]))
    for i, partidos_ronda in enumerate(rondas):
        huecos = max(1, n // (2 ** i))
        cruces = [_cruce(p) for p in partidos_ronda] + [_cruce(None)] * (huecos - len(partidos_ronda))
        out.append({"nombre": _nombre_ronda(primera + i), "cruces": cruces[:huecos]})
    return out


def cuadro_provisional(clasificacion: list[dict], playoff: list[list[int]]) -> list[dict]:
    por_pos = {f["posicion"]: f["equipo"] for f in clasificacion}
    semis = [_cruce(None, por_pos.get(a), por_pos.get(b)) for a, b in playoff]
    for c, (a, b) in zip(semis, playoff):
        c["pos"] = (a, b)
    return [{"nombre": "Semifinales", "cruces": semis}, {"nombre": "Final", "cruces": [_cruce(None)]}]


def slide_cuadro(dc: dict) -> dict | None:
    rondas = cuadro_real(dc["eliminatorias"])
    provisional = False
    if not rondas and dc["cfg"].get("playoff") and len(dc["grupos"]) == 1:
        rondas = cuadro_provisional(dc["grupos"][0]["filas"], dc["cfg"]["playoff"])
        provisional = True
    if not rondas:
        return None
    final = rondas[-1]["cruces"][0]
    return {"tipo": "cuadro", "clave": "cuadro", "rondas": rondas, "provisional": provisional,
            "campeon": final["gana"]}


def ultima_jornada(dc: dict) -> int | None:
    js = [p["jornada"] for p in dc["partidos"] if p["puntos_local"] is not None]
    return max(js) if js else None


def slide_resultados(dc: dict, jornada: int) -> dict:
    partidos = sorted((p for p in dc["partidos"] if p["jornada"] == jornada), key=lambda p: p["fecha"] or "")
    return {"tipo": "resultados", "clave": "resultados", "partidos": partidos, "fechas": ""}


def renderizar(comp: str, claves: list[str], destino: Path, formato: str = "post",
               cliente: OrigenA | None = None) -> list[Path]:
    """Imágenes de nivel competición: "resultados" (todos los grupos), "grupos", "cuadro"."""
    dc = datos_competicion(comp, cliente)
    jornada = ultima_jornada(dc)
    slides = []
    for clave in claves:
        if clave == "resultados" and jornada:
            slides.append(slide_resultados(dc, jornada))
        elif clave == "grupos" and (s := slide_grupos(dc)):
            slides.append(s)
        elif clave == "cuadro" and (s := slide_cuadro(dc)):
            slides.append(s)
    datos = {"competicion": comp, "grupo": "unico", "jornada": jornada,
             "temporada": cargar_config()["temporada"], "escudos": dc["escudos"]}
    return renderizar_slides(datos, slides, destino, formato)


def tiene_cuadro(comp: str) -> bool:
    cfg = cargar_config()["competiciones"][comp]
    return bool(cfg.get("playoff") or cfg.get("torneo"))


