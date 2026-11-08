"""Anotadores de la jornada y XV ideal a partir de las actas."""
from __future__ import annotations

from collections import defaultdict
from dataclasses import asdict, dataclass, field

from datosdep.models import Acta, Partido

POSICIONES = {
    1: "Pilier izquierdo", 2: "Talonador", 3: "Pilier derecho",
    4: "Segunda línea", 5: "Segunda línea", 6: "Flanker", 7: "Flanker",
    8: "Número 8", 9: "Medio de melé", 10: "Apertura", 11: "Ala",
    12: "Centro", 13: "Centro", 14: "Ala", 15: "Zaguero",
}
# Dorsales intercambiables: se eligen los mejores N del grupo.
GRUPOS_POSICION = [(1,), (2,), (3,), (4, 5), (6, 7), (8,), (9,), (10,), (11, 14), (12, 13), (15,)]

# Pesos de la fórmula del XV ideal (ajustables).
PESO_PUNTO = 1.0
EXTRA_ENSAYO = 3.0
BONUS_VICTORIA = 4.0
BONUS_EMPATE = 2.0
BONUS_MARGEN_MAX = 3.0  # +0.1 por punto de diferencia, hasta 30
CASTIGO = {"amarilla": -4.0, "roja20": -6.0, "roja": -10.0}


@dataclass
class LineaJugador:
    nombre: str
    equipo: str
    dorsal: int
    puntos: int = 0
    ensayos: int = 0
    conversiones: int = 0
    golpes: int = 0
    drops: int = 0
    tarjetas: list[str] = field(default_factory=list)
    resultado: str = ""  # "G", "E", "P"
    margen: int = 0
    rival: str = ""
    nota: float = 0.0
    foto: str = ""


def lineas_partido(p: Partido, a: Acta) -> list[LineaJugador]:
    """Una línea por jugador convocado, con su aportación al partido."""
    lineas: dict[tuple[str, str], LineaJugador] = {}
    for equipo, rival, alineacion, pf, pc in (
        (a.local, a.visitante, a.alineacion_local, p.puntos_local, p.puntos_visitante),
        (a.visitante, a.local, a.alineacion_visitante, p.puntos_visitante, p.puntos_local),
    ):
        res = "G" if pf > pc else "E" if pf == pc else "P"
        for j in alineacion:
            lineas[(equipo, j.nombre)] = LineaJugador(
                j.nombre, equipo, j.dorsal, resultado=res, margen=pf - pc, rival=rival, foto=j.foto
            )
    contadores = {"ensayo": "ensayos", "conversion": "conversiones", "golpe": "golpes", "drop": "drops"}
    for e in a.eventos:
        ln = lineas.get((e.equipo, e.jugador))
        if ln is None:
            continue  # ensayo de castigo o jugador no encontrado
        ln.puntos += e.puntos
        if e.tipo in contadores:
            setattr(ln, contadores[e.tipo], getattr(ln, contadores[e.tipo]) + 1)
        elif e.tipo in CASTIGO:
            ln.tarjetas.append(e.tipo)
    for ln in lineas.values():
        ln.nota = nota(ln)
    return list(lineas.values())


def nota(ln: LineaJugador) -> float:
    n = ln.puntos * PESO_PUNTO + ln.ensayos * EXTRA_ENSAYO
    n += {"G": BONUS_VICTORIA, "E": BONUS_EMPATE}.get(ln.resultado, 0.0)
    n += max(min(ln.margen, 30), -30) * BONUS_MARGEN_MAX / 30
    n += sum(CASTIGO[t] for t in ln.tarjetas)
    return round(n, 2)


def anotadores(lineas: list[LineaJugador], top: int = 10) -> list[LineaJugador]:
    con_puntos = [ln for ln in lineas if ln.puntos > 0]
    return sorted(con_puntos, key=lambda ln: (-ln.puntos, -ln.ensayos, ln.nombre))[:top]


def maximos_ensayadores(lineas: list[LineaJugador], top: int = 5) -> list[LineaJugador]:
    con = [ln for ln in lineas if ln.ensayos > 0]
    return sorted(con, key=lambda ln: (-ln.ensayos, -ln.puntos, ln.nombre))[:top]


def xv_ideal(lineas: list[LineaJugador], max_por_equipo: int = 4) -> dict[int, LineaJugador]:
    """Mejor titular por dorsal 1-15, como mucho `max_por_equipo` por club.

    Reparto voraz: se recorren todos los candidatos de mejor a peor nota y cada
    uno ocupa un hueco libre de su grupo de posición si su club no está lleno.
    """
    grupo_de = {d: g for g in GRUPOS_POSICION for d in g}
    candidatos = sorted(
        (ln for ln in lineas if 1 <= ln.dorsal <= 15),
        key=lambda ln: (-ln.nota, -ln.margen, -ln.puntos, ln.nombre),
    )
    huecos = {g: list(g) for g in GRUPOS_POSICION}
    por_equipo: dict[str, int] = defaultdict(int)
    xv: dict[int, LineaJugador] = {}
    for ln in candidatos:
        libres = huecos[grupo_de[ln.dorsal]]
        if not libres or por_equipo[ln.equipo] >= max_por_equipo:
            continue
        xv[libres.pop(0)] = ln
        por_equipo[ln.equipo] += 1
        if len(xv) == 15:
            break
    return dict(sorted(xv.items()))


def a_dict(ln: LineaJugador) -> dict:
    return asdict(ln)
