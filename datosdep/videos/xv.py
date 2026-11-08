"""Reel "XV ideal": gancho, campo que se dibuja con los 15 apareciendo por líneas,
el mejor del XV destacado y cierre."""
from __future__ import annotations

from datosdep.core.estadisticas import POSICIONES
from datosdep.render import nombres
from datosdep.videos import base
from datosdep.videos.base import props_base
from datosdep.videos.mvp import ficha

COMPOSICION = "ReelXV"

# Orden de aparición (de delante hacia atrás) y colocación en el campo: cada grupo es una fila.
LINEAS = [
    ("Primera línea", (1, 2, 3)),
    ("Segunda línea", (4, 5)),
    ("Tercera línea", (6, 8, 7)),
    ("Medios", (9, 10)),
    ("Centros", (12, 13)),
    ("Alas y zaguero", (11, 15, 14)),
]


def props(datos: dict, tema: str = "tele") -> dict:
    xv = datos.get("xv_ideal") or {}
    if len(xv) < 15:
        raise RuntimeError(f"la jornada {datos['jornada']} no tiene XV ideal (faltan actas con alineaciones)")
    escudos = datos.get("escudos", {})
    mejor = max(xv, key=lambda d: (xv[d].get("nota", 0), xv[d]["puntos"]))
    lineas = []
    for titulo, puestos in LINEAS:
        jugadores = []
        for d in puestos:
            x = xv[str(d)]
            j = nombres.jugador(x["nombre"])
            jugadores.append({"puesto": d, "nombre": j["nombre"], "apellido": j["corto"],
                              "equipo": nombres.equipo_corto(x["equipo"]), "abr": nombres.equipo_abr(x["equipo"]),
                              "escudo": base.R.escudo_equipo(x["equipo"], escudos), "posicion": POSICIONES[d],
                              "mejor": str(d) == mejor})
        lineas.append({"titulo": titulo, "jugadores": jugadores})
    return {**props_base(datos["competicion"], datos["jornada"], datos["temporada"], tema),
            "lineas": lineas, "mejor": ficha(datos, con_foto=False)}
