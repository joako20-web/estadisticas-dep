import pytest

from datosdep import fichas as F
from datosdep import historico as H


def _eq(equipo, corto, abr, comp="dh_masc", categoria="nacional", club=None):
    return {"id": F._id("e", comp, "unico", equipo), "equipo": equipo, "corto": corto, "abr": abr,
            "liga": comp, "comp": comp, "grupo": "unico", "categoria": categoria, "region": "",
            "escudo": "", "club": club}


INDICE = [
    _eq("VRAC QUESOS ENTREPINARES", "VRAC Entrepinares", "VRAC", club=23),
    _eq("TERRITORIAL MASCULINO VRAC QUESOS ENTREPINARES", "VRAC Territorial", "VRA", "cyl_masc", "regional"),
    _eq("VULCANIZADOS ALVAREZ EL SALVADOR", "El Salvador", "SAL", club=21),
    _eq("C.R. EL SALVADOR DHB", "El Salvador B", "SAL", "dhb_masc"),
    _eq("INVERSUS LICEO FRANCES", "Liceo Francés", "LIC", club=28),
    _eq("INVERSUS LICEO FRANCÉS", "Liceo Francés", "LIC", "copa", "copa", club=28),
    _eq("HUESITOS LA VILA RUGBY CLUB", "La Vila", "VIL", club=80),
]


def test_norm():
    assert F.norm("  Liceo Francés-C.R. ") == "liceo frances c r"


def test_buscar_equipo_exacto_por_abreviatura():
    r = F.buscar_equipo("vrac", INDICE)
    assert [c["corto"] for c in r] == ["VRAC Entrepinares"]


def test_buscar_equipo_varios_candidatos():
    r = F.buscar_equipo("salvador", INDICE)
    assert {c["corto"] for c in r} == {"El Salvador", "El Salvador B"}


def test_buscar_equipo_sin_tildes_y_sin_duplicar_copa():
    r = F.buscar_equipo("liceo frances", INDICE)
    assert [c["comp"] for c in r] == ["dh_masc"]  # la de Copa (con tilde) no se repite


def test_buscar_equipo_errata_y_nada():
    assert F.buscar_equipo("la vla", INDICE)[0]["corto"] == "La Vila"
    assert F.buscar_equipo("xxxx", INDICE) == []


def test_buscar_jugador():
    indice = [
        {"id": "j:1", "nombre": "SANTIAGO IGNACIO MANSILLA", "equipo": "X", "liga": "", "comp": "dh_masc",
         "grupo": "unico", "categoria": "nacional", "puntos": 42},
        {"id": "j:2", "nombre": "ALBA GARCÍA GARCÍA", "equipo": "Y", "liga": "", "comp": "mad_fem1",
         "grupo": "unico", "categoria": "regional", "puntos": 30},
        {"id": "j:3", "nombre": "RICARD PEREZ GARCIA", "equipo": "Z", "liga": "", "comp": "dh_masc",
         "grupo": "unico", "categoria": "nacional", "puntos": 10},
    ]
    assert [c["id"] for c in F.buscar_jugador("mansilla", indice)] == ["j:1"]
    assert [c["id"] for c in F.buscar_jugador("garcia", indice)] == ["j:2", "j:3"]  # por puntos
    assert len(F._id("j", "dh_masc", "unico", "NOMBRE MUY LARGO DE VERDAD", "EQUIPO")) <= 12


@pytest.mark.parametrize("nombre, tipo", [
    ("DIVISIÓN DE HONOR MASCULINA", "dh_masc"),
    ("DIVISIÓN DE HONOR FEMENINA - LIGA IBERDROLA", "dh_fem"),
    ("Liga Iberdrola de Rugby", "dh_fem"),
    ("DIVISIÓN DE HONOR ÉLITE MASCULINA", "dh_elite"),
    ("DIVISIÓN DE HONOR B MASCULINO", "dhb_masc"),
    ("DIVISIÓN DE HONOR B FEMENINA", "dhb_fem"),
    ("COPA DEL REY", "copa"),
    ("COPA SM EL REY", "copa"),
    ("CN M23 KPMG EMERGING", "m23"),
    ("PROMOCIÓN DIVISIÓN DE HONOR MASCULINA", None),
    ("SUPERCOPA DE ESPAÑA MASCULINA", None),
    ("COPA DE LA REINA", None),
])
def test_tipo_competicion(nombre, tipo):
    assert H.tipo_competicion(nombre) == tipo


def test_campeones_por_club(monkeypatch):
    """El campeón histórico se muestra con el nombre actual de su club."""
    datos = {
        "temporada": "2025/26", "tipo": "dh_masc",
        "partidos": [
            {"ronda": "Semifinales", "pl": 30, "pv": 10, "local": "DH VRAC QUESOS ENTREPINARES", "visitante": "A", "fecha": "2026-05-24T12:00:00"},
            {"ronda": "Final", "pl": 25, "pv": 24, "local": "DH VRAC QUESOS ENTREPINARES", "visitante": "INEXO EL SALVADOR", "fecha": "2026-06-07T12:00:00"},
        ],
        "clubes": {"DH VRAC QUESOS ENTREPINARES": 23, "INEXO EL SALVADOR": 21},
        "escudos": {},
    }
    monkeypatch.setattr(H, "datos_temporada", lambda temp, tipo: datos if temp == 2526 else None)
    monkeypatch.setattr("datosdep.historico.indice_equipos", lambda: INDICE)
    r = H.campeones("dh_masc")
    assert len(r) == 1
    assert (r[0]["campeon"], r[0]["subcampeon"], r[0]["marcador"]) == (
        "VRAC QUESOS ENTREPINARES", "VULCANIZADOS ALVAREZ EL SALVADOR", "25-24")
