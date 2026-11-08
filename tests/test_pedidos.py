import pytest

from datosdep.pedidos import interpretar


@pytest.mark.parametrize(
    "texto, ligas, claves, jornada",
    [
        ("quiero el xv de dhb", [("dhb_masc", g) for g in "ABCD"], ["xv"], None),
        ("XV DHB grupo c", [("dhb_masc", "C")], ["xv"], None),
        ("clasificación de la Élite", [("dh_elite", "unico")], ["clasificacion"], None),
        ("resultados dh jornada 1", [("dh_masc", "unico")], ["resultados"], 1),
        ("anotadores de la temporada liga iberdrola", [("dh_fem", "unico")], ["temporada"], None),
        ("máximos anotadores DH", [("dh_masc", "unico")], ["anotadores"], None),
        ("previa división de honor", [("dh_masc", "unico")], ["previa"], None),
        ("todo dhb femenina", [("dhb_fem", "unico")], None, None),
        ("dh", [("dh_masc", "unico")], None, None),
        ("xv y clasificacion dh j2", [("dh_masc", "unico")], ["xv", "clasificacion"], 2),
    ],
)
def test_interpretar(texto, ligas, claves, jornada):
    p = interpretar(texto)
    assert p.ligas == ligas
    assert p.claves == claves
    assert p.jornada == jornada


def test_sin_liga():
    assert interpretar("hola qué tal") is None


def test_copa_y_cuadro():
    p = interpretar("cuadro de la copa")
    assert p.ligas[0][0] == "copa" and len(p.ligas) == 6 and p.claves == ["cuadro"]
    p = interpretar("todos los grupos dhb")
    assert p.claves == ["grupos"]
