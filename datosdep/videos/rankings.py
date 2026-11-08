"""Reel de rankings de la temporada: top 5 de anotadores, ensayadores y pateadores."""
from __future__ import annotations

from datosdep.render import nombres
from datosdep.render import render as R
from datosdep.videos.base import props_base

COMPOSICION = "ReelRankings"
TOP = 5


def _fila(nombre: str, equipo: str, valor: int, escudos: dict, detalle: str = "") -> dict:
    j = nombres.jugador(nombre)
    return {"nombre": j["nombre"], "apellidos": j["apellidos"], "corto": j["corto"], "equipo": nombres.equipo_corto(equipo),
            "escudo": R.escudo_equipo(equipo, escudos), "valor": valor, "detalle": detalle}


def _top(filas: list[dict]) -> list[dict]:
    """Los TOP primeros con su puesto (los empatados comparten puesto)."""
    filas = filas[:TOP]
    for f in filas:
        f["pos"] = 1 + sum(o["valor"] > f["valor"] for o in filas)
    return filas


def bloques(datos: dict) -> list[dict]:
    """Bloques con datos (los vacíos se omiten): anotadores, ensayadores y pateadores."""
    escudos = datos["escudos"]
    rk = datos.get("rankings") or {}
    salida = []

    anot = sorted((x for x in datos.get("temporada_anotadores") or [] if x.get("puntos")),
                  key=lambda x: (-x["puntos"], x["nombre"]))[:TOP]
    if anot:
        salida.append({"clave": "anotadores", "titulo": "Máximos anotadores", "unidad": "puntos",
                       "filas": _top([_fila(x["nombre"], x["equipo"], x["puntos"], escudos) for x in anot])})

    ens = sorted((x for x in datos.get("temporada_ensayadores") or [] if x.get("ensayos")),
                 key=lambda x: (-x["ensayos"], -x.get("puntos", 0), x["nombre"]))[:TOP]
    filas = [_fila(x["nombre"], x["equipo"], x["ensayos"], escudos) for x in ens]
    if not filas:  # sin tabla oficial: la calculada con las actas
        filas = [_fila(x["nombre"], x["equipo"], x["valor"], escudos)
                 for x in (rk.get("ensayadores_t") or [])[:TOP] if x["valor"]]
    if filas:
        salida.append({"clave": "ensayadores", "titulo": "Máximos ensayadores", "unidad": "ensayos", "filas": _top(filas)})

    pat = [_fila(x["nombre"], x["equipo"], x["valor"], escudos, x.get("detalle", ""))
           for x in (rk.get("pateadores_t") or [])[:TOP] if x["valor"]]
    if pat:
        salida.append({"clave": "pateadores", "titulo": "Mejores pateadores", "unidad": "puntos al pie", "filas": _top(pat)})
    return salida


def props(datos: dict, tema: str = "tele") -> dict:
    lista = bloques(datos)
    if not lista:
        raise RuntimeError("aún no hay rankings de temporada")
    tras = max((f["pj"] for f in datos.get("clasificacion") or []), default=datos["jornada"])
    return {**props_base(datos["competicion"], datos["jornada"], datos["temporada"], tema),
            "bloques": lista, "trasJornada": tras}
