"""Lógica pura (sin red ni render) de la agenda y del partido de la jornada.

- proximo_finde: ventana de fechas de la próxima jornada a partir de los partidos pendientes.
- puntuar_cruce: cuánto "engancha" un partido, con razones legibles.
- forma / medias / cara_a_cara: datos de la previa de un equipo.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta

from datosdep.render import nombres

DIAS = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo"]
MESES = ["ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sep", "oct", "nov", "dic"]

# Palabras que no sirven para detectar derbis por ciudad
_GENERICAS = {"RUGBY", "CLUB", "UNION", "UNIÓN", "CR", "RC", "C.R.", "R.C.", "DE", "DEL", "LA", "EL",
              "LOS", "LAS", "SAN", "SANT", "UNIVERSIDAD", "UNIVERSITARIO", "DEPORTIVO", "CD", "AD",
              "TALDEA", "SENIOR", "FEMENINO", "MASCULINO", "TERRITORIAL", "DHB", "DH", "XV", "C",
              "B", "A", "FEM", "EMERGING", "SALUD", "CAJA", "RURAL", "QUESOS"}


def _fecha(p: dict) -> datetime | None:
    f = p.get("fecha")
    if isinstance(f, datetime):
        return f
    return datetime.fromisoformat(f) if f else None


def proximo_finde(partidos: list[dict], hoy: date | None = None) -> tuple[date, date] | None:
    """(lunes, domingo) de la semana del próximo partido pendiente con fecha.

    Si el primer partido pendiente cae en lunes (p. ej. aplazado de la jornada
    anterior), se toma igualmente su semana: la agenda cubre lunes-domingo.
    """
    hoy = hoy or date.today()
    fechas = sorted(f.date() for p in partidos
                    if (f := _fecha(p)) and f.date() >= hoy and p.get("puntos_local") is None)
    if not fechas:
        return None
    lunes = fechas[0] - timedelta(days=fechas[0].weekday())
    return lunes, lunes + timedelta(days=6)


def etiqueta_dia(d: date) -> str:
    return f"{DIAS[d.weekday()]} {d.day} {MESES[d.month - 1]}"


def rango_fechas(desde: date, hasta: date) -> str:
    if desde.month == hasta.month:
        return f"{desde.day}-{hasta.day} {MESES[hasta.month - 1]}"
    return f"{desde.day} {MESES[desde.month - 1]} - {hasta.day} {MESES[hasta.month - 1]}"


# ---------------- Partido de la jornada ----------------

def forma(equipo: str, partidos: list[dict], n: int = 5) -> list[str]:
    """Últimos n resultados del equipo (más antiguo primero): 'G', 'E' o 'P'."""
    jugados = sorted((p for p in partidos if p.get("puntos_local") is not None
                      and equipo in (p["local"], p["visitante"])),
                     key=lambda p: (p["jornada"], p.get("fecha") or ""))
    out = []
    for p in jugados[-n:]:
        propios, ajenos = ((p["puntos_local"], p["puntos_visitante"]) if p["local"] == equipo
                           else (p["puntos_visitante"], p["puntos_local"]))
        out.append("G" if propios > ajenos else "E" if propios == ajenos else "P")
    return out


def racha_actual(resultados: list[str]) -> tuple[str, int]:
    if not resultados:
        return "", 0
    ultimo, n = resultados[-1], 0
    for r in reversed(resultados):
        if r != ultimo:
            break
        n += 1
    return ultimo, n


def medias(fila: dict) -> tuple[float, float]:
    """Puntos a favor y en contra por partido (de la fila de clasificación)."""
    pj = fila.get("pj") or 0
    if not pj:
        return 0.0, 0.0
    return round(fila["tf"] / pj, 1), round(fila["tc"] / pj, 1)


def cara_a_cara(a: str, b: str, partidos: list[dict]) -> dict | None:
    """Último partido jugado entre a y b esta temporada."""
    previos = [p for p in partidos if p.get("puntos_local") is not None
               and {p["local"], p["visitante"]} == {a, b}]
    if not previos:
        return None
    return max(previos, key=lambda p: (p["jornada"], p.get("fecha") or ""))


def _palabras_ciudad(nombre: str) -> set[str]:
    return {w for w in nombre.upper().replace("-", " ").split()
            if len(w) > 3 and w not in _GENERICAS and "." not in w}


def es_derbi(a: str, b: str) -> str | None:
    """Palabra compartida significativa (ciudad o club) entre los dos nombres."""
    comunes = _palabras_ciudad(a) & _palabras_ciudad(b)
    return sorted(comunes)[0].title() if comunes else None


def puntuar_cruce(p: dict, por_equipo: dict[str, dict], n_equipos: int,
                  partidos: list[dict], zona_titulo: int = 0) -> tuple[float, list[str]]:
    """Puntuación de interés de un cruce y razones legibles (de más a menos peso)."""
    fl, fv = por_equipo.get(p["local"]), por_equipo.get(p["visitante"])
    if not fl or not fv or not n_equipos:
        return 0.0, []
    razones: list[tuple[float, str]] = []
    pl, pv = fl["posicion"], fv["posicion"]
    jugados = max(fl.get("pj", 0), fv.get("pj", 0))
    peso_tabla = 1.0 if jugados >= 3 else 0.6 if jugados >= 1 else 0.2  # al principio pesa poco

    alto = ((n_equipos - pl) + (n_equipos - pv)) / (2 * max(1, n_equipos - 1))
    razones.append((40 * alto * peso_tabla, f"{pl}º contra {pv}º"))
    dif_pos = abs(pl - pv)
    if dif_pos <= 2:
        razones.append(((20 - 6 * dif_pos) * peso_tabla, "vecinos en la tabla"))
    dif_pts = abs(fl["pt"] - fv["pt"])
    if jugados and dif_pts <= 3:
        razones.append((15 * peso_tabla, "empatados a puntos" if dif_pts == 0 else f"separados por {dif_pts} punto{'s' if dif_pts != 1 else ''}"))
    if 1 in (pl, pv):
        razones.append((10 * peso_tabla, "con el líder en juego"))
    if zona_titulo and pl <= zona_titulo and pv <= zona_titulo:
        razones.append((12 * peso_tabla, "duelo en zona de play-off"))
    if pl >= n_equipos - 1 and pv >= n_equipos - 1 and n_equipos >= 6:
        razones.append((10 * peso_tabla, "duelo por la permanencia"))
    for eq in (p["local"], p["visitante"]):
        tipo, n = racha_actual(forma(eq, partidos))
        if tipo == "G" and n >= 3:
            razones.append((4 + n, f"{nombres.equipo_corto(eq)} lleva {n} victorias seguidas"))
    if (d := es_derbi(p["local"], p["visitante"])):
        razones.append((14, f"derbi ({d})"))
    if cara_a_cara(p["local"], p["visitante"], partidos):
        razones.append((3, "revancha"))
    razones.sort(key=lambda r: -r[0])
    return round(sum(r[0] for r in razones), 1), [r[1] for r in razones if r[0] >= 3]


def elegir_cruce(pendientes: list[dict], clasificacion: list[dict], partidos: list[dict],
                 zona_titulo: int = 0) -> tuple[dict, float, list[str]] | None:
    por_equipo = {f["equipo"]: f for f in clasificacion}
    mejores = []
    for i, p in enumerate(pendientes):
        puntos, razones = puntuar_cruce(p, por_equipo, len(clasificacion), partidos, zona_titulo)
        mejores.append((puntos, -i, p, razones))  # a igualdad, el primero del calendario
    if not mejores:
        return None
    puntos, _, p, razones = max(mejores, key=lambda x: (x[0], x[1]))
    return p, puntos, razones
