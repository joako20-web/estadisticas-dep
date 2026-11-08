"""Reel del dato de la jornada: número gigante, unidad, titular, contexto y escudo."""
from __future__ import annotations

import re

from datosdep.render import nombres
from datosdep.render import render as R
from datosdep.videos.base import props_base

COMPOSICION = "ReelDato"


def _de_resultados(datos: dict) -> dict | None:
    """Sin "datos de la jornada": la victoria más amplia."""
    jugados = [p for p in datos.get("partidos") or [] if p.get("puntos_local") is not None]
    if not jugados:
        return None
    p = max(jugados, key=lambda p: abs(p["puntos_local"] - p["puntos_visitante"]))
    pl, pv = p["puntos_local"], p["puntos_visitante"]
    marcador = f"{nombres.equipo_corto(p['local'])} {pl}-{pv} {nombres.equipo_corto(p['visitante'])}"
    if pl == pv:
        return {"numero": str(pl), "unidad": "puntos por bando", "titular": "Reparto de puntos",
                "contexto": marcador, "equipo": ""}
    gana = p["local"] if pl > pv else p["visitante"]
    return {"numero": str(abs(pl - pv)), "unidad": "puntos de diferencia",
            "titular": f"Exhibición de {nombres.equipo_corto(gana)}", "contexto": marcador, "equipo": gana}


def partir_numero(numero: str) -> tuple[str, int | None, str]:
    """Separa la parte que cuenta: "73'" -> ("", 73, "'"); "+31" -> ("+", 31, ""); "x" -> ("x", None, "")."""
    m = re.fullmatch(r"(\D*?)(\d+)(\D*)", numero.strip())
    if not m:
        return numero, None, ""
    return m.group(1), int(m.group(2)), m.group(3)


def props(datos: dict, indice: int = 0, tema: str = "tele") -> dict:
    lista = datos.get("datos_jornada") or []
    if lista:
        d = lista[min(max(int(indice), 0), len(lista) - 1)]
    else:
        d = _de_resultados(datos)
        if not d:
            raise RuntimeError(f"la jornada {datos['jornada']} aún no tiene resultados")
    antes, valor, despues = partir_numero(str(d["numero"]))
    equipo = d.get("equipo") or ""
    return {
        **props_base(datos["competicion"], datos["jornada"], datos["temporada"], tema),
        "dato": {"numero": str(d["numero"]), "antes": antes, "valor": valor, "despues": despues,
                 "unidad": d.get("unidad", ""), "titular": d.get("titular", ""), "contexto": d.get("contexto", ""),
                 "equipo": nombres.equipo_corto(equipo) if equipo else "",
                 "escudo": R.escudo_equipo(equipo, datos["escudos"]) if equipo else ""},
        "total": len(lista),
    }
