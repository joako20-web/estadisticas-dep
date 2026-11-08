from pathlib import Path

from datosdep import arbitros as A

FX = Path(__file__).parent / "fixtures"


def _r(arb, local, visitante, pl, pv, am=0, ro=0, temp=2526, fecha="2025-10-01"):
    return {"temporada": temp, "fecha": fecha, "local": local, "visitante": visitante,
            "club_l": local, "club_v": visitante, "pl": pl, "pv": pv, "arbitro": arb,
            "am_l": am, "ro_l": ro, "am_v": 0, "ro_v": 0}


def test_parse_previo():
    d = A.parse_previo((FX / "previo_17648.html").read_bytes())
    assert d["arbitro"] == "ALVARO GARCIA DE LAS MESTAS GARCIA"
    assert d["asistentes"] == ["LUIS FERNANDEZ DIAZ", "DANIEL PEREZ CEPA"]


def test_es_comp():
    assert A._es_comp("dh_masc", "DIVISIÓN DE HONOR MASCULINA")
    assert not A._es_comp("dh_masc", "DIVISIÓN DE HONOR B MASCULINA")
    assert A._es_comp("dh_fem", "Liga Iberdrola de Rugby")
    assert A._es_comp("dh_fem", "DIVISIÓN DE HONOR FEMENINA - LIGA IBERDROLA")
    assert not A._es_comp("dh_fem", "DIVISIÓN DE HONOR B FEMENINA")


def test_stats_y_minimo():
    regs = [_r("X", "A", "B", 20, 10, am=2) for _ in range(5)] + [_r("Y", "A", "B", 10, 20, am=9)]
    st = A.stats_arbitros(regs)
    assert [s["arbitro"] for s in st] == ["X"]  # Y solo tiene 1 partido: fuera
    assert st[0]["tarjetas_pp"] == 2.0 and st[0]["local_pct"] == 100


def test_cruces_y_curiosidades():
    regs = [_r("X", "A", "B", 30, 10, fecha=f"2025-10-0{i}") for i in range(1, 5)]
    regs += [_r("X", "C", "D", 10, 10)]
    equipos = {k: {"nombre": k, "escudo": "", "actual": True} for k in "ABCD"}
    cr = {(c["club"], c["arbitro"]): c for c in A.cruces(regs)}
    assert (cr[("A", "X")]["g"], cr[("B", "X")]["p"]) == (4, 4)
    assert ("C", "X") not in cr  # un solo partido: sin conclusiones
    titulares = [c["titular"] for c in A.curiosidades(regs, equipos)]
    assert any("B no gana" in t for t in titulares)
    assert any("talismán de A" in t for t in titulares)
