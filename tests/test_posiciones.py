from datosdep.models import Jugador
from datosdep.scraper.origen_b import posiciones


def _j(*dorsales):
    return [Jugador(f"J{i}", d) for i, d in enumerate(dorsales)]


def test_camisetas_libres_se_usa_el_orden_del_acta():
    # Madrid: el 9.º de la lista es el medio melé aunque lleve el 12
    tit = _j(90, 28, 1, 5, 16, 56, 3, 7, 12, 54, 111, 13, 21, 62, 10)
    al = posiciones(tit, _j(20, 2, 23))
    assert [j.dorsal for j in al[:15]] == list(range(1, 16))
    assert al[8].camiseta == 12
    assert [j.dorsal for j in al[15:]] == [20, 17, 23]  # el suplente con el 2 no es titular


def test_dorsales_1_a_15_se_respetan_aunque_la_lista_venga_desordenada():
    tit = _j(1, 2, 3, 4, 5, 6, 8, 9, 10, 11, 12, 13, 14, 15, 7)
    al = posiciones(tit, [])
    assert [j.dorsal for j in al] == [1, 2, 3, 4, 5, 6, 8, 9, 10, 11, 12, 13, 14, 15, 7]
    assert all(j.camiseta is None for j in al)
