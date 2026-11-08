"""Partido de la jornada: elige el cruce más atractivo de la próxima jornada de una
liga/grupo y prepara su previa (posición, forma, medias, anotadores, cara a cara).

Uso:
    datos, rutas = partido_jornada("dh_masc")                # elige solo
    datos, rutas = partido_jornada("dh_masc", id_partido=17657, formato="historia")
"""
from __future__ import annotations

import tempfile
from dataclasses import asdict
from datetime import date, datetime
from pathlib import Path

from datosdep.pipeline import es_descanso
from datosdep.core import partido_jornada as PJ
from datosdep.pipeline import cargar_config, jugadores_desde_resumen, resumen_temporada
from datosdep.render.nombres import titulo
from datosdep.render.render import renderizar_slides, zonas_de
from datosdep.scraper.origen_a import cliente_para


def _p(p) -> dict:
    d = asdict(p)
    d["fecha"] = p.fecha.isoformat() if p.fecha else None
    return d


def _zona_titulo(comp: str, grupo: str, n: int) -> int:
    for z in zonas_de(comp, grupo):
        if z["color"] in ("titulo", "ascenso") and z["desde"] == 1:
            return z["hasta"] if z["hasta"] > 0 else n + 1 + z["hasta"]
    return 0


def _proxima_jornada(pendientes: list[dict], hoy: date) -> int | None:
    """Jornada del próximo partido pendiente (con fecha de hoy en adelante si la hay)."""
    con_fecha = [p for p in pendientes if p["fecha"] and datetime.fromisoformat(p["fecha"]).date() >= hoy]
    base = con_fecha or pendientes
    if not base:
        return None
    return min(base, key=lambda p: (p["fecha"] or "9999", p["jornada"]))["jornada"]


def _info_equipo(equipo: str, fila: dict, partidos: list[dict], jugadores: list) -> dict:
    pf, pc = PJ.medias(fila)
    goleadores = sorted((j for j in jugadores if j.equipo == equipo and j.puntos > 0),
                        key=lambda j: (-j.puntos, -j.ensayos))
    top = goleadores[0] if goleadores else None
    return {
        "equipo": equipo, "posicion": fila["posicion"], "pt": fila["pt"], "pj": fila["pj"],
        "pg": fila["pg"], "pe": fila["pe"], "pp": fila["pp"],
        "forma": PJ.forma(equipo, partidos), "pf": pf, "pc": pc, "ensayos": fila.get("ef", 0),
        "anotador": {"nombre": top.nombre, "puntos": top.puntos, "ensayos": top.ensayos} if top else None,
    }


def datos_partido_jornada(comp: str, grupo: str = "unico", id_partido: int | None = None,
                          hoy: date | None = None) -> dict:
    """Datos de la previa del partido de la jornada. Lanza RuntimeError si no hay
    partidos pendientes. `id_partido` fuerza un partido concreto."""
    hoy = hoy or date.today()
    cfg = cargar_config()["competiciones"][comp]
    id_grupo = cfg["grupos"][grupo]
    cliente = cliente_para(cfg)
    clas = [asdict(f) for f in cliente.clasificacion(id_grupo)]
    competicion = cliente.competicion(id_grupo).filtrar(id_grupo, {f["equipo"] for f in clas})
    partidos = [d for p in competicion.partidos if not es_descanso(d := _p(p))]
    pendientes = [p for p in partidos if p["puntos_local"] is None]

    if id_partido is not None:
        elegido = next((p for p in partidos if p["id"] == id_partido), None)
        if elegido is None:
            raise RuntimeError(f"El partido {id_partido} no es de {comp}/{grupo}")
        puntos, razones = PJ.puntuar_cruce(elegido, {f["equipo"]: f for f in clas}, len(clas), partidos,
                                           _zona_titulo(comp, grupo, len(clas)))
        candidatos = []
    else:
        jornada = _proxima_jornada(pendientes, hoy)
        if jornada is None:
            raise RuntimeError(f"{cfg['nombre']}: no quedan partidos por jugar")
        candidatos = [p for p in pendientes if p["jornada"] == jornada]
        res = PJ.elegir_cruce(candidatos, clas, partidos, _zona_titulo(comp, grupo, len(clas)))
        if res is None:
            raise RuntimeError(f"{cfg['nombre']}: sin cruces en la jornada {jornada}")
        elegido, puntos, razones = res

    # Máximo anotador por equipo: tabla oficial (el origen A) o calculada con las actas (OrigenB)
    jugadores = competicion.jugadores or jugadores_desde_resumen(resumen_temporada(comp, grupo, competicion, cliente))
    por_equipo = {f["equipo"]: f for f in clas}
    otros = sorted(
        ((PJ.puntuar_cruce(p, por_equipo, len(clas), partidos)[0], p) for p in candidatos if p is not elegido),
        key=lambda x: -x[0])
    return {
        "competicion": comp, "grupo": grupo, "nombre": cfg["nombre"], "jornada": elegido["jornada"],
        "temporada": cargar_config()["temporada"],
        "escudos": {f["equipo"]: f["escudo"] for f in clas if f.get("escudo")},
        "partido": elegido, "puntuacion": puntos, "razones": razones,
        "local": _info_equipo(elegido["local"], por_equipo.get(elegido["local"], _vacia(elegido["local"])), partidos, jugadores),
        "visitante": _info_equipo(elegido["visitante"], por_equipo.get(elegido["visitante"], _vacia(elegido["visitante"])), partidos, jugadores),
        "cara_a_cara": PJ.cara_a_cara(elegido["local"], elegido["visitante"], partidos),
        "alternativas": [{"local": p["local"], "visitante": p["visitante"], "puntuacion": s} for s, p in otros[:3]],
    }


def _vacia(equipo: str) -> dict:
    return {"equipo": equipo, "posicion": 0, "pt": 0, "pj": 0, "pg": 0, "pe": 0, "pp": 0,
            "tf": 0, "tc": 0, "ef": 0}


def slide_partido_jornada(d: dict) -> dict:
    p = d["partido"]
    f = datetime.fromisoformat(p["fecha"]) if p["fecha"] else None
    cuando = []
    if f:
        cuando.append(f"{PJ.etiqueta_dia(f.date())}")
        if (f.hour, f.minute) != (0, 0):
            cuando.append(f.strftime("%H:%M"))
    if p.get("campo"):
        cuando.append(titulo(p["campo"].split("(")[0].strip()))
    h2h = d["cara_a_cara"]
    return {
        "tipo": "partido_jornada", "clave": "partido_jornada",
        "cuando": " · ".join(cuando) or "Fecha por confirmar",
        "local": d["local"], "visitante": d["visitante"],
        "razones": d["razones"][:3],
        "cara_a_cara": h2h,
    }


def renderizar_partido_jornada(d: dict, destino: Path | None = None, formato: str = "post",
                               tema: str | None = None) -> list[Path]:
    destino = destino or Path(tempfile.mkdtemp(prefix="partido_jornada_"))
    base = {k: d[k] for k in ("competicion", "grupo", "jornada", "temporada", "escudos")}
    return renderizar_slides(base, [slide_partido_jornada(d)], destino, formato, tema)


def partido_jornada(comp: str, grupo: str = "unico", id_partido: int | None = None,
                    formato: str = "post", destino: Path | None = None,
                    tema: str | None = None) -> tuple[dict, list[Path]]:
    """Elige (o usa `id_partido`) el partido de la jornada y genera su previa.
    Devuelve (datos, [ruta de la imagen])."""
    d = datos_partido_jornada(comp, grupo, id_partido)
    return d, renderizar_partido_jornada(d, destino, formato, tema)


def texto_partido_jornada(d: dict) -> str:
    """Texto para el post / Telegram con el porqué de la elección."""
    from datosdep.render.nombres import equipo_corto

    l, v = d["local"], d["visitante"]
    lineas = [f"🔥 Partido de la jornada · {d['nombre']} · J{d['jornada']}",
              f"{equipo_corto(l['equipo'])} ({l['posicion']}º, {l['pt']} pts) vs "
              f"{equipo_corto(v['equipo'])} ({v['posicion']}º, {v['pt']} pts)"]
    if d["razones"]:
        lineas.append("Por qué: " + ", ".join(d["razones"][:3]))
    return "\n".join(lineas)
