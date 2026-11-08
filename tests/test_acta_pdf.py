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
    a = c.acta(17668)
    assert a.eventos == [] and c.actas_bloqueadas


def test_ensayo_de_castigo_sin_dorsal():
    """En la línea temporal el ensayo de castigo trae 'EQUIPO' en vez de dorsal (7 puntos)."""
    a = parsers.acta_json(acta_pdf.acta_a_json(_paginas(17644)), 17644)
    assert a.marcador_por_eventos() == (29, 19)
    castigo = [e for e in a.eventos if e.tipo == "ensayo_castigo"]
    assert len(castigo) == 1 and castigo[0].puntos == 7 and castigo[0].jugador == ""
