from collections import Counter
from pathlib import Path

import pytest

from datosdep.core import estadisticas as E
from datosdep.scraper import parsers as P
from datosdep.scraper.texto import decodificar, limpiar

FX = Path(__file__).parent / "fixtures"


def leer(nombre: str) -> bytes:
    return (FX / nombre).read_bytes()


@pytest.fixture(scope="module")
def comp():
    return P.estadisticas(leer("estadisticas.html"))


def actas_jornada(comp, n):
    return [(p, P.acta(leer(f"acta_{p.id}.html"), p.id)) for p in comp.jornada(n)]


def test_estadisticas(comp):
    assert len(comp.partidos) == 90
    assert comp.ultima_jornada_jugada() == 2
    p = comp.partidos[0]
    assert (p.id, p.jornada, p.local, p.puntos_local, p.puntos_visitante) == (
        17643, 1, "VRAC QUESOS ENTREPINARES", 40, 24
    )
    assert all(p.jugado for p in comp.jornada(2))
    assert not any(p.jugado for p in comp.jornada(3))
    assert comp.jugadores[0].nombre == "SANTIAGO IGNACIO MANSILLA"
    assert comp.jugadores[0].puntos == 42


@pytest.mark.parametrize("jornada", [1, 2])
def test_eventos_suman_el_marcador(comp, jornada):
    for p, a in actas_jornada(comp, jornada):
        assert (a.local, a.visitante) == (p.local, p.visitante)
        assert a.marcador_por_eventos() == (p.puntos_local, p.puntos_visitante)
        assert sorted(j.dorsal for j in a.alineacion_local)[:15] == list(range(1, 16))
        assert sum(j.tantos for j in a.alineacion_local) <= p.puntos_local


def test_tantos_por_jugador_cuadran_con_eventos(comp):
    for p, a in actas_jornada(comp, 2):
        lineas = {(ln.equipo, ln.nombre): ln for ln in E.lineas_partido(p, a)}
        for equipo, alineacion in ((a.local, a.alineacion_local), (a.visitante, a.alineacion_visitante)):
            for j in alineacion:
                assert lineas[(equipo, j.nombre)].puntos == j.tantos, j.nombre


def test_mojibake():
    assert limpiar("MARÃ\x87AL  CARRERAS") == "MARÇAL CARRERAS"
    assert decodificar(b"BAR\xc7A RUGBI") == "BARÇA RUGBI"
    assert decodificar("PEQUEÑO".encode()) == "PEQUEÑO"


def test_clasificacion():
    filas = P.clasificacion(leer("clasificacion.html"))
    assert len(filas) == 10
    assert filas[0].equipo == "VRAC QUESOS ENTREPINARES"
    assert (filas[0].posicion, filas[0].pt, filas[0].pj) == (1, 9, 2)
    assert filas[2].equipo == "VULCANIZADOS ALVAREZ EL SALVADOR"


def test_clasificacion_grupo_sin_tabla():
    # Grupo que el origen ha dejado vacío al rehacer las fases: sin tabla, sin error
    html = b"<html><body><h2>CLASIFICACION GENERAL</h2><p>TABLA FASE PRINCIPAL</p></body></html>"
    assert P.clasificacion(html) == []


def test_xv_ideal(comp):
    lineas = [ln for p, a in actas_jornada(comp, 2) for ln in E.lineas_partido(p, a)]
    xv = E.xv_ideal(lineas)
    assert sorted(xv) == list(range(1, 16))
    assert max(Counter(ln.equipo for ln in xv.values()).values()) <= 4
    assert len({ln.nombre for ln in xv.values()}) == 15


def test_ids_partidos_jornada():
    assert P.ids_partidos_jornada(leer("jornada_2.html")) == [17648, 17649, 17650, 17651, 17652]


def test_acta_sin_alineaciones_no_rompe():
    a = P.acta(b"<html><body><div class='local'></div></body></html>", 1)
    assert a.local == "" and a.visitante == "" and a.eventos == []


def test_acta_json_equivale_al_html():
    fx = Path(__file__).parent / "fixtures"
    h = P.acta((fx / "acta_17643.html").read_bytes(), 17643)
    j = P.acta_json((fx / "acta_17643.json").read_bytes(), 17643)
    clave = lambda e: (e.minuto, e.tipo, e.equipo, e.jugador, e.marcador)
    assert (h.local, h.visitante) == (j.local, j.visitante)
    assert sorted(map(clave, h.eventos), key=str) == sorted(map(clave, j.eventos), key=str)
    assert h.alineacion_local == j.alineacion_local and h.alineacion_visitante == j.alineacion_visitante
    assert j.marcador_por_eventos() == (40, 24)


def test_acta_json_sin_datos_falla_claro():
    with pytest.raises(ValueError):
        P.acta_json(b'{"status":false,"message":"id_partido requerido"}', 1)
