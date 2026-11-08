import json

import pytest

from datosdep import carteles_mvp
from datosdep.pipeline import ruta_jornada
from datosdep.videos import PLANTILLAS, base, mvp, xv


@pytest.fixture(autouse=True)
def sin_red(monkeypatch):
    monkeypatch.setattr(base.R, "escudo_equipo", lambda equipo, escudos: f"data:{equipo}")
    monkeypatch.setattr(base, "foto_jugador", lambda url, *a, **k: "data:foto" if url else "")


def _datos(comp="dh_masc", grupo="unico", j=2):
    return json.loads(ruta_jornada(comp, grupo, j).read_text(encoding="utf-8"))


def test_registradas():
    assert PLANTILLAS["xv"].composicion == "ReelXV"
    assert PLANTILLAS["mvp"].composicion == "ReelMvp"


def test_props_xv():
    p = xv.props(_datos())
    assert [len(l["jugadores"]) for l in p["lineas"]] == [3, 2, 3, 2, 2, 3]
    puestos = sorted(j["puesto"] for l in p["lineas"] for j in l["jugadores"])
    assert puestos == list(range(1, 16))
    mejores = [j for l in p["lineas"] for j in l["jugadores"] if j["mejor"]]
    assert len(mejores) == 1 and mejores[0]["puesto"] == p["mejor"]["puesto"]
    assert p["mejor"]["foto"] == ""  # el reel del XV no usa foto
    assert all(j["apellido"] and j["escudo"].startswith("data:") for l in p["lineas"] for j in l["jugadores"])


def test_xv_sin_xv_ideal():
    datos = _datos()
    datos["xv_ideal"] = None
    with pytest.raises(RuntimeError, match="XV ideal"):
        xv.props(datos)


def test_xv_liga_sin_xv_en_config(monkeypatch):
    monkeypatch.setattr("datosdep.videos.base.datos_jornada", lambda *a: pytest.fail("no debería cargar datos"))
    with pytest.raises(RuntimeError, match="no tiene XV ideal"):
        PLANTILLAS["xv"].construir("copa", "A", 1)


def test_ficha_mvp_partido_y_stats():
    datos = _datos()
    f = mvp.ficha(datos)
    mejor = max(datos["xv_ideal"].values(), key=lambda x: x["nota"])
    assert f["puntos"] == mejor["puntos"] and f["apellidos"]
    assert f["foto"] == "data:foto"
    assert [s["clave"] for s in f["stats"]][:3] == ["ensayos", "conversiones", "golpes"]
    p = f["partido"]
    assert p["propios"] is not None and p["letra"] in "GEP" and p["texto"]
    assert (p["propios"] > p["contra"]) == (p["letra"] == "G")
    assert p["escudoRival"] == f"data:{p['rivalOficial']}"


def test_ficha_sin_foto_y_sin_xv():
    datos = _datos()
    datos["xv_ideal"] = None  # tira del máximo anotador
    for a in datos["anotadores"]:
        a["foto"] = ""
    f = mvp.ficha(datos)
    assert f["foto"] == "" and f["puesto"] is None and f["motivo"] == "Máximo anotador"


def test_ficha_sin_jugadores():
    datos = _datos()
    datos["xv_ideal"], datos["anotadores"] = None, []
    with pytest.raises(RuntimeError):
        mvp.ficha(datos)


def test_props_mvp():
    p = mvp.props(_datos("dh_fem", "unico", 1))
    assert p["jugador"]["nombre"] and p["tema"]["acento"].startswith("#")


def test_cartel_mvp(monkeypatch, tmp_path):
    datos = _datos()
    llamadas = {}

    def falso(d, slides, destino, formato, tema):
        llamadas.update(d=d, slides=slides, formato=formato, tema=tema)
        return [destino / "01_mvp.jpg"]

    monkeypatch.setattr(carteles_mvp, "datos_jornada", lambda comp, grupo, j: datos)
    monkeypatch.setattr(carteles_mvp, "renderizar_slides", falso)
    rutas = carteles_mvp.renderizar_mvp("dh_masc", "unico", tmp_path, 2, "historia", "brutal")
    assert rutas == [tmp_path / "01_mvp.jpg"]
    [s] = llamadas["slides"]
    assert s["tipo"] == "mvp" and s["j"]["foto"] == "data:foto" and s["jornada_n"] == 2
    assert llamadas["formato"] == "historia" and llamadas["tema"] == "brutal"


def test_plantilla_mvp_html(monkeypatch):
    """La plantilla Jinja pinta nombre, stats y resultado (sin abrir navegador)."""
    from datosdep.render import render as R

    datos = _datos()
    html = R.html_post(datos, [carteles_mvp.slide_mvp(datos)], "post", "tele")
    f = mvp.ficha(datos)
    assert f["apellidos"] in html and "Jugador de la jornada" in html
    assert f"{f['partido']['propios']}-{f['partido']['contra']}" in html
