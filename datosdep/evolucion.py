"""Evolución de la clasificación jornada a jornada (gráfico de posiciones).

- el origen A: posiciones OFICIALES (clasificacion.php acepta &jornada=N).
- OrigenB: no da la tabla por jornada; se reconstruye con los resultados y
  los ensayos de las actas. Se prueban varias reglas de puntos de bonus y se usa
  la que reproduce exactamente la clasificación oficial actual (si ninguna cuadra
  exacto, la más cercana, y se avisa en "regla").
"""
from __future__ import annotations

from dataclasses import asdict
from pathlib import Path

from datosdep.pipeline import cargar_config
from datosdep.render.render import renderizar_slides
from datosdep.scraper import parsers
from datosdep.scraper.origen_a import OrigenA, cliente_para

# Reglas candidatas de bonus: (nombre, bonus ofensivo, bonus defensivo)
REGLAS = [
    ("4 ensayos / perder por 7 o menos", lambda ef, ec: ef >= 4, lambda dif: 0 < dif <= 7),
    ("4 ensayos / perder por 5 o menos", lambda ef, ec: ef >= 4, lambda dif: 0 < dif <= 5),
    ("3 ensayos más que el rival / perder por 5 o menos", lambda ef, ec: ef - ec >= 3, lambda dif: 0 < dif <= 5),
    ("3 ensayos más que el rival / perder por 7 o menos", lambda ef, ec: ef - ec >= 3, lambda dif: 0 < dif <= 7),
]


def tabla(partidos: list, ensayos: dict[int, tuple[int, int]], regla, hasta: int) -> list[dict]:
    """Clasificación reconstruida hasta la jornada `hasta` (victoria 4, empate 2, derrota 0 + bonus)."""
    _, bo, bd = regla
    t: dict[str, dict] = {}
    for p in partidos:
        if not p.jugado or not p.jornada or p.jornada > hasta:
            continue
        el, ev = ensayos.get(p.id, (0, 0))
        for eq, pf, pc, ef, ec in ((p.local, p.puntos_local, p.puntos_visitante, el, ev),
                                   (p.visitante, p.puntos_visitante, p.puntos_local, ev, el)):
            f = t.setdefault(eq, {"equipo": eq, "pt": 0, "tf": 0, "tc": 0})
            f["tf"] += pf
            f["tc"] += pc
            f["pt"] += 4 if pf > pc else 2 if pf == pc else 0
            f["pt"] += 1 if bo(ef, ec) else 0
            f["pt"] += 1 if bd(pc - pf) else 0
    filas = sorted(t.values(), key=lambda f: (-f["pt"], -(f["tf"] - f["tc"]), -f["tf"], f["equipo"]))
    for i, f in enumerate(filas, 1):
        f["posicion"] = i
    return filas


def _ensayos_por_partido(cliente, partidos) -> dict[int, tuple[int, int]]:
    out = {}
    for p in partidos:
        if not p.jugado:
            continue
        a = cliente.acta(p.id)
        tries = lambda eq: sum(1 for e in a.eventos if e.equipo == eq and e.tipo in ("ensayo", "ensayo_castigo"))
        out[p.id] = (tries(p.local), tries(p.visitante))
    return out


def posiciones(comp: str, grupo: str = "unico", cliente=None) -> dict:
    """{"jornadas": [1..n], "equipos": {equipo: [pos jornada1, ...]}, "regla": str, "final": [filas]}"""
    cfg = cargar_config()["competiciones"][comp]
    cliente = cliente or cliente_para(cfg)
    id_grupo = cfg["grupos"][grupo]
    oficial = cliente.clasificacion(id_grupo)
    competicion = cliente.competicion(id_grupo).filtrar(id_grupo, {f.equipo for f in oficial})
    jornadas = sorted({p.jornada for p in competicion.partidos if p.jugado and p.jornada})
    equipos: dict[str, list[int | None]] = {f.equipo: [] for f in oficial}

    if type(cliente) is OrigenA:
        ultima = jornadas[-1] if jornadas else 0
        for j in jornadas:
            params = {**cliente._params(id_grupo), "jornada": j}
            raw = cliente._get("clasificacion.php", params, cachear=j < ultima)
            pos = {f.equipo: f.posicion for f in parsers.clasificacion(raw)}
            for eq in equipos:
                equipos[eq].append(pos.get(eq))
        regla = "clasificación oficial de cada jornada"
    else:
        ensayos = _ensayos_por_partido(cliente, competicion.partidos)
        oficial_pt = {f.equipo: f.pt for f in oficial}
        ultima = jornadas[-1] if jornadas else 0

        def fallos(r):
            return sum(abs(f["pt"] - oficial_pt.get(f["equipo"], f["pt"])) for f in tabla(competicion.partidos, ensayos, r, ultima))

        mejor = min(REGLAS, key=fallos)
        regla = f"reconstruida ({mejor[0]})" + ("" if fallos(mejor) == 0 else " · aproximada: no cuadra exacto con la oficial")
        for j in jornadas:
            pos = {f["equipo"]: f["posicion"] for f in tabla(competicion.partidos, ensayos, mejor, j)}
            for eq in equipos:
                equipos[eq].append(pos.get(eq))
    return {"jornadas": jornadas, "equipos": equipos, "regla": regla,
            "final": [asdict(f) for f in oficial], "escudos": {f.equipo: f.escudo for f in oficial if f.escudo}}


def slide_evolucion(comp: str, grupo: str, evo: dict, destacar: list[str] | None = None) -> dict:
    """Gráfico de posiciones (bump chart) en SVG. Resalta `destacar` o, por defecto,
    los dos primeros y el último de la tabla actual."""
    final = evo["final"]
    n = len(final)
    destacar = destacar or [f["equipo"] for f in final[:2]] + ([final[-1]["equipo"]] if n > 3 else [])
    jornadas = evo["jornadas"]
    # Geometría del SVG (unidades CSS; el slide mide 1080 de ancho)
    ancho, alto = 680, 900  # el eje de jornadas va dentro (últimos 60)
    margen_x, margen_y = 40, 30
    paso_x = (ancho - 2 * margen_x) / max(1, len(jornadas) - 1)
    paso_y = (alto - 60 - 2 * margen_y) / max(1, n - 1)
    lineas = []
    for f in final:
        eq = f["equipo"]
        puntos = [(margen_x + i * paso_x, margen_y + (p - 1) * paso_y)
                  for i, p in enumerate(evo["equipos"].get(eq, [])) if p]
        if not puntos:
            continue
        lineas.append({
            "equipo": eq, "destacado": eq in destacar, "puntos": puntos,
            "path": " ".join(f"{'M' if i == 0 else 'L'}{x:.1f},{y:.1f}" for i, (x, y) in enumerate(puntos)),
            "final_y": puntos[-1][1], "posicion": f["posicion"],
        })
    # 1º acento, 2º color de texto, 3º color de texto en discontinuo (distinguibles en cualquier tema)
    estilos = [("var(--acento)", ""), ("var(--texto)", ""), ("var(--texto)", "14 12")]
    for i, eq in enumerate(destacar):
        for l in lineas:
            if l["equipo"] == eq:
                l["color"], l["guiones"] = estilos[i % len(estilos)]
    lineas.sort(key=lambda l: l["destacado"])  # las destacadas encima
    return {"tipo": "evolucion", "clave": "evolucion", "lineas": lineas, "jornadas": jornadas,
            "ancho": ancho, "alto": alto, "margen_x": margen_x, "margen_y": margen_y,
            "paso_x": paso_x, "paso_y": paso_y, "n": n, "regla": evo["regla"],
            "destacados": [l for l in lineas if l["destacado"]]}


def renderizar_evolucion(comp: str, grupo: str, destino: Path, formato: str = "post",
                         destacar: list[str] | None = None, tema: str | None = None, cliente=None) -> list[Path]:
    evo = posiciones(comp, grupo, cliente)
    if len(evo["jornadas"]) < 2:
        return []  # con una sola jornada no hay evolución que enseñar
    datos = {"competicion": comp, "grupo": grupo, "jornada": evo["jornadas"][-1],
             "temporada": cargar_config()["temporada"], "escudos": evo["escudos"]}
    return renderizar_slides(datos, [slide_evolucion(comp, grupo, evo, destacar)], destino, formato, tema)
