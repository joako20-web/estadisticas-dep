import json

from datosdep import sonido
from datosdep.videos import base, jornada
from datosdep.pipeline import ruta_jornada


def test_props_jornada(monkeypatch):
    monkeypatch.setattr(base.R, "escudo_equipo", lambda equipo, escudos: "data:x")
    datos = json.loads(ruta_jornada("dh_masc", "unico", 2).read_text(encoding="utf-8"))
    p = jornada.props(datos)
    assert p["jornada"] == 2 and len(p["partidos"]) == 5
    assert p["partidos"][0]["local"]["gana"] != p["partidos"][0]["visitante"]["gana"]
    assert p["mvp"]["apellidos"] and p["mvp"]["puntos"] > 0
    assert [f["pos"] for f in p["top"]] == [1, 2, 3, 4]
    assert p["trasJornada"] == 2
    assert p["tema"]["acento"].startswith("#")


def test_sonidos(tmp_path):
    rutas = sonido.generar(tmp_path)
    assert {r.stem for r in rutas} == set(sonido.EFECTOS)
    assert all(r.stat().st_size > 1000 for r in rutas)
