from dataclasses import asdict
from pathlib import Path

from datosdep.core import datos as D
from datosdep.core import estadisticas as E
from datosdep.scraper import parsers as P

FX = Path(__file__).parent / "fixtures"


def _p(p):
    return asdict(p) | {"fecha": p.fecha.isoformat()}


def test_datos_jornada_2():
    comp = P.estadisticas((FX / "estadisticas.html").read_bytes())
    partidos = [_p(p) for p in comp.partidos if p.jugado]
    actas, lineas = [], []
    for p in comp.jornada(2):
        a = P.acta((FX / f"acta_{p.id}.html").read_bytes(), p.id)
        actas.append((_p(p), [asdict(e) for e in a.eventos]))
        lineas += [asdict(x) for x in E.lineas_partido(p, a)]
    tarjetas = D.calcular(partidos, 2, lineas, actas, {}, [], None, [asdict(j) for j in comp.jugadores])
    titulares = [t["titular"] for t in tarjetas]
    assert "Remontada de La Vila" in titulares          # perdía 7-26 y ganó 36-33
    assert any("El Salvador" in t for t in titulares)    # 45-20, mayor diferencia
    assert len({t["equipo"] for t in tarjetas}) == len(tarjetas)  # un dato por equipo


def test_rachas():
    def p(j, l, v, pl, pv):
        return {"jornada": j, "local": l, "visitante": v, "puntos_local": pl, "puntos_visitante": pv, "fecha": f"2026-10-0{j}"}
    partidos = [p(1, "A", "B", 30, 10), p(2, "C", "A", 5, 20), p(3, "A", "D", 25, 24), p(3, "B", "C", 3, 9),
                p(1, "C", "D", 10, 12), p(2, "B", "D", 0, 7)]
    t = {x["titular"]: x for x in D.reglas_equipos(partidos, 3)}
    assert t["A sigue invicto"]["numero"] == "3"
    assert t["B sigue sin conocer la victoria"]["numero"] == "3"
