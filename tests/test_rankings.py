from dataclasses import asdict
from pathlib import Path

import pytest

from datosdep.core import estadisticas as E
from datosdep.core import rankings as R
from datosdep.pipeline import _fila_resumen
from datosdep.scraper import parsers as P

FX = Path(__file__).parent / "fixtures"


@pytest.fixture(scope="module")
def datos():
    comp = P.estadisticas((FX / "estadisticas.html").read_bytes())
    lineas = {1: [], 2: []}
    resumen = {}
    for j in (1, 2):
        for p in comp.jornada(j):
            a = P.acta((FX / f"acta_{p.id}.html").read_bytes(), p.id)
            ls = E.lineas_partido(p, a)
            lineas[j] += ls
            resumen[str(p.id)] = [_fila_resumen(ln) for ln in ls if ln.puntos or ln.tarjetas]
    clas = [asdict(f) for f in P.clasificacion((FX / "clasificacion.html").read_bytes())]
    return {"j2": [asdict(x) for x in lineas[2]], "resumen": resumen, "clas": clas, "lineas": lineas,
            "comp": comp}


def test_pie():
    assert R.pie(4, 0, 1) == 11
    assert R.desglose_pie(4, 0, 1) == "4 transf. · 1 drop"
    assert R.desglose_tarjetas(2, 1) == "2 amarillas · 1 roja"


def test_jornada(datos):
    pat = R.pateadores_jornada(datos["j2"])
    assert (pat[0]["nombre"], pat[0]["valor"], pat[0]["detalle"]) == ("SANTIAGO IGNACIO MANSILLA", 18, "6 golpes")
    ens = R.ensayadores_jornada(datos["j2"])
    assert ens[0]["nombre"] == "ADRIAN FERNANDEZ COUVREUR" and ens[0]["valor"] == 2
    assert all(f["rival"] for f in ens)


def test_temporada_cuadra_con_el_origen(datos):
    """Los puntos y ensayos acumulados coinciden con la tabla oficial de el origen A."""
    oficial = {(j.nombre, j.equipo): (j.puntos, j.ensayos) for j in datos["comp"].jugadores}
    tot = R.acumular(datos["resumen"])
    for clave, t in tot.items():
        if t["puntos"]:
            assert oficial[clave] == (t["puntos"], t["ensayos"]), clave
    pat = R.pateadores_temporada(tot)
    assert pat[0]["nombre"] == "SANTIAGO IGNACIO MANSILLA" and pat[0]["valor"] == 42


def test_disciplina_y_banquillo(datos):
    tot = R.acumular(datos["resumen"])
    dis = R.disciplina_temporada(tot)
    assert dis and dis[0]["valor"] >= dis[-1]["valor"]
    assert all(f["detalle"] for f in dis)
    banq = R.banquillo_temporada(tot)
    suplentes = {(ln.nombre, ln.equipo) for ls in datos["lineas"].values() for ln in ls if ln.dorsal >= 16}
    assert banq and all((f["nombre"], f["equipo"]) in suplentes for f in banq)


def test_bloques_equipos(datos):
    tot = R.acumular(datos["resumen"])
    b = {x["titulo"]: x for x in R.bloques_equipos(datos["clas"], tot)}
    assert b["Mejor ataque"]["filas"][0]["valor"] == max(f["tf"] for f in datos["clas"])
    assert b["Mejor defensa"]["filas"][0]["valor"] == min(f["tc"] for f in datos["clas"])
    assert "Más tarjetas" in b


def test_formato_resumen_antiguo_se_ignora():
    assert R.acumular({"1": [["A", "X", 5, 1]]}) == {}
