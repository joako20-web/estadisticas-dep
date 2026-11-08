"""'El dato de la jornada': hechos llamativos detectados con reglas fijas.

Cada regla devuelve tarjetas con un peso; se eligen las de más peso sin repetir
equipo. Todo sale de los resultados, las actas y la clasificación.
"""
from __future__ import annotations

from collections import defaultdict

from datosdep.core.rankings import PUNTOS
from datosdep.render import nombres


def _c(equipo: str) -> str:
    return nombres.equipo_corto(equipo)


def _j(nombre: str) -> str:
    return nombres.jugador(nombre)["completo"]


def _tarjeta(peso, numero, unidad, titular, contexto, equipo="") -> dict:
    return {"clave": "datos", "tipo": "dato", "peso": peso, "numero": str(numero),
            "unidad": unidad, "titular": titular, "contexto": contexto, "equipo": equipo}


def _secuencias(partidos: list[dict], hasta: int) -> dict[str, list[tuple[str, dict]]]:
    """Resultados de cada equipo por orden de jornada: [(G/E/P, partido), ...]."""
    seq: dict[str, list[tuple[str, dict]]] = defaultdict(list)
    for p in sorted(partidos, key=lambda p: (p["jornada"], p["fecha"] or "")):
        if p["puntos_local"] is None or p["jornada"] > hasta:
            continue
        pl, pv = p["puntos_local"], p["puntos_visitante"]
        seq[p["local"]].append(("G" if pl > pv else "E" if pl == pv else "P", p))
        seq[p["visitante"]].append(("G" if pv > pl else "E" if pl == pv else "P", p))
    return seq


def _racha(resultados: list[str], valores: set[str]) -> int:
    n = 0
    for r in reversed(resultados):
        if r not in valores:
            break
        n += 1
    return n


def reglas_equipos(partidos: list[dict], jornada: int) -> list[dict]:
    out = []
    for equipo, seq in _secuencias(partidos, jornada).items():
        res = [r for r, _ in seq]
        if not seq or seq[-1][1]["jornada"] != jornada:
            continue  # no jugó esta jornada
        pj = len(res)
        victorias = _racha(res, {"G"})
        if victorias == pj and pj >= 3:
            out.append(_tarjeta(60 + 6 * pj, pj, "partidos, todos ganados",
                                f"{_c(equipo)} sigue invicto", f"Pleno de victorias tras {pj} jornadas.", equipo))
        elif victorias >= 3:
            out.append(_tarjeta(50 + 6 * victorias, victorias, "victorias seguidas",
                                f"{_c(equipo)} no deja de ganar", f"Encadena {victorias} triunfos consecutivos.", equipo))
        if pj >= 3 and "G" not in res:
            out.append(_tarjeta(40 + 4 * pj, pj, "partidos sin ganar",
                                f"{_c(equipo)} sigue sin conocer la victoria",
                                f"Lleva {pj} jornadas buscando su primer triunfo.", equipo))
        derrotas = _racha(res, {"P"})
        if derrotas >= 3 and "G" in res:
            out.append(_tarjeta(35 + 4 * derrotas, derrotas, "derrotas seguidas",
                                f"Mala racha de {_c(equipo)}", f"Suma {derrotas} derrotas consecutivas.", equipo))
        # Primera victoria tras una mala racha
        if res[-1] == "G" and pj >= 4 and res[:-1].count("G") == 0:
            out.append(_tarjeta(58, 1, "primera victoria",
                                f"¡Por fin gana {_c(equipo)}!", f"Su primera victoria tras {pj - 1} jornadas.", equipo))
    return out


def regla_diferencia(partidos: list[dict], jornada: int) -> list[dict]:
    jugados = [p for p in partidos if p["puntos_local"] is not None and p["jornada"] <= jornada]
    if not jugados:
        return []
    margen = lambda p: abs(p["puntos_local"] - p["puntos_visitante"])
    record = max(margen(p) for p in jugados)
    out = []
    for p in jugados:
        if p["jornada"] != jornada or margen(p) < 25:
            continue
        gana = p["local"] if p["puntos_local"] > p["puntos_visitante"] else p["visitante"]
        pierde = p["visitante"] if gana == p["local"] else p["local"]
        es_record = margen(p) == record and jornada > 1
        out.append(_tarjeta(
            45 + margen(p) // 3 + (20 if es_record else 0), margen(p), "puntos de diferencia",
            f"Exhibición de {_c(gana)}",
            f"{_c(p['local'])} {p['puntos_local']}-{p['puntos_visitante']} {_c(p['visitante'])}"
            + (". La mayor diferencia de la temporada." if es_record else f". Paliza ante {_c(pierde)}."),
            gana,
        ))
    return out


def reglas_partidos(actas: list[tuple[dict, list[dict]]]) -> list[dict]:
    """Remontadas y finales agónicos a partir de la evolución del marcador."""
    out = []
    for p, eventos in actas:
        if p["puntos_local"] is None or p["puntos_local"] == p["puntos_visitante"]:
            continue
        gana_local = p["puntos_local"] > p["puntos_visitante"]
        gana = p["local"] if gana_local else p["visitante"]
        pierde = p["visitante"] if gana_local else p["local"]
        marcadores = sorted((e["minuto"], e["marcador"]) for e in eventos if e.get("marcador"))
        if not marcadores:
            continue
        # Desventaja máxima del ganador y último minuto en que se puso por delante
        peor, minuto_ventaja, iba_delante = 0, None, False
        for minuto, (ml, mv) in marcadores:
            dif = (ml - mv) if gana_local else (mv - ml)
            peor = min(peor, dif)
            if dif > 0 and not iba_delante:
                minuto_ventaja = minuto
            iba_delante = dif > 0
        res = f"{_c(p['local'])} {p['puntos_local']}-{p['puntos_visitante']} {_c(p['visitante'])}"
        if peor <= -10:
            out.append(_tarjeta(55 + abs(peor), abs(peor), "puntos de desventaja remontados",
                                f"Remontada de {_c(gana)}", f"Llegó a perder de {abs(peor)} ante {_c(pierde)}: {res}.", gana))
        elif minuto_ventaja is not None and minuto_ventaja >= 72:
            out.append(_tarjeta(62, f"{minuto_ventaja}'", "minuto de la victoria",
                                f"{_c(gana)} gana en el último suspiro",
                                f"Se puso por delante en el minuto {minuto_ventaja}: {res}.", gana))
    return out


def reglas_jugadores(lineas: list[dict], resumen: dict[str, list]) -> list[dict]:
    out = []
    record = max((j[PUNTOS] for jugadores in resumen.values() for j in jugadores), default=0)
    for ln in lineas:
        if ln["ensayos"] >= 3:
            out.append(_tarjeta(55 + 8 * ln["ensayos"], ln["ensayos"], "ensayos en un partido",
                                f"Hat-trick de {_j(ln['nombre'])}" if ln["ensayos"] == 3 else f"Exhibición de {_j(ln['nombre'])}",
                                f"Firmó {ln['ensayos']} ensayos ante {_c(ln['rival'])}.", ln["equipo"]))
        if ln["puntos"] >= 20:
            es_record = ln["puntos"] >= record
            out.append(_tarjeta(48 + ln["puntos"] // 2 + (20 if es_record else 0), ln["puntos"], "puntos en un partido",
                                f"{_j(ln['nombre'])} no falla",
                                f"Anotó {ln['puntos']} puntos ante {_c(ln['rival'])}"
                                + (", la mejor marca de la temporada." if es_record else "."),
                                ln["equipo"]))
    return out


def regla_lider(clasificacion: list[dict], lider_anterior: str | None) -> list[dict]:
    if not clasificacion or not lider_anterior:
        return []
    lider = clasificacion[0]
    if lider["equipo"] == lider_anterior:
        return []
    return [_tarjeta(70, lider["pt"], "puntos", f"{_c(lider['equipo'])}, nuevo líder",
                     f"Desbanca a {_c(lider_anterior)} de lo más alto de la tabla.", lider["equipo"])]


def regla_anotador_temporada(jugadores: list[dict]) -> list[dict]:
    if not jugadores:
        return []
    top = max(jugadores, key=lambda j: j["puntos"])
    if top["puntos"] < 30:
        return []
    return [_tarjeta(30, top["puntos"], "puntos esta temporada",
                     f"{_j(top['nombre'])} manda en la tabla de anotadores",
                     f"Suma {top['puntos']} puntos en {top['pj']} partidos con {_c(top['equipo'])}.", top["equipo"])]


def elegir(tarjetas: list[dict], n: int = 3) -> list[dict]:
    elegidas, equipos = [], set()
    for t in sorted(tarjetas, key=lambda t: -t["peso"]):
        if t["equipo"] and t["equipo"] in equipos:
            continue
        elegidas.append(t)
        equipos.add(t["equipo"])
        if len(elegidas) == n:
            break
    return elegidas


def calcular(partidos, jornada, lineas, actas, resumen, clasificacion, lider_anterior, jugadores) -> list[dict]:
    tarjetas = (
        reglas_equipos(partidos, jornada)
        + regla_diferencia(partidos, jornada)
        + reglas_partidos(actas)
        + reglas_jugadores(lineas, resumen)
        + regla_lider(clasificacion, lider_anterior)
        + regla_anotador_temporada(jugadores)
    )
    return elegir(tarjetas)
