"""Actas desde el JSON de la API: validación, guardado limpio, cambios del PDF y caminos de respaldo."""
import copy
import gzip
import json
from pathlib import Path

import pytest
import requests

from datosdep import minutos
from datosdep.models import Acta
from datosdep.scraper import acta_api, acta_pdf, origen_a, parsers

FIX = Path(__file__).parent / "fixtures"


def _api():
    return json.loads((FIX / "api_acta_anonima.json").read_text(encoding="utf-8"))


def _paginas(id_partido):
    datos = json.loads((FIX / f"acta_pdf_{id_partido}_fragmentos.json").read_text(encoding="utf-8"))
    return [[(y, x, t) for y, x, t in pagina] for pagina in datos]


# --- validación -------------------------------------------------------------------------------------------------

def test_valida_un_acta_correcta():
    dorsales, descuadre = acta_api.validar(_api(), 1)
    assert descuadre is None
    assert len(dorsales[0]) == 22 and len(dorsales[1]) == 18


def test_si_las_jugadas_no_suman_manda_el_marcador_oficial():
    r = _api()
    r["data"]["eventos"].append({**r["data"]["eventos"][1], "minuto": "66:00", "tipo_evento": "Conversion de ensayo"})
    dorsales, descuadre = acta_api.validar(r, 1)
    assert descuadre == [7, 58]  # la suma de las jugadas, para dejar constancia
    a = parsers.acta_json(json.dumps(acta_api.limpia(r, descuadre)).encode(), 1)
    assert a.marcador_oficial == (7, 56)
    assert a.cuadra_con((7, 56))  # vale para el partido: el resultado es el del árbitro
    assert a.marcador_por_eventos() == (7, 58)


def test_acta_sin_jugadas_con_marcador_no_vale():
    r = _api()
    r["data"]["eventos"] = []
    with pytest.raises(ValueError, match="sin eventos"):
        acta_api.validar(r, 1)


@pytest.mark.parametrize("estropear, mensaje", [
    (lambda d: d["alineaciones"].append({**d["alineaciones"][0]}), "repetido"),
    (lambda d: d.__setitem__("alineaciones", d["alineaciones"][:10]), "incompleta"),
    (lambda d: d["partido"]["local"].pop("resultado"), "cabecera"),
    (lambda d: d["eventos"].append({**d["eventos"][0], "id_equipo": 999}), "no juega"),
])
def test_rechaza_actas_dudosas(estropear, mensaje):
    r = _api()
    estropear(r["data"])
    with pytest.raises(ValueError, match=mensaje):
        acta_api.validar(r, 1)


def test_respuesta_sin_datos():
    for r in ({}, {"data": None}, {"error": "x"}, []):
        with pytest.raises(ValueError):
            acta_api.validar(r, 1)


def test_lo_guardado_no_lleva_direcciones_de_la_fuente_ni_tecnicos():
    limpio = acta_api.limpia(_api())
    texto = json.dumps(limpio)
    assert "//" not in texto and "TECNICO" not in texto
    a = parsers.acta_json(texto.encode(), 1)
    assert len(a.alineacion_local) == 22 and a.cuadra_con((7, 56))


# --- marcador oficial frente a suma de jugadas -------------------------------------------------------------------

def test_cuadra_con():
    vacia = Acta(1, "A", "B", [], [], [])
    assert vacia.cuadra_con((0, 0)) and not vacia.cuadra_con((7, 0))  # sin marcador oficial: como siempre
    sin_jugadas = Acta(1, "A", "B", [], [], [], marcador_oficial=(48, 39))
    assert not sin_jugadas.cuadra_con((48, 39))  # un acta sin jugadas no sirve aunque el marcador coincida
    assert Acta(1, "A", "B", [], [], [], marcador_oficial=(0, 0)).cuadra_con((0, 0))


# --- cambios del PDF contrastados con el acta ----------------------------------------------------------------------

def _base_pdf(id_partido):
    paginas = _paginas(id_partido)
    d = json.loads(acta_pdf.acta_a_json(paginas))["data"]
    dorsales = [{j["dorsal"] for j in d["alineaciones"] if j["id_equipo"] == lado} for lado in (1, 2)]
    marcador = (d["partido"]["local"]["resultado"], d["partido"]["visitante"]["resultado"])
    return paginas, d, dorsales, marcador


def test_cambios_del_pdf_iguales_a_los_del_lector_completo():
    paginas, d, dorsales, marcador = _base_pdf(17668)
    extra = acta_pdf.extra_de_fragmentos(paginas, d["extra"]["equipos"], marcador, dorsales)
    assert sorted(extra["cambios"]) == sorted(d["extra"]["cambios"])
    assert sorted(extra["tarjetas"]) == sorted(d["extra"]["tarjetas"])


def test_cambios_de_un_pdf_que_no_es_de_ese_partido():
    paginas, d, dorsales, marcador = _base_pdf(17668)
    with pytest.raises(ValueError, match="otro marcador"):
        acta_pdf.extra_de_fragmentos(paginas, d["extra"]["equipos"], (marcador[0] + 1, marcador[1]), dorsales)
    if d["extra"]["cambios"]:
        lado = d["extra"]["cambios"][0][0]
        cojos = [set(x) for x in dorsales]
        cojos[lado].discard(d["extra"]["cambios"][0][3])
        with pytest.raises(ValueError, match="no está en la alineación"):
            acta_pdf.extra_de_fragmentos(paginas, d["extra"]["equipos"], marcador, cojos)


# --- cliente: caminos de respaldo ----------------------------------------------------------------------------------

@pytest.fixture
def cliente(tmp_path, monkeypatch):
    monkeypatch.setattr(origen_a, "RAIZ_DATOS", tmp_path / "datos")
    monkeypatch.setenv("ORIGEN_A_ACTA_URL", "https://ejemplo.invalid/acta")
    c = origen_a.OrigenA()
    c.cache_dir = tmp_path / "cache"
    c.pdf_pedidos = 0

    def get(*a, **k):
        c.pdf_pedidos += 1
        return b"%PDF falso"
    monkeypatch.setattr(c, "_get", get)
    monkeypatch.setattr(c, "_api", lambda tipo, **k: _api())
    return c


EXTRA = {"equipos": ["CLUB LOCAL DE PRUEBA", "CLUB VISITANTE DE PRUEBA"], "fin": 4800,
         "cambios": [[0, 2400, 1, 16, "Reemplazo Táctico"]], "tarjetas": []}


def _guardada(c, i):
    return json.loads(gzip.decompress(c._guardada(i).read_bytes()))


def test_api_y_pdf_bien(cliente, monkeypatch):
    monkeypatch.setattr(acta_pdf, "extra_de_pdf", lambda *a: EXTRA)
    a = cliente.acta(5)
    assert a.cuadra_con((7, 56)) and len(a.alineacion_visitante) == 18
    g = _guardada(cliente, 5)
    assert g["fuente"] == "api" and g["data"]["extra"] == EXTRA
    assert minutos.minutos_jugador(cliente.extra_acta(5), "Club  local de prueba", 16) == 40  # nombre tolerante
    cliente.acta(5)
    assert cliente.pdf_pedidos == 1  # guardada: no se vuelve a pedir


def test_pdf_falla_el_acta_vale_sin_minutos_y_se_reintenta_con_limite(cliente, monkeypatch):
    def falla(*a):
        raise ValueError("PDF raro")
    monkeypatch.setattr(acta_pdf, "extra_de_pdf", falla)
    a = cliente.acta(6)
    assert a.cuadra_con((7, 56))  # las estadísticas salen igual
    assert not cliente.tiene_extra(6) and cliente.puede_extra(6)
    for _ in range(5):
        cliente.refrescar_extra(6)
    assert cliente.pdf_pedidos == origen_a.MAX_INTENTOS_EXTRA  # 1 al leerla + 2 reintentos, y se deja
    assert not cliente.puede_extra(6)
    monkeypatch.setattr(acta_pdf, "extra_de_pdf", lambda *a: EXTRA)
    assert not cliente.refrescar_extra(6)  # agotado: ya no pide más


def test_api_mal_usa_el_pdf_entero(cliente, monkeypatch):
    monkeypatch.setattr(cliente, "_api", lambda tipo, **k: {"data": None})
    monkeypatch.setattr(acta_pdf, "pdf_a_json", lambda raw: acta_pdf.acta_a_json(_paginas(17668)))
    a = cliente.acta(7)
    assert a.eventos and _guardada(cliente, 7).get("fuente") is None  # formato del lector de PDF


@pytest.mark.parametrize("error_api", [requests.ConnectionError("corte"), ValueError("raro"), origen_a.AccesoRestringido("403")])
def test_todo_falla_queda_pendiente_sin_romper(cliente, monkeypatch, error_api):
    def api(tipo, **k):
        raise error_api

    def pdf(raw):
        raise ValueError("no cuadra")
    monkeypatch.setattr(cliente, "_api", api)
    monkeypatch.setattr(acta_pdf, "pdf_a_json", pdf)
    a = cliente.acta(8)
    assert a.id_partido == 8 and not a.eventos and not a.cuadra_con((7, 56))
    assert 8 in cliente.actas_ilegibles
    assert not cliente._guardada(8).exists()


def test_acta_guardada_corrupta_se_vuelve_a_pedir(cliente, monkeypatch):
    monkeypatch.setattr(acta_pdf, "extra_de_pdf", lambda *a: EXTRA)
    cliente._guardada(9).parent.mkdir(parents=True, exist_ok=True)
    cliente._guardada(9).write_bytes(b"esto no es gzip")
    assert cliente.acta(9).cuadra_con((7, 56))
    assert _guardada(cliente, 9)["fuente"] == "api"


def test_acta_descuadrada_se_revisa_una_vez_al_dia(cliente, monkeypatch):
    monkeypatch.setattr(acta_pdf, "extra_de_pdf", lambda *a: EXTRA)
    malo = _api()
    malo["data"]["eventos"].append({**malo["data"]["eventos"][1], "tipo_evento": "Conversion de ensayo"})
    monkeypatch.setattr(cliente, "_api", lambda tipo, **k: copy.deepcopy(malo))
    cliente.acta(10)
    assert _guardada(cliente, 10)["descuadre"] == [7, 58]
    monkeypatch.setattr(cliente, "_api", lambda tipo, **k: _api())  # la federación lo corrige
    cliente.acta(10)
    assert _guardada(cliente, 10)["descuadre"] == [7, 58]  # aún no ha pasado un día
    g = _guardada(cliente, 10)
    g["guardado"] -= 25 * 3600
    cliente._escribir_guardada(10, json.dumps(g).encode())
    cliente.acta(10)
    assert _guardada(cliente, 10)["descuadre"] is None


def test_acta_ilegible_no_se_vuelve_a_pedir_enseguida(cliente, monkeypatch):
    llamadas = []

    def api(tipo, **k):
        llamadas.append(1)
        raise ValueError("raro")

    def pdf(raw):
        raise ValueError("no cuadra")
    monkeypatch.setattr(cliente, "_api", api)
    monkeypatch.setattr(acta_pdf, "pdf_a_json", pdf)
    cliente.acta(11)
    cliente.acta(11)
    assert len(llamadas) == 1 and cliente.pdf_pedidos == 1
