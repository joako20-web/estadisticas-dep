"""Reel de la clasificación: gancho con el líder y tabla completa con zonas y movimientos."""
from __future__ import annotations

import json

from datosdep.pipeline import ruta_jornada
from datosdep.render import nombres
from datosdep.render import render as R
from datosdep.videos.base import colores_tema, props_base

COMPOSICION = "ReelClasificacion"
# Colores de las franjas de zona en el vídeo (la del título usa el acento del tema)
COLORES_ZONA = {"ascenso": "#5aa9f0", "promocion": "#f0a830", "descenso": "#ef5b4b", "fase": "#a98be8"}


def color_zona(zona: str, tema: str = "tele") -> str:
    if not zona:
        return ""
    if zona == "titulo":
        return colores_tema(tema).get("acento", "#f5c518")
    return COLORES_ZONA.get(zona, "#aab7d6")


def anterior(datos: dict) -> dict | None:
    """JSON de la jornada anterior si está guardado (sin descargar nada)."""
    if datos["jornada"] <= 1:
        return None
    ruta = ruta_jornada(datos["competicion"], datos["grupo"], datos["jornada"] - 1)
    return json.loads(ruta.read_text(encoding="utf-8")) if ruta.exists() else None


def movimientos(clasificacion: list[dict], previa: list[dict] | None) -> dict[str, int | None]:
    """Puestos ganados (+) o perdidos (-) por equipo; None si no hay con qué comparar."""
    # Sin previa, sin partidos jugados en ella (orden arbitrario) o guardada ya con los
    # partidos de esta jornada (se descargó tarde: no es la de antes): sin flechas
    jugados_antes = max((f.get("pj") or 0 for f in previa or []), default=0)
    jugados = max((f.get("pj") or 0 for f in clasificacion), default=0)
    valida = previa and 0 < jugados_antes < jugados
    antes = {f["equipo"]: f["posicion"] for f in previa} if valida else {}
    return {f["equipo"]: (antes[f["equipo"]] - f["posicion"]) if f["equipo"] in antes else None
            for f in clasificacion}


def props(datos: dict, previa: dict | None = None, tema: str = "tele") -> dict:
    if not datos["clasificacion"] or not any(f["pj"] for f in datos["clasificacion"]):
        raise RuntimeError("aún no hay clasificación")
    escudos = datos["escudos"]
    filas, leyenda = R.con_zonas(datos["clasificacion"], datos["competicion"], datos["grupo"])
    mov = movimientos(datos["clasificacion"], (previa or {}).get("clasificacion"))
    tabla = [{
        "pos": f["posicion"], "nombre": nombres.equipo_corto(f["equipo"]), "abr": nombres.equipo_abr(f["equipo"]),
        "escudo": R.escudo_equipo(f["equipo"], escudos), "pj": f["pj"], "pg": f.get("pg", 0), "pe": f.get("pe", 0),
        "pp": f.get("pp", 0), "pt": f["pt"], "dif": f.get("dt", 0), "zona": color_zona(f["zona"], tema),
        "mov": mov.get(f["equipo"]),
    } for f in filas]
    tras = max((f["pj"] for f in datos["clasificacion"]), default=datos["jornada"])
    return {
        **props_base(datos["competicion"], datos["jornada"], datos["temporada"], tema),
        "filas": tabla,
        "leyenda": [{"color": color_zona(z["color"], tema), "texto": z["texto"]} for z in leyenda],
        "trasJornada": tras,
        "ventaja": tabla[0]["pt"] - tabla[1]["pt"] if len(tabla) > 1 else 0,
    }
