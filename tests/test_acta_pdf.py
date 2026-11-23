"""Lector del acta en PDF de el origen A: debe dar lo mismo que el JSON del proxy."""
import gzip
import json
from pathlib import Path

import pytest

from datosdep.scraper import acta_pdf, origen_a, parsers

FIX = Path(__file__).parent / "fixtures"


def _paginas(id_partido):
    datos = json.loads((FIX / f"acta_pdf_{id_partido}_fragmentos.json").read_text(encoding="utf-8"))
    return [[(y, x, t) for y, x, t in pagina] for pagina in datos]


def _eventos(a):
    return sorted((e.minuto, e.tipo, e.equipo, e.jugador) for e in a.eventos)


def _alineaciones(a):
    return sorted((j.nombre, j.dorsal, j.tantos) for j in a.alineacion_local + a.alineacion_visitante)


@pytest.mark.parametrize("id_partido", [17668, 17671])
def test_pdf_igual_que_json(id_partido):
    pdf = parsers.acta_json(acta_pdf.acta_a_json(_paginas(id_partido)), id_partido)
    json_ = parsers.acta_json((FIX / f"acta_{id_partido}.json").read_bytes(), id_partido)
    assert (pdf.local, pdf.visitante) == (json_.local, json_.visitante)
    assert pdf.marcador_por_eventos() == json_.marcador_por_eventos()
    assert _eventos(pdf) == _eventos(json_)
    # los nombres con caracteres rotos en el JSON de el origen A se leen mejor en el PDF: se ignoran aquí
    ok = lambda a: [x for x in _alineaciones(a) if x[0].isascii()]  # noqa: E731
    assert ok(pdf) == ok(json_)


def test_nombre_largo_partido_en_dos_lineas():
    a = parsers.acta_json(acta_pdf.acta_a_json(_paginas(17671)), 17671)
    assert "NICOLAS BENJAMIN GUILLE-ANDRE RORET" in [j.nombre for j in a.alineacion_local + a.alineacion_visitante]


def test_pdf_con_marcador_que_no_cuadra_no_se_acepta():
    paginas = _paginas(17668)
    paginas[0] = [(y, x, "99" if t == "30" else t) for y, x, t in paginas[0]]
    with pytest.raises(ValueError):
        acta_pdf.acta_a_json(paginas)


def test_lo_que_no_es_pdf_se_rechaza():
    with pytest.raises(ValueError):
        acta_pdf.fragmentos(b"<html>403</html>")


def test_acta_se_pide_una_sola_vez(tmp_path, monkeypatch):
    """Pedida y convertida, el acta se guarda en data/actas_pdf y no se vuelve a pedir."""
    monkeypatch.setattr(origen_a, "RAIZ_DATOS", tmp_path)
    monkeypatch.setenv("ORIGEN_A_ACTA_URL", "https://ejemplo.invalid/acta")
    pedidos = []
    monkeypatch.setattr(origen_a.OrigenA, "_get", lambda self, *a, **k: pedidos.append(a) or b"%PDF")
    monkeypatch.setattr(acta_pdf, "fragmentos", lambda raw: _paginas(17668))
    c = origen_a.OrigenA(cache_dir=tmp_path / "cache")
    monkeypatch.setattr(c, "_api", lambda *a, **k: {"data": None})  # sin JSON: se usa el PDF entero
    a1 = c.acta(17668)
    a2 = c.acta(17668)
    assert len(pedidos) == 1 and pedidos[0][0] == "https://ejemplo.invalid/acta"
    assert a1.marcador_por_eventos() == a2.marcador_por_eventos() == (30, 21)
    assert c.acta_en_cache(17668)
    assert json.loads(gzip.decompress((tmp_path / "actas_pdf" / "17668.gz").read_bytes()))["status"]


def test_sin_direccion_configurada_cuenta_como_sin_acceso(tmp_path, monkeypatch):
    monkeypatch.setattr(origen_a, "RAIZ_DATOS", tmp_path)
    monkeypatch.delenv("ORIGEN_A_ACTA_URL", raising=False)
    c = origen_a.OrigenA(cache_dir=tmp_path / "cache")
    monkeypatch.setattr(c, "_api", lambda *a, **k: {"data": None})
    a = c.acta(17668)
    assert a.eventos == [] and c.actas_bloqueadas


def test_ensayo_de_castigo_sin_dorsal():
    """En la línea temporal el ensayo de castigo trae 'EQUIPO' en vez de dorsal (7 puntos)."""
    a = parsers.acta_json(acta_pdf.acta_a_json(_paginas(17644)), 17644)
    assert a.marcador_por_eventos() == (29, 19)
    castigo = [e for e in a.eventos if e.tipo == "ensayo_castigo"]
    assert len(castigo) == 1 and castigo[0].puntos == 7 and castigo[0].jugador == ""


def test_designaciones_con_partido_sin_fecha(monkeypatch):
    """Un partido de la próxima jornada sin fecha no debe romper el orden (iba con 'fecha or 0')."""
    from datetime import datetime

    from datosdep import arbitros
    from datosdep.models import Competicion, Partido

    def p(i, fecha):
        return Partido(i, 7, fecha, f"L{i}", f"V{i}", None, None, "", "pendiente", grupo=1)

    comp = Competicion([p(1, None), p(2, datetime(2026, 11, 15, 12)), p(3, datetime(2026, 11, 14, 17))], [])

    class Falso:
        def clasificacion(self, g): return []
        def competicion(self, g): return comp

    monkeypatch.setattr(arbitros, "registros", lambda c, cl: ([], {}))
    monkeypatch.setattr(arbitros, "cruces", lambda r, minimo=1: [])
    monkeypatch.setattr(arbitros, "_arbitro", lambda c, i, j: None)
    monkeypatch.setattr(arbitros, "cargar_config", lambda: {"competiciones": {"x": {"grupos": {"unico": 1}}}})
    d = arbitros.designaciones("x", Falso())
    assert [f["local"] for f in d["filas"]] == ["L3", "L2", "L1"]  # por fecha y, al final, el que no la tiene


def test_apellido_largo_en_dos_lineas_y_cabecera_con_otra_disposicion():
    """Acta de M23: el dorsal 21 del visitante tiene el apellido en dos líneas y el marcador visitante va en otra columna."""
    a = parsers.acta_json(acta_pdf.acta_a_json(_paginas(18101)), 18101)
    assert a.marcador_por_eventos() == (31, 55)
    assert "ANTONIO CAMPS MONJARDINO DE AZEVEDO SOARES" in [j.nombre for j in a.alineacion_visitante if j.dorsal == 21]


def test_dos_dorsales_o_minutos_pegados_son_filas_distintas():
    """Filas de jugadores o de eventos a menos de 5 pt: no se funden (se perdía un ensayo o un suplente)."""
    from datosdep.scraper.acta_pdf import _filas

    trozos = [(100.0, 10.0, "19"), (100.0, 60.0, "RODRIGUEZ LAMAS, NICOLAS"),
              (97.0, 60.0, "GARCIMARTIN BAILON ,"), (96.0, 10.0, "20"), (93.0, 60.0, "GONZALO")]
    filas = _filas(trozos)
    assert [[t for _, t in f] for _, f in filas] == [["19", "RODRIGUEZ LAMAS, NICOLAS"], ["GARCIMARTIN BAILON ,", "20", "GONZALO"]] \
        or [[t for _, t in f] for _, f in filas] == [["19", "RODRIGUEZ LAMAS, NICOLAS"], ["20", "GARCIMARTIN BAILON , GONZALO"]]
    horas = [(100.0, 10.0, "27:00"), (100.0, 40.0, "Ensayo"), (97.0, 10.0, "27:30"), (97.0, 40.0, "Conversion de ensayo")]
    assert len(_filas(horas)) == 2
