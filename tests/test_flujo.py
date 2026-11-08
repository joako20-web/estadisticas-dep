from dataclasses import asdict
from pathlib import Path

import pytest

from datosdep import caption
from datosdep.core import estadisticas as E
from datosdep.core.editar import cambiar_xv
from datosdep.scraper import parsers as P

FX = Path(__file__).parent / "fixtures"


@pytest.fixture
def datos():
    comp = P.estadisticas((FX / "estadisticas.html").read_bytes())
    lineas = []
    for p in comp.jornada(2):
        a = P.acta((FX / f"acta_{p.id}.html").read_bytes(), p.id)
        lineas += E.lineas_partido(p, a)
    return {
        "competicion": "dh_masc",
        "nombre": "División de Honor",
        "grupo": "unico",
        "jornada": 2,
        "partidos": [asdict(p) | {"fecha": p.fecha.isoformat()} for p in comp.jornada(2)],
        "anotadores": [asdict(x) for x in E.anotadores(lineas)],
        "xv_ideal": {str(d): asdict(ln) for d, ln in E.xv_ideal(lineas).items()},
        "candidatos_xv": [asdict(ln) for ln in lineas if 1 <= ln.dorsal <= 15],
        "clasificacion": [asdict(f) for f in P.clasificacion((FX / "clasificacion.html").read_bytes())],
    }


def test_cambiar_xv_por_apellido(datos):
    msg = cambiar_xv(datos, "9 sirvent")  # jugó de 10, aviso de fuera de posición
    assert datos["xv_ideal"]["9"]["nombre"] == "MARCEL SIRVENT SANSO"
    assert "jugó de 10" in msg
    assert datos["xv_editado"]


def test_cambiar_xv_con_tilde_y_en_posicion(datos):
    cambiar_xv(datos, "9 Albert Millan")
    assert datos["xv_ideal"]["9"]["nombre"] == "ALBERT MILLAN DIAZ"


def test_cambiar_xv_errores(datos):
    with pytest.raises(ValueError, match="dorsal"):
        cambiar_xv(datos, "Araña")
    with pytest.raises(ValueError, match="No encuentro"):
        cambiar_xv(datos, "9 Zzzz")
    with pytest.raises(ValueError, match="varios"):
        cambiar_xv(datos, "1 a")  # demasiado genérico


def test_texto_post(datos):
    t = caption.texto_post(datos)
    assert t.startswith("🏉 División de Honor · Jornada 2")
    assert "La Vila 36-33 Santboiana" in t
    assert "Líder: VRAC Entrepinares con 9 puntos" in t
    assert "#DivisionDeHonor" in t and "#rugby" in t
