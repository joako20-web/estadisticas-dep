"""API de la web nueva del origen A: traducción a los modelos del bot (con respuestas reales) y manejo de la clave."""
import json
import time
from pathlib import Path

import pytest
import requests

from datosdep.scraper import api, origen_a

FIX = Path(__file__).parent / "fixtures"
RAIZ = Path(__file__).resolve().parents[1]


def _json(nombre):
    return json.loads((FIX / nombre).read_text(encoding="utf-8"))


# ---------- traducción de respuestas ----------

def test_clasificacion_igual_que_la_guardada_de_la_j6():
    """La tabla que sale de la API debe coincidir con la que el bot guardó en su día de la web antigua."""
    equipos = api.equipos_de_torneo(_json("api_torneo.json"))
    nueva = api.filas_clasificacion(_json("api_clasificacion.json"), equipos)
    guardada = json.loads((RAIZ / "data/2026-27/dh_masc/unico/j06.json").read_text(encoding="utf-8"))["clasificacion"]
    campos = ("posicion", "equipo", "pt", "pj", "pg", "pe", "pp", "tf", "tc", "dt", "ef", "ec", "de", "bo", "bd", "escudo")
    assert [{k: getattr(f, k) for k in campos} for f in nueva] == [{k: f[k] for k in campos} for f in guardada]
    assert [f.racha for f in nueva] == [f["racha"] for f in guardada]


def test_partidos_igual_que_los_guardados_de_la_temporada():
    nuevos = {p.id: p for p in api.partidos_de_torneo(_json("api_torneo.json"))}
    guardados = json.loads((RAIZ / "data/2026-27/dh_masc/unico/j06.json").read_text(encoding="utf-8"))["partidos_temporada"]
    assert len(nuevos) == 90
    jugados = [g for g in guardados if g["estado"] == "jugado"]
    assert len(jugados) == 30
    for g in jugados:
        n = nuevos[g["id"]]
        assert (n.jornada, n.local, n.visitante, n.puntos_local, n.puntos_visitante, n.estado) == (
            g["jornada"], g["local"], g["visitante"], g["puntos_local"], g["puntos_visitante"], "jugado")
        assert n.fecha.isoformat() == g["fecha"] and n.jugado and n.grupo is None


def test_orden_de_los_partidos_como_la_web_antigua():
    nuevos = api.partidos_de_torneo(_json("api_torneo.json"))
    guardados = json.loads((RAIZ / "data/2026-27/dh_masc/unico/j06.json").read_text(encoding="utf-8"))["partidos_temporada"]
    assert [p.id for p in nuevos if p.estado == "jugado"] == [g["id"] for g in guardados]  # por jornada, hora y orden


def test_partido_pendiente_y_ultima_jornada():
    t = _json("api_torneo.json")
    pendiente = next(p for p in api.partidos_de_torneo(t) if p.estado == "pendiente")
    assert not pendiente.jugado and pendiente.puntos_local is None
    assert api.ultima_jornada_jugada(t) == 6


def test_arbitro_es_el_principal_no_los_asistentes():
    p = _json("api_previo.json")
    assert [a["rol"] for a in p["arbitros"]][:3] == ["ARBITRO", "ARBITRO ASISTENTE", "ARBITRO ASISTENTE"]
    assert api.arbitro_de_previo(p) == "JENNY LEE"
    assert api.arbitro_de_previo({"arbitros": []}) is None and api.arbitro_de_previo({}) is None


def test_fecha_sin_hora_y_eliminatoria_como_ronda():
    t = {"partidos": [{"id": 1, "j": 1, "torneo": 5, "fecha": "2027-04-18", "estado": "Pendiente", "fase": "FASE FINAL",
                       "grupo": "CUARTOS DE FINAL", "gl": None, "gv": None, "l": {"id": 1, "n": "A", "e": ""},
                       "v": {"id": 2, "n": "B", "e": ""}}]}
    p = api.partidos_de_torneo(t)[0]
    assert (p.fecha.hour, p.ronda, p.jornada) == (0, "CUARTOS DE FINAL", 0)


# ---------- cliente: clave temporal, caducidad y bloqueos ----------

class _R:
    def __init__(self, status=200, texto="", json_=None, headers=None):
        self.status_code, self.headers = status, headers or {}
        self.text = texto if json_ is None else json.dumps(json_)
        self.content = self.text.encode()

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(str(self.status_code))


def _pagina(caduca):
    return _R(texto=f'<html><meta name="client-token" content="{int(caduca)}.abc.def.ghi"><body></body></html>')


class _Sesion:
    headers: dict = {}

    def __init__(self, caduca=None, respuestas=None):
        self.caduca = caduca if caduca is not None else time.time() + 43200
        self.respuestas = list(respuestas or [])
        self.paginas = 0
        self.posts = []

    def get(self, url, **k):
        self.paginas += 1
        return _pagina(self.caduca)

    def post(self, url, data=None, headers=None, **k):
        self.posts.append((data, headers))
        return self.respuestas.pop(0) if self.respuestas else _R(json_={"ok": 1})


@pytest.fixture
def cliente(tmp_path, monkeypatch):
    monkeypatch.setattr(origen_a, "BASE", "https://origen-a.invalid")
    monkeypatch.setattr(origen_a.time, "sleep", lambda s: None)

    def nuevo(**kw):
        c = origen_a.OrigenA(cache_dir=tmp_path)
        c.sesion = _Sesion(**kw)
        return c
    return nuevo


def test_la_clave_se_pide_una_vez_y_se_reutiliza(cliente):
    c = cliente()
    c._api("torneo", id=1)
    c._api("clasificacion", se=0, id=1, j=1)
    assert c.sesion.paginas == 1
    assert c.sesion.posts[0][1]["X-Client-Token"].endswith(".abc.def.ghi") and c.sesion.posts[0][0] == {"tipo": "torneo", "id": 1}


def test_la_clave_a_punto_de_caducar_se_renueva(cliente):
    c = cliente(caduca=time.time() + 600)  # le quedan 10 min: menos de 30
    c._api("torneo", id=1)
    c._api("torneo", id=2)
    assert c.sesion.paginas == 2


def test_clave_caducada_se_renueva_y_se_reintenta_una_vez(cliente):
    c = cliente(respuestas=[_R(403, json_={"code": "CLIENT_TOKEN_EXPIRED"}), _R(json_={"ok": 1})])
    assert c._api("torneo", id=1) == {"ok": 1}
    assert c.sesion.paginas == 2 and len(c.sesion.posts) == 2


def test_429_bloquea_la_api_y_sirve_lo_ultimo_guardado(cliente):
    c = cliente(respuestas=[_R(json_={"v": 1}), _R(429)])
    assert c._api("clasificacion", cachear=False, se=0, id=1, j=1) == {"v": 1}
    c._memoria.clear()
    assert c._api("clasificacion", cachear=False, se=0, id=1, j=1) == {"v": 1}  # bloqueada: el último dato guardado
    assert c.bloqueado_ahora()
    with pytest.raises(origen_a.AccesoRestringido):
        c._api("torneo", id=9)  # otra consulta sin dato guardado: no se insiste
    assert len(c.sesion.posts) == 2


def test_respuesta_que_no_es_json_no_se_guarda(cliente, tmp_path):
    c = cliente(respuestas=[_R(texto="<html>nada</html>")])
    with pytest.raises(ValueError):
        c._api("torneo", id=1)
    assert not list(tmp_path.glob("*.gz"))


def test_pagina_sin_clave_es_web_cambiada(cliente):
    c = cliente()
    c.sesion.get = lambda url, **k: _R(texto="<html>sin meta</html>")
    with pytest.raises(origen_a.FuenteCambiada):
        c._api("torneo", id=1)


def test_competicion_clasificacion_y_arbitro_con_respuestas_reales(cliente):
    c = cliente(respuestas=[_R(json_=_json("api_torneo.json")), _R(json_=_json("api_clasificacion.json")),
                            _R(json_=_json("api_previo.json"))])
    comp = c.competicion(1296)
    assert len(comp.partidos) == 90 and comp.jugadores == []  # la tabla de jugadores la calcula el bot con las actas
    tabla = c.clasificacion(1296)  # usa la última jornada jugada (6) y los nombres del torneo
    assert tabla[0].equipo.startswith("RECOLETAS") and c.sesion.posts[1][0] == {"tipo": "clasificacion", "se": 0, "id": 1296, "j": 6}
    assert c.arbitro(17669) == "JENNY LEE" and c.previo_en_cache(17669)


# ---------- fase 2: temporadas, jugadores con id e histórico ----------

def test_competiciones_y_grupos_de_una_temporada_pasada(cliente):
    c = cliente(respuestas=[_R(json_=_json("api_selectores.json")), _R(json_=_json("api_selectores.json"))])
    comps = c.competiciones_de(2526)
    assert (316, "DIVISIÓN DE HONOR MASCULINA") in comps and len(comps) == 43
    grupos = c.torneos_de(2526, 316)
    assert {"id": 1070, "nombre": "CUARTOS DE FINAL", "fase": "FASE FINAL"} in grupos and len(grupos) == 4
    assert c.sesion.posts[1][0]["comp"] == 316 and c.sesion.posts[0][0]["temp"] == 2526


def test_jugadores_con_id_de_la_competicion_del_grupo(cliente):
    c = cliente(respuestas=[_R(json_=_json("api_torneo.json")), _R(json_=_json("api_comparar_candidatos.json"))])
    jugadores = c.jugadores_con_id(1296)
    mansilla = next(j for j in jugadores if j.id == 1027011)
    assert mansilla.nombre == "SANTIAGO IGNACIO MANSILLA" and mansilla.pj == 6 and mansilla.equipo.startswith("RECOLETAS")
    assert c.sesion.posts[1][0] == {"tipo": "comparar_candidatos", "comp": 416, "s": 1}  # la competición sale del torneo


class _ClienteHistorico:
    """Respuestas reales de la API en lugar de la red."""

    def competiciones_de(self, id_temp):
        return [(c["id"], c["nombre"]) for c in _json("api_selectores.json")["competiciones"]]

    def torneos_de(self, id_temp, id_comp):
        return [{"id": 1296, "nombre": "1ª FASE", "fase": "LIGA REGULAR"}]

    def torneo(self, id_grupo, cachear=False):
        return _json("api_torneo.json")

    def candidatos(self, id_comp, cachear=False):
        return _json("api_comparar_candidatos.json")

    def goleadores(self, id_grupo, id_comp, cachear=False):
        return _json("api_goleadores.json")


def test_datos_temporada_pasada_con_la_api(tmp_path, monkeypatch):
    from datosdep import historico

    monkeypatch.setattr(historico, "HISTORICO", tmp_path)
    monkeypatch.setattr(historico, "_cliente", lambda: _ClienteHistorico())
    d = historico.datos_temporada(2526, "dh_masc")
    assert d["tipo"] == "dh_masc" and d["temporada"] == "2025/26" and len(d["partidos"]) == 90
    assert d["grupos"] == [{"id": 1296, "nombre": "1ª FASE", "fase": "LIGA REGULAR"}]
    mansilla = d["jugadores"]["1027011"][0]
    assert mansilla[2:] == [6, 101, None, None, None]  # partidos y puntos sí; ensayos y tarjetas no se publican
    assert all(club for club in d["clubes"].values()) and (tmp_path / "2526_dh_masc.json").exists()
    assert historico.datos_temporada(2526, "dh_masc") == d  # la segunda vez sale del fichero, sin pedir nada


def test_carrera_con_datos_desconocidos_no_inventa_ceros(tmp_path, monkeypatch):
    from datosdep import fichas, historico

    monkeypatch.setattr(historico, "HISTORICO", tmp_path)
    monkeypatch.setattr(historico, "completar", lambda tipo: None)
    (tmp_path / "2526_dh_masc.json").write_text(json.dumps({"id_temp": 2526, "temporada": "2025/26", "tipo": "dh_masc", "clubes": {},
        "jugadores": {"7": [["ANA", "X", 10, 100, None, None, None]]}}), encoding="utf-8")
    filas = historico.carrera(7)
    assert filas[0]["ensayos"] is None and filas[0]["tarjetas"] is None and filas[0]["puntos"] == 100
    d = {"id_fuente": 7, "comp": "dh_masc", "liga": "DH", "equipo": "X", "partidos": 5, "puntos": 50, "ensayos": 3,
         "amarillas": 1, "rojas": 0}
    monkeypatch.setattr(historico, "_actuales", lambda comp: {})
    _, total = fichas.carrera_jugador(d)
    assert (total["pj"], total["puntos"]) == (15, 150) and total["ensayos"] is None and total["tarjetas"] is None


def test_ranking_sin_ensayos_cuando_alguna_temporada_no_los_publica(tmp_path, monkeypatch):
    from datosdep import fichas, historico

    monkeypatch.setattr(historico, "HISTORICO", tmp_path)
    monkeypatch.setattr(historico, "completar", lambda tipo: None)
    (tmp_path / "2526_dh_masc.json").write_text(json.dumps({"id_temp": 2526, "jugadores": {
        "1": [["A", "X", 10, 100, None, None, None]], "2": [["B", "X", 10, 50, None, None, None]]}}), encoding="utf-8")
    r = fichas._ranking_historico("dh_masc", [], 1)
    assert r["puesto_puntos"] == 1 and r["puesto_ensayos"] is None


def test_actuales_con_id_une_por_nombre_y_equipo():
    from datosdep import fichas
    from datosdep.scraper.parsers import JugadorTemporada as J

    tabla = [J(None, "ANA PEREZ", "EQ A", 5, 30, 2, 0, 0), J(None, "SIN ID", "EQ A", 1, 0, 0, 0, 0)]
    con_id = [J(9, "ANA PEREZ", "EQ A", 5, 0, 0, 0, 0)]
    r = fichas._actuales_con_id(tabla, con_id)
    assert [(j.id, j.nombre, j.puntos) for j in r] == [(9, "ANA PEREZ", 30)]


def test_acta_con_el_nombre_del_equipo_en_otro_orden_usa_el_de_la_competicion(cliente):
    from datosdep.models import Acta, Evento

    c = cliente()
    c._equipos[1] = {5: ("RECOLETAS SALUD BURGOS CAJA RURAL APAREJADORES", "")}
    acta = Acta(1, "RECOLETAS SALUD CAJA RURAL BURGOS APAREJADORES", "OTRO", [Evento(1, "ensayo", "x", None, "RECOLETAS SALUD CAJA RURAL BURGOS APAREJADORES", "J")], [], [])
    r = c._unificar_nombres(acta)
    assert r.local == "RECOLETAS SALUD BURGOS CAJA RURAL APAREJADORES" and r.visitante == "OTRO"
    assert r.eventos[0].equipo == "RECOLETAS SALUD BURGOS CAJA RURAL APAREJADORES"
