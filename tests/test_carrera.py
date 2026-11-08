"""Carrera de un jugador entre temporadas: se une por el id del jugador, no por club ni nombre."""
import json

from datosdep import fichas, historico
from datosdep.scraper.parsers import JugadorTemporada


def _guardar(tmp_path, id_temp, tipo, jugadores, clubes=None):
    (tmp_path / f"{id_temp}_{tipo}.json").write_text(json.dumps({
        "id_temp": id_temp, "temporada": f"{id_temp // 100 + 2000}/{id_temp % 100}", "tipo": tipo,
        "clubes": clubes or {}, "jugadores": jugadores}), encoding="utf-8")


def test_cambio_de_club_y_otra_competicion_con_el_mismo_club(tmp_path, monkeypatch):
    monkeypatch.setattr(historico, "HISTORICO", tmp_path)
    _guardar(tmp_path, 2425, "dh_masc", {"7": [["ANA PEREZ", "BARÇA RUGBY", 17, 163, 1, 1, 0]]})
    _guardar(tmp_path, 2526, "dh_masc", {"7": [["ANA PEREZ", "RECOLETAS 2031", 18, 208, 0, 0, 0]]})
    _guardar(tmp_path, 2526, "copa", {"7": [["ANA PEREZ", "RECOLETAS 2031", 2, 32, 0, 0, 0]]})
    filas = historico.carrera(7)
    assert [(f["temporada"], f["tipo"], f["equipo"]) for f in filas] == [
        ("2025/26", "copa", "RECOLETAS 2031"), ("2025/26", "dh_masc", "RECOLETAS 2031"),
        ("2024/25", "dh_masc", "BARÇA RUGBY")]
    assert filas[2]["tarjetas"] == 1


def test_dos_equipos_en_la_misma_temporada_y_liga(tmp_path, monkeypatch):
    monkeypatch.setattr(historico, "HISTORICO", tmp_path)
    _guardar(tmp_path, 2526, "dh_masc", {"9": [["LUIS RUIZ", "A", 5, 20, 0, 0, 0], ["LUIS RUIZ", "B", 8, 40, 1, 0, 1]]})
    assert [(f["equipo"], f["pj"], f["tarjetas"]) for f in historico.carrera(9)] == [("A", 5, 0), ("B", 8, 1)]


def test_otro_jugador_o_sin_id_no_mezcla(tmp_path, monkeypatch):
    monkeypatch.setattr(historico, "HISTORICO", tmp_path)
    _guardar(tmp_path, 2526, "dh_masc", {"7": [["ANA PEREZ", "A", 1, 1, 0, 0, 0]]})
    assert historico.carrera(8) == [] and historico.carrera(None) == []


def test_id_fuente_por_nombre_sin_tildes_y_desempata_por_equipo():
    js = [JugadorTemporada(1, "JOSÉ GARCÍA", "A", 1, 1, 0, 0, 0), JugadorTemporada(2, "JOSE GARCIA", "B", 1, 1, 0, 0, 0)]
    assert fichas._id_fuente(js, "Jose Garcia", "B") == 2
    assert fichas._id_fuente(js, "Nadie", "B") is None
