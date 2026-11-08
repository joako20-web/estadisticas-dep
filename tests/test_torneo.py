from pathlib import Path

from datosdep import torneo
from datosdep.render.render import con_zonas
from datosdep.scraper import parsers as P

FX = Path(__file__).parent / "fixtures"


def test_cuadro_real_temporada_pasada():
    c = P.estadisticas((FX / "estadisticas_2526_dh_fasefinal.html").read_bytes())
    rondas = torneo.cuadro_real([torneo._p(p) for p in c.partidos if p.ronda])
    assert [r["nombre"] for r in rondas] == ["Cuartos", "Semifinales", "Final"]
    assert [len(r["cruces"]) for r in rondas] == [4, 2, 1]
    assert rondas[-1]["cruces"][0]["gana"] == "DH VRAC QUESOS ENTREPINARES"
    # Los dos primeros cuartos alimentan la primera semifinal
    semi1 = rondas[1]["cruces"][0]
    ganadores_cuartos = {rondas[0]["cruces"][i]["gana"] for i in (0, 1)}
    assert {semi1["local"], semi1["visitante"]} == ganadores_cuartos


def test_cuadro_provisional():
    clas = [{"posicion": i, "equipo": f"E{i}"} for i in range(1, 11)]
    r = torneo.cuadro_provisional(clas, [[1, 4], [2, 3]])
    assert (r[0]["cruces"][0]["local"], r[0]["cruces"][0]["visitante"]) == ("E1", "E4")


def test_zonas():
    clas = [{"posicion": i, "equipo": f"E{i}"} for i in range(1, 9)]
    filas, leyenda = con_zonas(clas, "dh_fem", "unico")
    assert [f["zona"] for f in filas] == ["titulo"] * 4 + ["", ""] + ["promocion", "descenso"]
    assert [z["color"] for z in leyenda] == ["titulo", "promocion", "descenso"]
