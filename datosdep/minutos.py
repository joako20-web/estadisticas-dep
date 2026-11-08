"""Minutos jugados por un jugador a partir de los cambios y tarjetas del acta en PDF.

Aproximado: los 15 titulares empiezan en el minuto 0 y los suplentes cuando entran; el partido dura 80'
(más si hay cambios después). Una amarilla resta 10', una roja de 20' resta 20' y una roja resta el
resto del partido. Los cambios temporales (p. ej. "de 1ª línea por TA o TR") se tratan como salida y
vuelta a entrar.
"""
from __future__ import annotations

AMARILLA_S, ROJA20_S = 600, 1200


def _solape(a: tuple[int, int], b: tuple[int, int]) -> int:
    return max(0, min(a[1], b[1]) - max(a[0], b[0]))


def minutos_jugador(extra: dict | None, equipo: str, dorsal: int) -> int | None:
    """Minutos en el campo, o None si no hay datos de cambios para ese acta."""
    if not extra or not dorsal or equipo not in extra.get("equipos", []):
        return None
    lado = extra["equipos"].index(equipo)
    fin = extra["fin"]
    dentro: int | None = 0 if 1 <= dorsal <= 15 else None
    tramos: list[tuple[int, int]] = []
    for l, seg, sale, entra, _ in sorted(extra["cambios"], key=lambda c: c[1]):
        if l != lado:
            continue
        if sale == dorsal and dentro is not None:
            tramos.append((dentro, seg))
            dentro = None
        if entra == dorsal and dentro is None:
            dentro = seg
    if dentro is not None:
        tramos.append((dentro, fin))
    for l, seg, d, tipo in extra["tarjetas"]:
        if l != lado or d != dorsal:
            continue
        if tipo == "roja":
            tramos = [(a, min(b, seg)) for a, b in tramos if a < seg]
        else:
            fuera = (seg, seg + (AMARILLA_S if tipo == "amarilla" else ROJA20_S))
            nuevos = []
            for a, b in tramos:  # se parte el tramo en dos si la suspensión cae en medio
                if _solape((a, b), fuera) == 0:
                    nuevos.append((a, b))
                    continue
                if a < fuera[0]:
                    nuevos.append((a, fuera[0]))
                if b > fuera[1]:
                    nuevos.append((fuera[1], b))
            tramos = nuevos
    return round(sum(b - a for a, b in tramos) / 60)
