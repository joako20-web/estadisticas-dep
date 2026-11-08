"""Jornadas con descanso (OrigenB las publica como un partido contra «DESCANSO»)."""
import copy
import json

import pytest

from datosdep import caption, especiales
from datosdep.pipeline import es_descanso, ruta_jornada, separar_descansos
from datosdep.render import render as R
from datosdep.videos import base, previa


def _bye(local, visitante, jornada):
    return {"id": 999, "jornada": jornada, "fecha": None, "local": local, "visitante": visitante,
            "puntos_local": None, "puntos_visitante": None, "campo": "", "estado": "pendiente",
            "grupo": None, "ronda": ""}


@pytest.fixture
def datos(monkeypatch):
    monkeypatch.setattr(R, "escudo_equipo", lambda equipo, escudos: "data:x")
    monkeypatch.setattr(base.R, "escudo_equipo", lambda equipo, escudos: "data:x")
    d = copy.deepcopy(json.loads(ruta_jornada("dh_masc", "unico", 2).read_text(encoding="utf-8")))
    # datos guardados con el formato antiguo: el descanso como partido
    d["partidos"].append(_bye("TORRELODONES RC", "DESCANSO", d["jornada"]))
    d["proxima_jornada"]["partidos"].append(_bye("DESCANSO", "SANSE SCRUM", d["jornada"] + 1))
    return d


def test_separar_descansos():
    ps = [_bye("A", "B", 1), _bye("TORRELODONES RC", "DESCANSO", 1), _bye("DESCANSO", "SANSE SCRUM", 1)]
    reales, descansan = separar_descansos(ps)
    assert [p["local"] for p in reales] == ["A"] and descansan == ["TORRELODONES RC", "SANSE SCRUM"]
    assert es_descanso(ps[1]) and not es_descanso(ps[0])


def test_carrusel_sin_partido_contra_descanso(datos):
    slides = {s["tipo"]: s for s in R.slides_de_jornada(datos)}
    for tipo, equipo in (("resultados", "TORRELODONES RC"), ("previa", "SANSE SCRUM")):
        s = slides[tipo]
        assert not any(es_descanso(p) for p in s["partidos"]) and s["descansa"] == [equipo]
        html = R.html_post(datos, [s], "post", "tele")
        assert "Descansa:" in html and ">DESCANSO<" not in html.upper().replace(" ", "")


def test_caption_y_encuesta(datos):
    texto = caption.texto_post(datos)
    assert "Descansa: " in texto and "DESCANSO" not in texto
    assert not es_descanso(especiales.partido_destacado(datos))


def test_video_previa_sin_descanso_y_destacado_forzado(datos):
    p = previa.props(datos)
    assert len(p["partidos"]) == p["total"] == 5  # el descanso no cuenta
    otro = next(x for x in datos["proxima_jornada"]["partidos"]
                if x["id"] != p["idDestacado"] and not es_descanso(x))
    q = previa.props(datos, id_destacado=otro["id"])
    assert q["idDestacado"] == otro["id"]
    assert sum(x["destacado"] for x in q["partidos"]) == 1


def test_nombre_corto_con_san():
    from datosdep.render.nombres import equipo_corto

    assert equipo_corto("SAN ISIDRO FUENCARRAL") == "San Isidro"
    assert equipo_corto("CLUB DE RUGBY SANT CUGAT") == "Sant Cugat"
    assert equipo_corto("VULCANIZADOS ALVAREZ EL SALVADOR") == "El Salvador"
