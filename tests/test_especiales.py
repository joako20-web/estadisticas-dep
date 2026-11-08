from dataclasses import asdict
from pathlib import Path

from datosdep import especiales as X
from datosdep import evolucion as V
from datosdep.core import estadisticas as E
from datosdep.core import temporada as T
from datosdep.scraper import parsers as P

FX = Path(__file__).parent / "fixtures"


def _comp():
    return P.estadisticas((FX / "estadisticas.html").read_bytes())


def _actas(comp):
    return {p.id: P.acta((FX / f"acta_{p.id}.html").read_bytes(), p.id)
            for j in (1, 2) for p in comp.jornada(j)}


def test_tabla_reconstruida_reproduce_la_oficial():
    comp = _comp()
    actas = _actas(comp)
    tries = {pid: tuple(sum(1 for e in a.eventos if e.equipo == eq and e.tipo in ("ensayo", "ensayo_castigo"))
                        for eq in (a.local, a.visitante)) for pid, a in actas.items()}
    oficial = {f.equipo: f.pt for f in P.clasificacion((FX / "clasificacion.html").read_bytes())}
    regla = next(r for r in V.REGLAS if r[0].startswith("3 ensayos"))  # la de el origen A
    t = V.tabla(comp.partidos, tries, regla, 2)
    assert {f["equipo"]: f["pt"] for f in t} == oficial


def test_xv_y_mvp_de_temporada():
    comp = _comp()
    actas = _actas(comp)
    por_jornada = {j: [ln for p in comp.jornada(j) for ln in E.lineas_partido(p, actas[p.id])] for j in (1, 2)}
    acum = T.acumular(por_jornada)
    mvp = T.mvp_temporada(acum, 3)
    assert mvp[0].nombre == "SANTIAGO IGNACIO MANSILLA" and mvp[0].partidos == 2 and mvp[0].puntos == 42
    xv = T.xv_temporada(acum, 2)
    assert sorted(xv) == list(range(1, 16))
    assert len({ln.nombre for ln in xv.values()}) == 15


def test_partido_destacado_y_candidatos():
    datos = {
        "clasificacion": [{"equipo": e, "posicion": i} for i, e in enumerate("ABCDEF", 1)],
        "proxima_jornada": {"numero": 3, "partidos": [
            {"id": 1, "local": "A", "visitante": "F", "puntos_local": None},
            {"id": 2, "local": "B", "visitante": "C", "puntos_local": None},
            {"id": 3, "local": "D", "visitante": "E", "puntos_local": None},
        ]},
    }
    assert X.partido_destacado(datos)["id"] == 2  # 2º contra 3º
    comp = _comp()
    actas = _actas(comp)
    lineas = [ln for p in comp.jornada(2) for ln in E.lineas_partido(p, actas[p.id])]
    cands = X.candidatos_mvp({"candidatos_xv": [asdict(ln) for ln in lineas if 1 <= ln.dorsal <= 15]})
    assert len(cands) == 4 and cands[0]["nombre"] == "SANTIAGO IGNACIO MANSILLA"
