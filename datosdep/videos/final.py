"""Reel "Así fue" de un partido: marcador final con el relato, evolución del marcador
minuto a minuto, línea de tiempo de los ensayos, anotadores y cierre.

Uso desde Python (el partido se pide por id, no por liga):

    from datosdep.videos import reel
    reel("dh_masc", "unico", 2, tipo="final", id_partido=17648)   # -> out/reel_final_..._p17648.mp4

    # ids de los partidos jugados de una jornada (para ofrecerlos en un menú):
    from datosdep.videos.final import id_partidos_jornada
    id_partidos_jornada("dh_masc", "unico", 2)   # -> [(17648, "La Vila 36-33 Santboiana"), ...]

Si el acta está incompleta (los eventos no suman el resultado), el vídeo sale igual pero
solo con el marcador (sin evolución, ensayos ni anotadores) en lugar de fallar.
"""
from __future__ import annotations

import json

from datetime import datetime

from datosdep.models import PUNTOS, Acta
from datosdep.pipeline import cargar_config
from datosdep.render import nombres
from datosdep.render import render as R
from datosdep.render.render import MESES
from datosdep.videos.base import datos_jornada, equipo, props_base

COMPOSICION = "ReelFinal"
MAX_ANOTADORES = 4
MAX_LETRAS_ENSAYO = 16  # lo que cabe al lado de la línea de tiempo a 44 px
_PARTICULAS = {"de", "del", "la", "las", "los", "da", "das", "do", "dos", "van", "von", "di"}
ENSAYOS = ("ensayo", "ensayo_castigo")
# Dentro de un mismo minuto: el ensayo antes que su transformación
_ORDEN_TIPO = {"ensayo": 0, "ensayo_castigo": 0, "golpe": 1, "drop": 1, "conversion": 2}
_DETALLE = (("ensayos", "ensayo", "ensayos"), ("conversiones", "transf.", "transf."),
            ("golpes", "golpe", "golpes"), ("drops", "drop", "drops"))


def id_partidos_jornada(comp: str, grupo: str = "unico", jornada: int | None = None) -> list[tuple[int, str]]:
    """(id, "Local 36-33 Visitante") de los partidos jugados de la jornada."""
    datos = datos_jornada(comp, grupo, jornada)
    return [(p["id"], f"{nombres.equipo_corto(p['local'])} {p['puntos_local']}-{p['puntos_visitante']} "
                      f"{nombres.equipo_corto(p['visitante'])}")
            for p in datos["partidos"] if p.get("puntos_local") is not None]


def construir(comp: str, grupo: str = "unico", jornada: int | None = None, id_partido: int | None = None,
              cliente=None, **_) -> dict:
    """Props del reel (registrado en PLANTILLAS como "final")."""
    if id_partido is None:
        raise RuntimeError("falta id_partido para el vídeo del partido")
    id_partido = int(id_partido)
    datos = datos_jornada(comp, grupo, jornada)
    p = next((x for x in datos["partidos"] + datos.get("partidos_temporada", []) if x["id"] == id_partido), None)
    if p is not None and p.get("puntos_local") is None:  # guardado antes de acabar el partido: datos frescos
        from datosdep.pipeline import preparar_jornada

        datos = json.loads(preparar_jornada(comp, grupo, jornada).read_text(encoding="utf-8"))
        p = next((x for x in datos["partidos"] + datos.get("partidos_temporada", []) if x["id"] == id_partido), None)
    if p is None:
        raise RuntimeError(f"el partido {id_partido} no está en la jornada {datos['jornada']}")
    if p.get("puntos_local") is None:
        raise RuntimeError("el partido aún no tiene resultado")
    acta = _acta(comp, grupo, id_partido, cliente)
    return props(p, acta, datos["escudos"], comp, datos["temporada"])


def _acta(comp: str, grupo: str, id_partido: int, cliente=None) -> Acta | None:
    from datosdep.scraper.origen_a import cliente_para

    cfg = cargar_config()["competiciones"][comp]
    cliente = cliente or cliente_para(cfg)
    try:
        if cfg.get("fuente") == "origen_b":  # el acta de OrigenB toma los nombres del calendario
            cliente.competicion(cfg["grupos"][grupo])
        return cliente.acta(id_partido)
    except Exception as e:  # sin acta el vídeo sale solo con el marcador
        print(f"[final] acta {id_partido} no disponible: {e}")
        return None


def anotaciones(acta: Acta, local: str, visitante: str) -> list[dict]:
    """Eventos con puntos en orden, con el marcador acumulado tras cada uno."""
    con_puntos = [e for e in acta.eventos if e.tipo in PUNTOS and e.equipo in (local, visitante)]

    def clave(e):
        suma = sum(e.marcador) if e.marcador else 0
        return (e.minuto, suma, _ORDEN_TIPO.get(e.tipo, 1))

    out, ml, mv = [], 0, 0
    for e in sorted(con_puntos, key=clave):
        if e.equipo == local:
            ml += e.puntos
        else:
            mv += e.puntos
        out.append({"minuto": e.minuto, "lado": "L" if e.equipo == local else "V", "tipo": e.tipo,
                    "puntos": e.puntos, "local": ml, "visitante": mv, "jugador": e.jugador})
    return out


def _apellido(nombre: str) -> str:
    """Apellidos para la línea de tiempo. Con 3 palabras no se sabe si la segunda es nombre o
    apellido (LUCAS MAXIMILIANO MELIAN / PAU MASSONI SALADO), así que se dejan los dos si caben."""
    if not nombre:
        return "Castigo"
    j = nombres.jugador(nombre)
    if len(j["apellidos"]) <= MAX_LETRAS_ENSAYO:
        return j["apellidos"]
    # Demasiado largo: los dos últimos apellidos (con su partícula: "Da Luz Silva"), o el último
    palabras = nombres.titulo(nombre).split()
    for n in (2, 1):
        k = len(palabras) - n
        while k > 1 and palabras[k - 1].lower() in _PARTICULAS:
            k -= 1
        opcion = " ".join(palabras[k:])
        if len(opcion) <= MAX_LETRAS_ENSAYO:
            return opcion
    return palabras[-1][:MAX_LETRAS_ENSAYO - 1] + "."


def relato(anot: list[dict], pl: int, pv: int, completa: bool) -> tuple[str, str]:
    """Etiqueta del gancho (REMONTADA, EN EL ÚLTIMO MINUTO...) y su frase. ("", "") si no hay historia."""
    if pl == pv:
        return "Empate", "Reparto de puntos"
    gana_local = pl > pv
    margen = abs(pl - pv)
    if completa and anot:
        peor, ventaja, delante = 0, None, False
        for a in anot:
            dif = (a["local"] - a["visitante"]) * (1 if gana_local else -1)
            peor = min(peor, dif)
            if dif > 0 and not delante:
                ventaja = a["minuto"]
            delante = dif > 0
        if peor <= -10:
            final = f" en el {ventaja}'" if ventaja and ventaja >= 72 else ""
            return "Remontada", f"De perder por {-peor} a ganar{final}"
        if ventaja and ventaja >= 76:
            return "En el último minuto", f"Se puso por delante en el {ventaja}'"
        if ventaja and ventaja >= 70:
            return "Final de infarto", f"Se puso por delante en el {ventaja}'"
    if margen >= 40:
        return "Paliza", f"{margen} puntos de diferencia"
    if margen <= 3:
        return "Al límite", f"Decidido por {margen} punto{'s' if margen > 1 else ''}"
    if completa:
        eg = sum(1 for a in anot if a["tipo"] in ENSAYOS and (a["lado"] == "L") == gana_local)
        ep = sum(1 for a in anot if a["tipo"] in ENSAYOS and (a["lado"] == "L") != gana_local)
        if eg >= 4 and eg - ep >= 3:
            return "Bonus ofensivo", f"{eg} ensayos a {ep}"
    if margen >= 25:
        return "Paliza", f"{margen} puntos de diferencia"
    return "", ""


def _anotadores(anot: list[dict]) -> list[dict]:
    por: dict[tuple[str, str], dict] = {}
    contadores = {"ensayo": "ensayos", "conversion": "conversiones", "golpe": "golpes", "drop": "drops"}
    for a in anot:
        if not a["jugador"] or a["tipo"] not in contadores:
            continue
        j = por.setdefault((a["lado"], a["jugador"]), {"lado": a["lado"], "jugador": a["jugador"], "puntos": 0,
                                                       "ensayos": 0, "conversiones": 0, "golpes": 0, "drops": 0})
        j["puntos"] += a["puntos"]
        j[contadores[a["tipo"]]] += 1
    top = sorted(por.values(), key=lambda j: (-j["puntos"], -j["ensayos"], j["jugador"]))[:MAX_ANOTADORES]
    out = []
    for j in top:
        n = nombres.jugador(j["jugador"])
        detalle = " · ".join(f"{j[k]} {uno if j[k] == 1 else varios}" for k, uno, varios in _DETALLE if j[k])
        out.append({"nombre": n["nombre"], "apellidos": n["corto"], "lado": j["lado"], "puntos": j["puntos"],
                    "detalle": detalle})
    return out


def _cuando(p: dict) -> str:
    f = datetime.fromisoformat(p["fecha"]) if p.get("fecha") else None
    return f"{f.day} {MESES[f.month - 1]}" if f else ""


def props(p: dict, acta: Acta | None, escudos: dict, comp: str, temporada: str, tema: str = "tele") -> dict:
    """Props del ReelFinal a partir del partido (dict de la jornada) y su acta (o None)."""
    pl, pv = p["puntos_local"], p["puntos_visitante"]
    anot = anotaciones(acta, p["local"], p["visitante"]) if acta else []
    completa = bool(anot) and (anot[-1]["local"], anot[-1]["visitante"]) == (pl, pv)
    if not completa:
        anot = []
    etiqueta, frase = relato(anot, pl, pv, completa)
    loc = equipo(p["local"], escudos, pl, pl > pv)
    vis = equipo(p["visitante"], escudos, pv, pv > pl)
    loc["ensayos"] = sum(1 for a in anot if a["tipo"] in ENSAYOS and a["lado"] == "L")
    vis["ensayos"] = sum(1 for a in anot if a["tipo"] in ENSAYOS and a["lado"] == "V")
    return {
        **props_base(comp, p["jornada"], temporada, tema),
        "idPartido": p["id"], "ronda": p.get("ronda") or "", "cuando": _cuando(p),
        "local": loc, "visitante": vis, "etiqueta": etiqueta, "frase": frase, "completa": completa,
        "evolucion": [{k: a[k] for k in ("minuto", "lado", "tipo", "local", "visitante")} for a in anot],
        "ensayos": [{"minuto": a["minuto"], "lado": a["lado"], "jugador": _apellido(a["jugador"]),
                     "castigo": a["tipo"] == "ensayo_castigo"} for a in anot if a["tipo"] in ENSAYOS],
        "anotadores": _anotadores(anot),
    }
