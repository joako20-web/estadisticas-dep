"""MVP elegido por la afición (votación de la red) y porcentajes en la tarjeta."""
import json
import shutil

import pytest

from datosdep import carteles_mvp as C, especiales, flujo, pipeline
from conftest import DATOS_TEST
from datosdep.render import render as R
from datosdep.videos import mvp


@pytest.fixture
def datos_tmp(tmp_path, monkeypatch):
    shutil.copytree(DATOS_TEST, tmp_path / "data")
    monkeypatch.setattr(pipeline, "DATA", tmp_path / "data")
    monkeypatch.setattr(R, "escudo_equipo", lambda equipo, escudos: "data:x")
    monkeypatch.setattr(mvp.base.R, "escudo_equipo", lambda equipo, escudos: "data:x")
    monkeypatch.setattr(mvp.base, "foto_jugador", lambda url: "")
    return pipeline.ruta_jornada("dh_masc", "unico", 3)


def _leer(ruta):
    return json.loads(ruta.read_text(encoding="utf-8"))


def test_leer_porcentajes():
    assert C.leer_porcentajes("48 24 19 9", 4) == [48, 24, 19, 9]
    assert C.leer_porcentajes("48% / 24% / 19%", 4) == [48, 24, 19, 9]  # el último se completa
    assert C.leer_porcentajes("33,33,33", 3) == [33, 33, 33]  # redondeo de la red
    with pytest.raises(ValueError, match="Necesito 4"):
        C.leer_porcentajes("50 50", 4)
    with pytest.raises(ValueError, match="Suman"):
        C.leer_porcentajes("50 50 50 50", 4)


def test_tarjeta_con_ganador_y_votos(datos_tmp):
    datos = _leer(datos_tmp)
    por_nota = C.slide_mvp(datos)
    assert not por_nota["aficion"] and not por_nota["votos"]
    cands = especiales.candidatos_mvp(datos)
    ganador = cands[2]["nombre"]
    C.guardar_votacion(datos, ganador, dict(zip([c["nombre"] for c in cands], [24, 19, 48, 9])))
    s = C.slide_mvp(datos)
    assert s["aficion"] and s["j"]["motivo"] == "Elegido por la afición"
    assert s["j"]["apellidos"].upper() in ganador
    assert [v["pct"] for v in s["votos"]] == [48, 24, 19, 9] and s["votos"][0]["gana"]
    html = R.html_post(datos, [s], "post", "tele")
    assert "MVP de la afición" in html and "48%" in html
    C.guardar_votacion(datos, None)
    assert "mvp_votacion" not in datos and not C.slide_mvp(datos)["aficion"]


class TgFalso:
    def __init__(self):
        self.mensajes = []

    def mensaje(self, chat, texto, botones=None, **_):
        self.mensajes.append((texto, botones))

    def album(self, chat, imagenes, como_archivo=False):
        self.mensajes.append(("album", len(imagenes)))


def test_flujo_votacion(datos_tmp, monkeypatch):
    enviados = []
    monkeypatch.setattr(flujo, "enviar_especial", lambda tg, chat, clave, comp, grupo, jornada=None, **k:
                        enviados.append((clave, comp, grupo, jornada)) or True)
    tg, b = TgFalso(), {"chat_id": 1, "esperando": None}
    flujo._boton_votacion(tg, b, ["ym", "dh_masc/unico", "3"])
    texto, filas = tg.mensajes[-1]
    assert "¿Quién ganó" in texto and filas[-1][0][1] == "yw|dh_masc/unico|3|x"
    flujo._boton_votacion(tg, b, ["yw", "dh_masc/unico", "3", "1"])
    assert _leer(datos_tmp)["mvp_votacion"]["ganador"] == especiales.candidatos_mvp(_leer(datos_tmp))[1]["nombre"]
    flujo._boton_votacion(tg, b, ["yq", "dh_masc/unico", "3"])
    assert b["esperando"]["accion"] == "mvp_pct"
    flujo._porcentajes_mvp(tg, b, "esto no son porcentajes")
    assert b["esperando"] and "🤔" in tg.mensajes[-1][0]
    flujo._porcentajes_mvp(tg, b, "24 48 19 9")
    assert b["esperando"] is None and enviados[-1] == ("mvp_jornada", "dh_masc", "unico", 3)
    votos = _leer(datos_tmp)["mvp_votacion"]["votos"]
    assert sorted(votos.values()) == [9, 19, 24, 48]
    flujo._boton_votacion(tg, b, ["yw", "dh_masc/unico", "3", "x"])
    assert "mvp_votacion" not in _leer(datos_tmp)


def test_regenerar_jornada_conserva_votacion():
    # preparar_jornada copia mvp_votacion del JSON previo (igual que el XV editado)
    import inspect

    assert 'previo.get("mvp_votacion")' in inspect.getsource(pipeline.preparar_jornada)
