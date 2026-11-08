"""Minutos jugados a partir de los cambios y tarjetas del acta (caso real 17668: Recoletas - Santboiana)."""
import json
from pathlib import Path

from datosdep.minutos import minutos_jugador
from datosdep.scraper import acta_pdf

REC, SAN = "RECOLETAS SALUD CAJA RURAL BURGOS APAREJADORES", "UNIO ESPORTIVA SANTBOIANA"


def _extra():
    pg = json.loads((Path(__file__).parent / "fixtures" / "acta_pdf_17668_fragmentos.json").read_text(encoding="utf-8"))
    return json.loads(acta_pdf.acta_a_json([[tuple(x) for x in p] for p in pg]))["data"]["extra"]


def test_titular_que_juega_todo_el_partido():
    assert minutos_jugador(_extra(), REC, 5) == 80  # el 5 local no sale


def test_titular_sustituido():
    assert minutos_jugador(_extra(), REC, 3) == 50   # sale a los 50'
    assert minutos_jugador(_extra(), REC, 11) == 64  # sale a los 64'


def test_suplente_que_entra():
    assert minutos_jugador(_extra(), REC, 18) == 30   # entra a los 50' hasta el 80'
    assert minutos_jugador(_extra(), REC, 16) == 15   # entra a los 65'
    assert minutos_jugador(_extra(), SAN, 17) == 50   # entra a los 30'


def test_suplente_que_no_juega():
    ex = _extra()
    ex["cambios"] = [c for c in ex["cambios"] if not (c[0] == 0 and c[3] == 22)]  # el 22 local no entra
    assert minutos_jugador(ex, REC, 22) == 0


def test_amarilla_cuenta_solo_hasta_que_se_va_fuera():
    # el 17 local entra a los 65' y ve amarilla a los 72': 7' en el campo (luego, 10' fuera, hasta el final)
    assert minutos_jugador(_extra(), REC, 17) == 7


def test_amarilla_en_mitad_del_partido_resta_diez():
    ex = _extra()
    ex["tarjetas"] = [[0, 1200, 5, "amarilla"]]  # el 5 local, titular todo el partido, amarilla a los 20'
    assert minutos_jugador(ex, REC, 5) == 70


def test_roja_deja_al_jugador_fuera_el_resto():
    ex = _extra()
    ex["tarjetas"] = [[0, 1200, 5, "roja"]]
    assert minutos_jugador(ex, REC, 5) == 20


def test_cambio_temporal_vuelve_a_entrar():
    # el 2 sale a los 65' (entra el 17) y vuelve a los 72' (sale el 20): 65' + 8' = 73'
    assert minutos_jugador(_extra(), REC, 2) == 73


def test_sin_datos_o_equipo_desconocido():
    assert minutos_jugador(None, REC, 5) is None
    assert minutos_jugador(_extra(), "OTRO", 5) is None
