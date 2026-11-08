"""Props de los vídeos de clasificación, rankings y dato de la jornada (sin red ni Node)."""
import json

import pytest

from datosdep.pipeline import ruta_jornada
from datosdep.videos import PLANTILLAS, base, clasificacion, dato, rankings


@pytest.fixture(autouse=True)
def sin_red(monkeypatch):
    monkeypatch.setattr(base.R, "escudo_equipo", lambda equipo, escudos: "data:x")


def _datos(comp="dh_masc", grupo="unico", j=3):
    return json.loads(ruta_jornada(comp, grupo, j).read_text(encoding="utf-8"))


def test_registradas():
    for clave, comp in (("clasificacion", "ReelClasificacion"), ("rankings", "ReelRankings"), ("dato", "ReelDato")):
        assert PLANTILLAS[clave].composicion == comp


def test_clasificacion_con_movimientos():
    datos = _datos()
    previa = clasificacion.anterior(datos)
    assert previa and previa["jornada"] == 2
    p = clasificacion.props(datos, previa)
    assert [f["pos"] for f in p["filas"]] == list(range(1, 11))
    assert all(isinstance(f["mov"], int) for f in p["filas"])
    # el movimiento cuadra con las posiciones de la jornada anterior
    antes = {f["equipo"]: f["posicion"] for f in previa["clasificacion"]}
    for f, bruta in zip(p["filas"], datos["clasificacion"]):
        assert f["mov"] == antes[bruta["equipo"]] - bruta["posicion"]
    assert sum(f["mov"] for f in p["filas"]) == 0
    # zonas: las 4 primeras (semifinales, color acento) y el último (descenso)
    assert all(f["zona"] == p["tema"]["acento"] for f in p["filas"][:4])
    assert p["filas"][-1]["zona"] == clasificacion.COLORES_ZONA["descenso"]
    assert [z["texto"] for z in p["leyenda"]] == ["Semifinales por el título", "Desciende a DH Élite"]
    assert p["ventaja"] == p["filas"][0]["pt"] - p["filas"][1]["pt"]
    assert p["trasJornada"] == 3


def test_clasificacion_sin_previa():
    p = clasificacion.props(_datos("mad_2r", "B", 1), None)
    assert len(p["filas"]) == 12
    assert all(f["mov"] is None for f in p["filas"])


def test_movimientos():
    previa = [{"equipo": "A", "posicion": 1, "pj": 1}, {"equipo": "B", "posicion": 2, "pj": 1}]
    actual = [{"equipo": "B", "posicion": 1, "pj": 2}, {"equipo": "A", "posicion": 2, "pj": 2},
              {"equipo": "C", "posicion": 3, "pj": 1}]
    assert clasificacion.movimientos(actual, previa) == {"B": 1, "A": -1, "C": None}
    nada = {"B": None, "A": None, "C": None}
    # previa sin partidos jugados: el orden no significa nada
    assert clasificacion.movimientos(actual, [{**f, "pj": 0} for f in previa]) == nada
    # previa guardada tarde (ya con los partidos de esta jornada): no sirve para comparar
    assert clasificacion.movimientos(actual, [{**f, "pj": 2} for f in previa]) == nada


def test_previa_guardada_tarde():
    # j01 de dh_masc se guardó con 2 partidos jugados, como j02: sin flechas
    datos = _datos(j=2)
    p = clasificacion.props(datos, clasificacion.anterior(datos))
    assert all(f["mov"] is None for f in p["filas"])


def test_rankings():
    p = rankings.props(_datos())
    assert [b["clave"] for b in p["bloques"]] == ["anotadores", "ensayadores", "pateadores"]
    for b in p["bloques"]:
        assert 1 <= len(b["filas"]) <= rankings.TOP
        valores = [f["valor"] for f in b["filas"]]
        assert valores == sorted(valores, reverse=True) and valores[0] > 0
        assert b["filas"][0]["pos"] == 1 and all(f["apellidos"] and f["corto"] for f in b["filas"])
    # empatados comparten puesto
    ens = p["bloques"][1]["filas"]
    for a, b in zip(ens, ens[1:]):
        assert (a["pos"] == b["pos"]) == (a["valor"] == b["valor"])


def test_rankings_omite_bloques_vacios():
    datos = _datos()
    datos["rankings"] = {}
    assert [b["clave"] for b in rankings.bloques(datos)] == ["anotadores", "ensayadores"]
    datos["temporada_anotadores"] = datos["temporada_ensayadores"] = []
    with pytest.raises(RuntimeError):
        rankings.props(datos)


def test_dato_por_indice():
    datos = _datos()
    primero = dato.props(datos)["dato"]
    assert primero["titular"] == datos["datos_jornada"][0]["titular"] and primero["escudo"] == "data:x"
    tercero = dato.props(datos, indice=2)
    assert tercero["dato"]["titular"] == datos["datos_jornada"][2]["titular"] and tercero["total"] == 3
    assert dato.props(datos, indice=99)["dato"]["titular"] == tercero["dato"]["titular"]


def test_dato_sin_datos_usa_la_mayor_victoria():
    p = dato.props(_datos("cyl_masc", "unico", 1))
    assert p["total"] == 0 and p["dato"]["unidad"] == "puntos de diferencia"
    assert p["dato"]["valor"] == int(p["dato"]["numero"]) > 0


def test_partir_numero():
    assert dato.partir_numero("73'") == ("", 73, "'")
    assert dato.partir_numero("+31") == ("+", 31, "")
    assert dato.partir_numero("3/3") == ("3/3", None, "")
