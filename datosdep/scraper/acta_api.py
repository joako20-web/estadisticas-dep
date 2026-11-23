"""Acta desde el JSON de la API: se valida antes de darla por buena y se guarda sin datos de la fuente.

Un acta solo se acepta si sus datos son coherentes entre sí; si no, el bot prefiere no publicar
estadísticas de ese partido a publicar unas equivocadas.
"""
from __future__ import annotations

from datosdep.models import PUNTOS
from datosdep.scraper.parsers import tipo_evento
from datosdep.scraper.texto import limpiar

MIN_JUGADORES = 7  # por equipo: menos es un acta a medias


def validar(resp: dict, id_partido: int) -> tuple[list[set[int]], list[int] | None]:
    """Comprueba el acta y devuelve (dorsales de cada equipo [local, visitante], descuadre).

    ValueError si falta algo, si no hay jugadas o si la alineación es dudosa. Si las jugadas no suman el marcador
    del árbitro, el acta vale igualmente (manda el marcador oficial) y `descuadre` trae la suma de las jugadas."""
    if not isinstance(resp, dict) or not isinstance(resp.get("data"), dict):
        raise ValueError(f"acta {id_partido}: respuesta sin datos")
    d = resp["data"]
    try:
        part = d["partido"]
        ids = [int(part["local"]["id_equipo"]), int(part["visitante"]["id_equipo"])]
        marcador = [int(part["local"]["resultado"]), int(part["visitante"]["resultado"])]
    except (KeyError, TypeError, ValueError) as e:
        raise ValueError(f"acta {id_partido}: cabecera incompleta ({e!r})") from e
    if ids[0] == ids[1]:
        raise ValueError(f"acta {id_partido}: los dos equipos son el mismo")
    puntos = {ids[0]: 0, ids[1]: 0}
    for e in d.get("eventos") or []:
        try:
            eq = int(e["id_equipo"])
            texto = str(e["tipo_evento"])
        except (KeyError, TypeError, ValueError) as ex:
            raise ValueError(f"acta {id_partido}: evento sin equipo o tipo ({ex!r})") from ex
        if eq not in puntos:
            raise ValueError(f"acta {id_partido}: evento de un equipo que no juega ({eq})")
        puntos[eq] += PUNTOS.get(tipo_evento(texto), 0)
    suma = [puntos[ids[0]], puntos[ids[1]]]
    if suma != marcador and sum(suma) == 0:
        raise ValueError(f"acta sin eventos: el marcador es ({marcador[0]}, {marcador[1]}) y no hay jugadas")
    dorsales: list[set[int]] = [set(), set()]
    vistos: set[tuple[int, int]] = set()
    for j in d.get("alineaciones") or []:
        try:
            eq, dorsal = int(j["id_equipo"]), int(j.get("dorsal") or 0)
        except (KeyError, TypeError, ValueError):
            continue
        if eq not in ids or dorsal <= 0:
            continue  # técnicos y delegados llevan dorsal 0
        if (eq, dorsal) in vistos:
            raise ValueError(f"acta {id_partido}: dorsal {dorsal} repetido en un equipo")
        vistos.add((eq, dorsal))
        if not limpiar(j.get("nombre_jugador") or ""):
            raise ValueError(f"acta {id_partido}: jugador sin nombre (dorsal {dorsal})")
        dorsales[ids.index(eq)].add(dorsal)
    if min(len(dorsales[0]), len(dorsales[1])) < MIN_JUGADORES:
        raise ValueError(f"acta {id_partido}: alineación incompleta ({len(dorsales[0])} y {len(dorsales[1])} jugadores)")
    return dorsales, (suma if suma != marcador else None)


def limpia(resp: dict, descuadre: list[int] | None = None) -> dict:
    """Solo lo que el bot usa, sin direcciones de la fuente (fotos, escudos) ni técnicos."""
    d = resp["data"]
    p = d["partido"]
    lado = lambda x: {"id_equipo": int(x["id_equipo"]), "nombre": x["nombre"], "resultado": int(x["resultado"])}  # noqa: E731
    return {
        "fuente": "api",
        "descuadre": descuadre,
        "data": {
            "partido": {"local": lado(p["local"]), "visitante": lado(p["visitante"])},
            "eventos": [
                {k: e.get(k) for k in ("id_jugador", "tipo_evento", "minuto", "jugador", "id_equipo", "tantos")}
                for e in d.get("eventos") or []
            ],
            "alineaciones": [
                {"dorsal": int(j["dorsal"]), "id_jugador": j.get("id_jugador"), "nombre_jugador": j["nombre_jugador"],
                 "id_equipo": int(j["id_equipo"]), "goles": j.get("goles") or 0, "titular": j.get("titular"), "url_foto": ""}
                for j in d.get("alineaciones") or [] if int(j.get("dorsal") or 0) > 0
            ],
        },
    }
