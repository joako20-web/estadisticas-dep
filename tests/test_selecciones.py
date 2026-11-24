"""Sevens de selecciones: traducciones, elección del torneo, páginas y cliente."""
from datetime import UTC, date, datetime

import pytest
import requests

from datosdep import selecciones as s
from datosdep.scraper import origen_c


def _ms(dia: str, hora: str) -> int:
    return int(datetime.fromisoformat(f"{dia}T{hora}:00").replace(tzinfo=UTC).timestamp() * 1000)


def _evento(id_, label, sport, ini, fin, abbr="Dubai"):
    return {"id": id_, "label": label, "sport": sport, "abbr": abbr, "start": {"label": ini, "millis": _ms(ini, "00:00")},
            "end": {"label": fin, "millis": _ms(fin, "00:00")}}


def _partido(ev, dia, hora, a, b, fase="Pool A", estado="U", puntos=(0, 0)):
    return {"events": [{"id": ev}], "time": {"millis": _ms(dia, hora)}, "teams": [{"name": a}, {"name": b}],
            "status": estado, "scores": list(puntos), "eventPhase": fase}


class _Falso:
    def __init__(self):
        self.ev = {
            "mrs": [_evento("m3", "HSBC SVNS 3 2027 Mens - Dubai", "mrs", "2026-11-27", "2026-11-28"),
                    _evento("m1", "HSBC SVNS 2027 Mens - Dubai", "mrs", "2026-11-28", "2026-11-29"),
                    _evento("m9", "HSBC SVNS 2027 Mens - Cape Town", "mrs", "2026-12-05", "2026-12-06", "Cape Town")],
            "wrs": [_evento("f1", "HSBC SVNS 2027 Womens - Dubai", "wrs", "2026-11-28", "2026-11-29")],
        }
        self.tablas = []

    def eventos(self, dep, desde, hasta):
        return self.ev[dep]

    def partidos_de(self, ids):
        todos = [
            _partido("m1", "2026-11-28", "08:14", "Spain 7s", "France 7s", estado="C", puntos=(19, 12)),
            _partido("m1", "2026-11-28", "08:36", "New Zealand 7s", "Fiji 7s", fase="Pool B"),
            _partido("f1", "2026-11-28", "06:00", "USA 7s", "Spain 7s"),
            _partido("m1", "2026-11-29", "10:06", "1st Pool A", "2nd Pool B", fase="Cup Semi Finals"),
            _partido("m1", "2026-11-29", "16:11", "Winner M15", "Winner M16", fase="Cup Final"),
            _partido("m3", "2026-11-27", "09:00", "Samoa 7s", "Mexico 7s", fase="Pool Pool"),
        ]
        return [p for p in todos if p["events"][0]["id"] in ids]

    def clasificacion(self, id_):
        return self.tablas


@pytest.fixture
def falso(monkeypatch):
    f = _Falso()
    monkeypatch.setattr(s, "cliente", lambda: f)
    return f


def test_traducciones():
    assert s.nombre_equipo("Hong Kong China 7s") == "Hong Kong"
    assert s.nombre_equipo("3rd Pool B") == "3.º Grupo B" and s.es_hueco("3rd Pool B")
    assert s.nombre_equipo("Loser W15") == "Perdedor P15"
    assert s.nombre_equipo("Atlantis 7s") == "Atlantis"  # país sin traducir: tal cual
    assert s.fase("Cup Semi Finals") == "Semifinal" and s.fase("Pool B") == "Grupo B"
    assert s.fase("11th Place Play-Off") == "11.º puesto"


def test_elige_el_circuito_principal_y_junta_chicos_y_chicas(falso):
    t = s.torneo(date(2026, 11, 26))
    assert t["ciudad"] == "Dubái" and set(t["eventos"]) == {"m", "f"}
    assert t["eventos"]["m"]["id"] == "m1"  # no la división de ascenso
    assert set(t["finde"]) == {"m1", "m3", "f1"}  # Ciudad del Cabo (la semana siguiente) no
    assert (t["desde"], t["hasta"]) == (date(2026, 11, 28), date(2026, 11, 29))


def test_paginas_de_espana_y_hora_espanola(falso):
    t = s.torneo(date(2026, 11, 26))
    ps, destacado = s._de_la_vista(t, "pes")
    sl = s.slides(t, ps, "pes", "post", destacado)
    assert len(sl) == 1 and sl[0]["titulo"] == "Sábado 28 nov" and sl[0]["pagina"] == ""
    filas = sl[0]["bloques"][0]["partidos"]
    assert [f["hora"] for f in filas] == ["07:00", "09:14"]  # UTC+1 en noviembre
    assert filas[1]["marcador"] == "19-12" and filas[1]["gana"] == 0 and filas[1]["esp_local"]
    assert filas[0]["fase"] == "Fem · Grupo A"
    assert "eliminatorias" in sl[0]["nota"]  # el domingo depende del grupo


def test_una_imagen_por_dia_sin_numerar(falso):
    t = s.torneo(date(2026, 11, 26))
    ps, destacado = s._de_la_vista(t, "m")
    sl = s.slides(t, ps, "m", "historia", destacado)
    assert [x["titulo"] for x in sl] == ["Sábado 28 nov", "Domingo 29 nov"]
    assert all(x["pagina"] == "" for x in sl)
    final = sl[1]["bloques"][0]["partidos"][-1]
    assert final["local"] == "Ganador P15" and final["hueco_local"] and final["fase"] == "Final"


def test_pais_de_otra_division_y_pais_que_no_juega(falso):
    t = s.torneo(date(2026, 11, 26))
    ps, destacado = s._de_la_vista(t, "pws")  # Samoa: juega la división 3
    sl = s.slides(t, ps, "pws", "post", destacado)
    fila = sl[0]["bloques"][0]["partidos"][0]
    assert destacado == "Samoa" and fila["esp_local"] and fila["fase"] == "Masc · Div. 3 · Grupo"
    assert "Samoa" in s.paises(t) and s.paises(t)[0] == "España"
    assert s._de_la_vista(t, "puy")[0] == []  # Uruguay no juega ese fin de semana


def test_grupos_a_cero_no_se_mandan(falso):
    t = s.torneo(date(2026, 11, 26))
    fila = {"positionLabel": "1", "team": {"name": "Spain 7s"}, "played": 0, "points": 0}
    falso.tablas = [{"label": "Pool A", "entries": [fila]}]
    assert s.slides_grupos(t) == []
    falso.tablas = [{"label": "Pool A", "entries": [{**fila, "played": 1, "points": 3}]}]
    g = s.slides_grupos(t)[0]["grupos"]
    assert g[0]["nombre"] == "Masculino · Grupo A" and g[0]["filas"][0]["equipo"] == "España"


def test_sin_torneo(monkeypatch):
    class Vacio(_Falso):
        def eventos(self, dep, desde, hasta):
            return []
    monkeypatch.setattr(s, "cliente", lambda: Vacio())
    assert s.torneo(date(2026, 11, 26)) is None and s.imagenes("pes") == ([], None)


# --- cliente ------------------------------------------------------------------------------------------------------

class _R:
    def __init__(self, status, cuerpo=None):
        self.status_code, self.cuerpo = status, cuerpo

    def json(self):
        return self.cuerpo

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(str(self.status_code))


def test_cliente_limitado_usa_lo_ultimo_y_no_insiste(monkeypatch):
    monkeypatch.setattr(origen_c, "BASE", "https://ejemplo.invalid")
    c = origen_c.OrigenC()
    respuestas = [_R(200, {"content": [{"id": 1}], "pageInfo": {"numPages": 1}}), _R(429)]
    llamadas = []
    monkeypatch.setattr(c.sesion, "get", lambda *a, **k: llamadas.append(1) or respuestas.pop(0))
    assert c.partidos_de(["x"]) == [{"id": 1}]
    c._memoria = {k: (0.0, v) for k, (_, v) in c._memoria.items()}  # caducado
    assert c.partidos_de(["x"]) == [{"id": 1}]  # 429: lo último que se tuvo
    assert c.partidos_de(["x"]) == [{"id": 1}] and len(llamadas) == 2  # bloqueado: ya no pide


def test_cliente_sin_configurar(monkeypatch):
    monkeypatch.setattr(origen_c, "BASE", "")
    with pytest.raises(origen_c.SinAcceso):
        origen_c.OrigenC().partidos_de(["x"])


def test_cada_pais_tiene_su_bandera_guardada():
    from datosdep.render import render

    faltan = [n for n, c in s.BANDERA.items() if not (render.BANDERAS / f"{c}.png").exists()]
    assert not faltan
    assert set(s.BANDERA) >= set(s.PAISES.values())  # todo país traducido lleva bandera
    assert render.escudo_equipo("España", s.banderas(["España"])).startswith("data:image/jpeg")
    assert render.escudo_equipo("Atlantis", s.banderas(["Atlantis"])) == ""
