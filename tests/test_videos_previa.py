import json

import pytest

from datosdep import carteles
from datosdep.pipeline import ruta_jornada
from datosdep.render import render as R
from datosdep.videos import PLANTILLAS, base, previa


def _datos(comp="dh_masc", grupo="unico", jornada=2):
    return json.loads(ruta_jornada(comp, grupo, jornada).read_text(encoding="utf-8"))


@pytest.fixture
def sin_red(monkeypatch):
    monkeypatch.setattr(base.R, "escudo_equipo", lambda equipo, escudos: "data:x")


def test_cuando():
    assert previa.cuando("2026-10-10T16:00:00") == {"dia": "SÁB", "hora": "16:00", "fecha": "10 OCT"}
    assert previa.cuando("2026-10-14T00:00:00") == {"dia": "MIÉ", "hora": "", "fecha": "14 OCT"}
    assert previa.cuando(None) == {"dia": "", "hora": "", "fecha": ""}
    assert previa.campo("CAMPOS DE RUGBY DE PEPE ROJO (INSTALACIONES)") == "Campos de Rugby de Pepe Rojo"


def test_props_previa(sin_red):
    p = previa.props(_datos())
    assert p["jornada"] == 3 and p["total"] == 5 and len(p["partidos"]) == 5
    d = p["destacado"]
    assert (d["local"]["pos"], d["visitante"]["pos"]) == (1, 2)  # VRAC (1º) - Aparejadores (2º)
    assert d["dia"] == "DOM" and d["hora"] == "12:00" and d["campo"] == "Campos de Rugby de Pepe Rojo"
    assert sum(x["destacado"] for x in p["partidos"]) == 1
    fechas = [(x["fecha"], x["hora"]) for x in p["partidos"]]
    assert fechas[0] == ("10 OCT", "16:00") and fechas[-1][0] == "11 OCT"  # orden cronológico
    assert p["partidos"][0]["local"]["escudo"] == "data:x"
    assert "previa" in PLANTILLAS and PLANTILLAS["previa"].composicion == "ReelPrevia"


def test_previa_maximo_incluye_destacado(sin_red, monkeypatch):
    monkeypatch.setattr(previa, "MAX_PARTIDOS", 2)
    p = previa.props(_datos())
    assert len(p["partidos"]) == 2 and p["total"] == 5
    assert any(x["destacado"] for x in p["partidos"])


def test_previa_sin_proxima_jornada(sin_red):
    datos = _datos()
    datos["proxima_jornada"] = None
    with pytest.raises(RuntimeError, match="próxima jornada"):
        previa.props(datos)


def test_slide_matchday():
    datos = _datos()
    s = carteles.slide_matchday(datos)  # sin id: el destacado
    assert s["id"] == 17654 and s["numero"] == 3
    assert s["dia"] == "Domingo 11 de octubre" and s["hora"] == "12:00"
    assert [l["posicion"] for l in s["lados"]] == [1, 2]
    s = carteles.slide_matchday(datos, 17657)
    assert s["lados"][0]["equipo"] == "UNIO ESPORTIVA SANTBOIANA" and s["dia"].startswith("Sábado")
    with pytest.raises(RuntimeError):
        carteles.slide_matchday(datos, 1)


def test_html_matchday(monkeypatch):
    monkeypatch.setattr(R, "escudo_equipo", lambda equipo, escudos: "data:x")
    datos = _datos()
    s = carteles.slide_matchday(datos)
    cab = {**datos, "jornada": s["numero"]}
    for formato in ("post", "historia"):
        for tema in R.TEMAS:
            html = R.html_post(cab, [s], formato, tema)
            assert "Matchday" in html and "12:00" in html and "Campos de Rugby de Pepe Rojo" in html
            assert f"tema-{tema}" in html and f"f-{formato}" in html


def test_cabecera_proxima_jornada(monkeypatch):
    # El slide "Próxima jornada" va en el carrusel de la última jugada, pero su cabecera
    # debe decir la jornada que anuncia (antes ponía "jornada 2" arriba y "Jornada 3" abajo).
    monkeypatch.setattr(R, "escudo_equipo", lambda equipo, escudos: "data:x")
    datos = _datos()
    s = next(x for x in R.slides_de_jornada(datos) if x["tipo"] == "previa")
    for formato in ("post", "historia"):
        for tema in R.TEMAS:
            html = R.html_post(datos, [s], formato, tema)
            assert f"jornada {s['numero']}" in html and f"jornada {datos['jornada']}<" not in html
