"""Rankings de estadísticas: ensayadores, pateadores, tarjetas, banquillo y equipos.

Lógica pura (sin red ni render). Entradas:
- lineas de la jornada: dicts de LineaJugador (core.estadisticas).
- resumen de temporada: {id_partido: [[nombre, equipo, puntos, ensayos, conversiones,
  golpes, drops, amarillas, rojas, dorsal], ...]} (pipeline.resumen_temporada).
- clasificación: dicts de FilaClasificacion.

Cada ranking de jugadores devuelve filas {nombre, equipo, valor, detalle, extra}, el
mismo formato que usa la plantilla de ranking (más `rival` en las de jornada).
"""
from __future__ import annotations

from collections import defaultdict

# Índices del formato de resumen_partidos.json
NOMBRE, EQUIPO, PUNTOS, ENSAYOS, CONV, GOLPES, DROPS, AMARILLAS, ROJAS, DORSAL = range(10)
CAMPOS_RESUMEN = 10
SUPLENTE_DESDE = 16  # dorsales 16-23: banquillo


def _n(n: int, singular: str, plural: str) -> str:
    return f"{n} {singular if n == 1 else plural}"


def pie(conversiones: int, golpes: int, drops: int) -> int:
    """Puntos al pie: transformaciones (2) + golpes de castigo (3) + drops (3)."""
    return 2 * conversiones + 3 * golpes + 3 * drops


def desglose_pie(conversiones: int, golpes: int, drops: int) -> str:
    partes = []
    if conversiones:
        partes.append(_n(conversiones, "transf.", "transf."))
    if golpes:
        partes.append(_n(golpes, "golpe", "golpes"))
    if drops:
        partes.append(_n(drops, "drop", "drops"))
    return " · ".join(partes)


def desglose_tarjetas(amarillas: int, rojas: int) -> str:
    partes = []
    if amarillas:
        partes.append(_n(amarillas, "amarilla", "amarillas"))
    if rojas:
        partes.append(_n(rojas, "roja", "rojas"))
    return " · ".join(partes)


def _fila(nombre, equipo, valor, detalle="", rival="") -> dict:
    """`rival` va en bruto (nombre oficial); el render lo acorta."""
    return {"nombre": nombre, "equipo": equipo, "valor": valor, "detalle": detalle, "rival": rival}


def _rojas(tarjetas: list[str]) -> int:
    return sum(t in ("roja", "roja20") for t in tarjetas)


# ---------- Jornada (a partir de las líneas de cada jugador) ----------

def ensayadores_jornada(lineas: list[dict], top: int = 7) -> list[dict]:
    con = sorted((ln for ln in lineas if ln["ensayos"]), key=lambda ln: (-ln["ensayos"], -ln["puntos"], ln["nombre"]))
    return [_fila(ln["nombre"], ln["equipo"], ln["ensayos"], _n(ln["puntos"], "punto", "puntos"),
                  ln.get("rival", "")) for ln in con[:top]]


def pateadores_jornada(lineas: list[dict], top: int = 7) -> list[dict]:
    con = [ln for ln in lineas if pie(ln["conversiones"], ln["golpes"], ln["drops"])]
    con.sort(key=lambda ln: (-pie(ln["conversiones"], ln["golpes"], ln["drops"]), ln["nombre"]))
    return [_fila(ln["nombre"], ln["equipo"], pie(ln["conversiones"], ln["golpes"], ln["drops"]),
                  desglose_pie(ln["conversiones"], ln["golpes"], ln["drops"]),
                  ln.get("rival", "")) for ln in con[:top]]


# ---------- Temporada (a partir del resumen de partidos) ----------

def acumular(resumen: dict[str, list]) -> dict[tuple[str, str], dict]:
    """Totales de temporada por (jugador, equipo)."""
    tot: dict[tuple[str, str], dict] = defaultdict(lambda: defaultdict(int))
    for jugadores in resumen.values():
        for j in jugadores:
            if len(j) < CAMPOS_RESUMEN:
                continue
            t = tot[(j[NOMBRE], j[EQUIPO])]
            t["partidos"] += 1
            for clave, i in (("puntos", PUNTOS), ("ensayos", ENSAYOS), ("conversiones", CONV), ("golpes", GOLPES),
                             ("drops", DROPS), ("amarillas", AMARILLAS), ("rojas", ROJAS)):
                t[clave] += j[i]
            if j[DORSAL] >= SUPLENTE_DESDE:
                t["banquillo_puntos"] += j[PUNTOS]
                t["banquillo_ensayos"] += j[ENSAYOS]
    return tot


def ensayadores_temporada(tot: dict, top: int = 7) -> list[dict]:
    con = sorted(((k, t) for k, t in tot.items() if t["ensayos"]),
                 key=lambda x: (-x[1]["ensayos"], -x[1]["puntos"], x[0][0]))
    return [_fila(n, e, t["ensayos"], _n(t["puntos"], "punto", "puntos")) for (n, e), t in con[:top]]


def pateadores_temporada(tot: dict, top: int = 7) -> list[dict]:
    def p(t):
        return pie(t["conversiones"], t["golpes"], t["drops"])

    con = sorted(((k, t) for k, t in tot.items() if p(t)), key=lambda x: (-p(x[1]), x[0][0]))
    return [_fila(n, e, p(t), desglose_pie(t["conversiones"], t["golpes"], t["drops"])) for (n, e), t in con[:top]]


def disciplina_temporada(tot: dict, top: int = 7) -> list[dict]:
    """Jugadores con más tarjetas (a igualdad, primero quien tiene más rojas)."""
    con = [(k, t) for k, t in tot.items() if t["amarillas"] or t["rojas"]]
    con.sort(key=lambda x: (-(x[1]["amarillas"] + x[1]["rojas"]), -x[1]["rojas"], x[0][0]))
    return [_fila(n, e, t["amarillas"] + t["rojas"], desglose_tarjetas(t["amarillas"], t["rojas"]))
            for (n, e), t in con[:top]]


def banquillo_temporada(tot: dict, top: int = 7) -> list[dict]:
    """Los suplentes (dorsal 16-23) que más puntos han sumado saliendo desde el banquillo."""
    con = [(k, t) for k, t in tot.items() if t["banquillo_puntos"]]
    con.sort(key=lambda x: (-x[1]["banquillo_puntos"], -x[1]["banquillo_ensayos"], x[0][0]))
    return [_fila(n, e, t["banquillo_puntos"],
                  _n(t["banquillo_ensayos"], "ensayo", "ensayos") if t["banquillo_ensayos"] else "")
            for (n, e), t in con[:top]]


def tarjetas_equipos(tot: dict) -> dict[str, dict]:
    out: dict[str, dict] = defaultdict(lambda: {"amarillas": 0, "rojas": 0})
    for (_, equipo), t in tot.items():
        out[equipo]["amarillas"] += t["amarillas"]
        out[equipo]["rojas"] += t["rojas"]
    return out


# ---------- Equipos (clasificación + tarjetas) ----------

def bloques_equipos(clasificacion: list[dict], tot: dict, top: int = 3) -> list[dict]:
    """Cuatro mini-rankings de equipos: ataque, defensa, ensayos y tarjetas."""
    jugados = [f for f in clasificacion if f["pj"]]
    if not jugados:
        return []

    def bloque(titulo, filas, valor, unidad, reverso=False):
        orden = sorted(filas, key=lambda f: (valor(f) if reverso else -valor(f), f["posicion"]))
        return {"titulo": titulo, "unidad": unidad,
                "filas": [{"equipo": f["equipo"], "valor": valor(f)} for f in orden[:top]]}

    bloques = [
        bloque("Mejor ataque", jugados, lambda f: f["tf"], "pts a favor"),
        bloque("Mejor defensa", jugados, lambda f: f["tc"], "pts en contra", reverso=True),
        bloque("Más ensayos", jugados, lambda f: f["ef"], "ensayos"),
    ]
    tarj = tarjetas_equipos(tot)
    con_tarjetas = [{"equipo": e, "posicion": 0, "t": v["amarillas"] + v["rojas"]} for e, v in tarj.items()
                    if v["amarillas"] + v["rojas"]]
    if con_tarjetas:
        bloques.append(bloque("Más tarjetas", con_tarjetas, lambda f: f["t"], "tarjetas"))
    else:
        bloques.append(bloque("Más bonus", jugados, lambda f: f["bo"] + f["bd"], "bonus"))
    return bloques


def calcular(lineas: list[dict], resumen: dict[str, list], clasificacion: list[dict]) -> dict:
    """Todos los rankings para guardarlos en el JSON de la jornada."""
    tot = acumular(resumen)
    return {
        "ensayadores": ensayadores_jornada(lineas),
        "pateadores": pateadores_jornada(lineas),
        "ensayadores_t": ensayadores_temporada(tot),
        "pateadores_t": pateadores_temporada(tot),
        "disciplina": disciplina_temporada(tot),
        "banquillo": banquillo_temporada(tot),
        "equipos": bloques_equipos(clasificacion, tot),
    }
