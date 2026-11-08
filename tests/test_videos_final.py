"""Props del reel "Así fue" de un partido (sin red: acta de prueba y escudos falsos)."""
import pytest

from datosdep.models import Acta, Evento
from datosdep.videos import PLANTILLAS, base, final

L, V = "HUESITOS LA VILA RUGBY CLUB", "UNIO ESPORTIVA SANTBOIANA"
PARTIDO = {"id": 1, "jornada": 2, "fecha": "2026-10-04T12:00:00", "local": L, "visitante": V,
           "puntos_local": 36, "puntos_visitante": 33, "ronda": ""}


def ev(minuto, tipo, equipo, jugador="", marcador=None):
    return Evento(minuto, tipo, tipo, marcador, equipo, jugador or f"JUGADOR DEL MINUTO {minuto}")


# Remontada de 19 y drop en el 80' (como el origen A, en orden inverso)
EVENTOS = list(reversed([
    ev(5, "ensayo", L, "LUCAS MAXIMILIANO MELIAN"), ev(6, "conversion", L, "AGUSTIN ALTAMIRANO DECICCO"),
    ev(17, "ensayo", V), ev(18, "conversion", V, "ALBERT MILLAN DIAZ"),
    ev(23, "ensayo", V), ev(28, "ensayo", V), ev(29, "conversion", V, "ALBERT MILLAN DIAZ"),
    ev(34, "ensayo", V), ev(35, "conversion", V, "ALBERT MILLAN DIAZ"),
    ev(38, "ensayo", L), ev(39, "conversion", L, "AGUSTIN ALTAMIRANO DECICCO"),
    ev(48, "ensayo", L), ev(48, "amarilla", V), ev(49, "conversion", L, "AGUSTIN ALTAMIRANO DECICCO"),
    ev(58, "ensayo", L), ev(65, "ensayo", L), ev(66, "conversion", L, "AGUSTIN ALTAMIRANO DECICCO"),
    ev(75, "ensayo", V), ev(76, "conversion", V, "ALBERT MILLAN DIAZ"),
    ev(80, "drop", L, "AGUSTIN ALTAMIRANO DECICCO"),
]))


@pytest.fixture(autouse=True)
def sin_escudos(monkeypatch):
    monkeypatch.setattr(base.R, "escudo_equipo", lambda equipo, escudos: "data:x")


def props(eventos=EVENTOS, partido=PARTIDO):
    return final.props(partido, Acta(1, L, V, eventos, [], []), {}, "dh_masc", "2026/27")


def test_remontada_completa():
    p = props()
    assert p["completa"] and p["etiqueta"] == "Remontada"
    assert p["frase"] == "De perder por 19 a ganar en el 80'"
    assert p["local"]["gana"] and not p["visitante"]["gana"]
    assert (p["local"]["ensayos"], p["visitante"]["ensayos"]) == (5, 5)
    ev_ = p["evolucion"]
    assert ev_[0] == {"minuto": 5, "lado": "L", "tipo": "ensayo", "local": 5, "visitante": 0}
    assert (ev_[-1]["local"], ev_[-1]["visitante"]) == (36, 33)
    assert min(a["local"] - a["visitante"] for a in ev_) == -19
    assert [e["minuto"] for e in p["ensayos"]] == sorted(e["minuto"] for e in p["ensayos"])
    assert len(p["ensayos"]) == 10


def test_anotadores():
    a = props()["anotadores"]
    assert len(a) == 4
    assert a[0]["apellidos"].startswith("Altamirano") and a[0]["puntos"] == 11
    assert a[0]["detalle"] == "4 transf. · 1 drop" and a[0]["lado"] == "L"
    assert a[1]["puntos"] == 8 and a[1]["detalle"] == "4 transf."


def test_acta_incompleta_solo_marcador():
    p = props(EVENTOS[1:])  # falta el drop del 80'
    assert not p["completa"]
    assert p["evolucion"] == p["ensayos"] == p["anotadores"] == []
    assert p["etiqueta"] == "Al límite"  # el relato por el resultado sí sale
    assert final.props(PARTIDO, None, {}, "dh_masc", "2026/27")["completa"] is False


def test_relatos():
    assert final.relato([], 70, 0, False) == ("Paliza", "70 puntos de diferencia")
    assert final.relato([], 20, 20, False)[0] == "Empate"
    anot = [{"minuto": m, "lado": "L", "tipo": "ensayo", "local": 5 * i, "visitante": 0, "puntos": 5, "jugador": "X"}
            for i, m in enumerate((10, 20, 30, 40), 1)]
    assert final.relato(anot, 20, 0, True) == ("Bonus ofensivo", "4 ensayos a 0")
    ultimo = [{"minuto": 10, "lado": "V", "tipo": "golpe", "local": 0, "visitante": 3},
              {"minuto": 78, "lado": "L", "tipo": "ensayo", "local": 5, "visitante": 3}]
    assert final.relato(ultimo, 5, 3, True)[0] == "En el último minuto"


def test_orden_origen_b_y_mismo_minuto():
    # OrigenB: orden directo, ensayo y transformación en el mismo minuto
    evs = [ev(7, "conversion", V, marcador=(0, 7)), ev(7, "ensayo", V, marcador=(0, 5)), ev(3, "golpe", L, marcador=(3, 0))]
    anot = final.anotaciones(Acta(1, L, V, evs, [], []), L, V)
    assert [(a["tipo"], a["local"], a["visitante"]) for a in anot] == [
        ("golpe", 3, 0), ("ensayo", 3, 5), ("conversion", 3, 7)]


def test_apellidos_caben():
    for nombre in ("LUCAS MAXIMILIANO MELIAN", "CELIA CARMEN JOVER CANO", "THALIA SIBEL DA LUZ SILVA"):
        assert 0 < len(final._apellido(nombre)) <= final.MAX_LETRAS_ENSAYO
    assert final._apellido("") == "Castigo"


def test_registro_y_construir(monkeypatch):
    p = PLANTILLAS["final"]
    assert p.composicion == "ReelFinal" and not p.por_liga
    datos = {"partidos": [PARTIDO], "escudos": {}, "temporada": "2026/27", "jornada": 2}
    monkeypatch.setattr(final, "datos_jornada", lambda *a: datos)
    monkeypatch.setattr(final, "_acta", lambda *a: Acta(1, L, V, EVENTOS, [], []))
    props_ = p.construir("dh_masc", "unico", 2, id_partido=1)
    assert props_["etiqueta"] == "Remontada" and props_["jornada"] == 2
    with pytest.raises(RuntimeError):
        p.construir("dh_masc", "unico", 2, id_partido=999)
    with pytest.raises(RuntimeError):
        p.construir("dh_masc", "unico", 2)
    assert final.id_partidos_jornada("dh_masc", "unico", 2) == [(1, "La Vila 36-33 Santboiana")]
