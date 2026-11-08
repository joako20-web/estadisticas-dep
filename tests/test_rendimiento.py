"""Rendimiento del jugador (puntos por partido, peso en el equipo, titularidad, minutos), ranking histórico y comparación."""
import gzip
import json

from datosdep import fichas, historico
from datosdep.scraper import acta_pdf, origen_a
from datosdep.scraper.parsers import JugadorTemporada

CAND = {"nombre": "ANA PEREZ", "equipo": "EQ A", "comp": "dh_masc", "grupo": "unico"}
# fila de resumen: nombre, equipo, puntos, ensayos, conv, golpes, drops, amarillas, rojas, dorsal
FILAS = [("1", ["ANA PEREZ", "EQ A", 10, 1, 0, 0, 0, 0, 0, 10]), ("2", ["ANA PEREZ", "EQ A", 0, 0, 0, 0, 0, 0, 0, 18]),
         ("4", ["ANA PEREZ", "EQ A", 20, 0, 5, 0, 0, 0, 0, 10])]
PARTIDOS = {
    1: {"id": 1, "jornada": 1, "local": "EQ A", "visitante": "EQ B", "puntos_local": 30, "puntos_visitante": 10, "estado": "jugado"},
    2: {"id": 2, "jornada": 2, "local": "EQ C", "visitante": "EQ A", "puntos_local": 5, "puntos_visitante": 20, "estado": "jugado"},
    3: {"id": 3, "jornada": 3, "local": "EQ A", "visitante": "EQ D", "puntos_local": 12, "puntos_visitante": 12, "estado": "jugado"},
    4: {"id": 4, "jornada": 4, "local": "EQ A", "visitante": "EQ E", "puntos_local": 40, "puntos_visitante": 0, "estado": "jugado"},
    5: {"id": 5, "jornada": 5, "local": "EQ F", "visitante": "EQ G", "puntos_local": 9, "puntos_visitante": 9, "estado": "jugado"},
}


class _Cliente:
    def extra_acta(self, pid):
        return {"equipos": ["EQ A", "EQ B"], "fin": 4800, "cambios": [[0, 2400, 10, 16, "Reemplazo Táctico"]], "tarjetas": []} \
            if pid == 1 else None


def test_rendimiento(monkeypatch):
    monkeypatch.setattr(fichas, "_partidos_guardados", lambda c, g: PARTIDOS)
    resumen = {pid: [f] for pid, f in FILAS}
    r = fichas.rendimiento_jugador(CAND, {}, resumen, FILAS, _Cliente(), None)
    assert r["pj"] == 3 and r["puntos"] == 30 and r["ppp"] == 10.0
    assert (r["titular"], r["suplente"]) == (2, 1)
    assert r["pct_equipo"] == round(100 * 30 / (30 + 20 + 40))  # sus puntos entre los de su equipo en esos partidos
    assert [(b["j"], b["pts"]) for b in r["barras"]] == [(1, 10), (2, 0), (3, None), (4, 20)]  # el 3 no estuvo convocado
    assert r["minutos"] == {"total": 40, "partidos": 1, "media": 40}  # sale a los 40' (solo el partido 1 tiene cambios)


def test_rendimiento_sin_partidos_guardados(monkeypatch):
    monkeypatch.setattr(fichas, "_partidos_guardados", lambda c, g: {})
    r = fichas.rendimiento_jugador(CAND, {}, {pid: [f] for pid, f in FILAS}, FILAS, _Cliente(), None)
    assert r["pct_equipo"] is None and r["barras"] == []


def test_minutos_no_se_calculan_para_otra_plataforma(monkeypatch):
    monkeypatch.setattr(fichas, "_partidos_guardados", lambda c, g: PARTIDOS)
    r = fichas.rendimiento_jugador(CAND, {"fuente": "origen_b"}, {pid: [f] for pid, f in FILAS}, FILAS, _Cliente(), None)
    assert r["minutos"] is None


def test_ranking_historico(tmp_path, monkeypatch):
    monkeypatch.setattr(historico, "HISTORICO", tmp_path)
    monkeypatch.setattr(historico, "completar", lambda tipo: None)
    (tmp_path / "2526_dh_masc.json").write_text(json.dumps({"id_temp": 2526, "jugadores": {
        "1": [["A", "X", 10, 100, 2, 0, 0]], "2": [["B", "X", 10, 300, 5, 0, 0]], "3": [["C", "X", 20, 50, 1, 0, 0]]}}), encoding="utf-8")
    actuales = [JugadorTemporada(1, "A", "X", 5, 60, 1, 0, 0), JugadorTemporada(2, "B", "X", 5, 10, 0, 0, 0)]
    r = fichas._ranking_historico("dh_masc", actuales, 1)
    assert (r["puntos"], r["puesto_puntos"], r["de"], r["temporadas"]) == (160, 2, 3, 2)  # B: 310 > A: 160 > C: 50
    assert r["puesto_pj"] == 2 and r["puesto_ensayos"] == 2  # C tiene más partidos (20); B más ensayos
    assert fichas._ranking_historico("mad_1r", actuales, 1) is None and fichas._ranking_historico("dh_masc", actuales, None) is None


def test_comparacion_marca_al_mejor_y_en_tarjetas_gana_el_menor():
    a = {"esta": {"pj": 6, "puntos": 100, "ppp": 16.7, "ensayos": 1, "tarjetas": 0}, "carrera": {"temporadas": 3, "pj": 40, "puntos": 500, "ensayos": 2, "tarjetas": 4}}
    b = {"esta": {"pj": 5, "puntos": 40, "ppp": 8.0, "ensayos": 1, "tarjetas": 0}, "carrera": {"temporadas": 4, "pj": 60, "puntos": 520, "ensayos": 6, "tarjetas": 1}}
    gana = {f["k"] + str(i): f["gana"] for i, f in enumerate(fichas._filas_comparacion(a, b)) if "k" in f}
    assert gana["Partidos1"] == "a" and gana["Ensayos4"] is None  # empate: nadie
    assert gana["Temporadas6"] == "b" and gana["Tarjetas10"] == "b"  # menos tarjetas gana


def test_refrescar_extra_completa_un_acta_guardada_sin_cambios(tmp_path, monkeypatch):
    """Un acta guardada antes sin cambios se vuelve a pedir una vez y queda con ellos."""
    monkeypatch.setattr(origen_a, "RAIZ_DATOS", tmp_path)
    monkeypatch.setenv("ORIGEN_A_ACTA_URL", "https://ejemplo.invalid/acta")
    paginas = json.loads((__import__("pathlib").Path(__file__).parent / "fixtures" / "acta_pdf_17668_fragmentos.json").read_text(encoding="utf-8"))
    monkeypatch.setattr(origen_a.OrigenA, "_get", lambda self, *a, **k: b"%PDF")
    monkeypatch.setattr(acta_pdf, "fragmentos", lambda raw: [[tuple(x) for x in p] for p in paginas])
    c = origen_a.OrigenA(cache_dir=tmp_path / "cache")
    ruta = c._guardada(17668)
    ruta.parent.mkdir(parents=True)
    ruta.write_bytes(gzip.compress(b'{"status": true, "data": {"partido": {}}}'))  # formato antiguo, sin 'extra'
    assert not c.tiene_extra(17668)
    assert c.refrescar_extra(17668) and c.tiene_extra(17668)
    assert c.extra_acta(17668)["fin"] == 4800


def test_vs_en_jugador_o_equipo_se_entiende_como_comparacion():
    from datosdep.flujo import _CON_VS

    assert _CON_VS.search("felicisimo santiago rodriguez vs salvador guardiola garcia")
    assert _CON_VS.search("vrac VS salvador") and _CON_VS.search("a contra b")
    assert not _CON_VS.search("alvaro versus") and not _CON_VS.search("mansilla")
