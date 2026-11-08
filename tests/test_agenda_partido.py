from dataclasses import asdict
from datetime import date
from pathlib import Path

import pytest

from datosdep import agenda as A
from datosdep.core import partido_jornada as PJ
from datosdep.scraper import parsers as P

FX = Path(__file__).parent / "fixtures"


def _p(p):
    d = asdict(p)
    d["fecha"] = p.fecha.isoformat() if p.fecha else None
    return d


@pytest.fixture(scope="module")
def dh():
    comp = P.estadisticas((FX / "estadisticas.html").read_bytes())
    clas = [asdict(f) for f in P.clasificacion((FX / "clasificacion.html").read_bytes())]
    return [_p(p) for p in comp.partidos], clas


def test_proximo_finde(dh):
    partidos, _ = dh
    assert PJ.proximo_finde(partidos, date(2026, 10, 7)) == (date(2026, 10, 5), date(2026, 10, 11))
    assert PJ.proximo_finde([], date(2026, 10, 7)) is None


def test_forma_y_medias(dh):
    partidos, clas = dh
    assert PJ.forma("VRAC QUESOS ENTREPINARES", partidos) == ["G", "G"]
    assert PJ.forma("CRC POZUELO RUGBY", partidos) == ["P", "P"]
    vrac = next(f for f in clas if f["equipo"] == "VRAC QUESOS ENTREPINARES")
    assert PJ.medias(vrac) == (31.0, 18.0)
    assert PJ.racha_actual(["P", "G", "G"]) == ("G", 2)


def test_elige_el_partido_grande(dh):
    partidos, clas = dh
    jornada3 = [p for p in partidos if p["jornada"] == 3]
    p, puntos, razones = PJ.elegir_cruce(jornada3, clas, partidos, zona_titulo=4)
    # 1º contra 2º, separados por un punto
    assert {p["local"], p["visitante"]} == {"VRAC QUESOS ENTREPINARES",
                                            "RECOLETAS SALUD CAJA RURAL BURGOS APAREJADORES"}
    assert "1º contra 2º" in razones and "separados por 1 punto" in razones
    assert puntos > 0


def test_cara_a_cara_y_derbi(dh):
    partidos, _ = dh
    previo = PJ.cara_a_cara("VRAC QUESOS ENTREPINARES", "HUESITOS LA VILA RUGBY CLUB", partidos)
    assert previo and previo["jornada"] == 1
    assert PJ.es_derbi("CRC POZUELO RUGBY", "OLIMPICO DE POZUELO CR") == "Pozuelo"
    assert PJ.es_derbi("CRC POZUELO RUGBY", "AMPO ORDIZIA") is None


def test_paginar_equilibrado():
    ligas = [{"liga": f"L{i}", "partidos": [{"id": j} for j in range(n)]} for i, n in enumerate([2, 1, 1, 2, 3, 4, 2, 1, 4, 4])]
    paginas = A._paginar("Sábado", ligas, 16)
    filas = [A._filas(p["bloques"]) for p in paginas]
    assert all(f <= 16 for f in filas)
    assert max(filas) - min(filas) <= 4  # reparto parejo, sin páginas casi vacías
    total = sum(len(b["partidos"]) for p in paginas for b in p["bloques"])
    assert total == 24
    # ninguna cabecera sin partidos
    assert all(b["partidos"] for p in paginas for b in p["bloques"])


def test_descanso_y_hora_sin_fijar():
    assert A.es_descanso({"local": "TORRELODONES RC", "visitante": "DESCANSO"})
    assert A._hora({"fecha": "2026-10-18T00:00:00"}) == "--:--"
    assert A._hora({"fecha": "2026-10-18T16:30:00"}) == "16:30"
