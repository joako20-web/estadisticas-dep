"""Estadísticas de árbitros de la División de Honor y la Liga Iberdrola (el origen A).

- El árbitro de cada partido sale de previo.php?id_partido=N (sirve para partidos
  jugados de cualquier temporada y para los pendientes ya designados).
- Las tarjetas salen del acta (eventos amarilla / roja20 / roja), ya cacheada.
- Se usan varias temporadas (desde 2023/24) para tener muestra; los equipos se
  emparejan entre temporadas por el id de club del escudo de el origen A
  (.../afiliacion_clubs/<id>/...), que no cambia con el patrocinador.

Funciones públicas (todas devuelven list[Path], vacía si no hay muestra suficiente):
- renderizar_tarjeteros(comp, destino, formato="post", tema=None)
- renderizar_curiosidades(comp, destino, formato="post", tema=None)
- renderizar_designaciones(comp, destino, formato="post", tema=None)
- renderizar_equipo(comp, equipo, destino, formato="post", tema=None)
Datos: registros(comp), stats_arbitros(regs), cruces(regs), curiosidades(regs), designaciones(comp)
"""
from __future__ import annotations

import json
import re
import unicodedata
from collections import defaultdict
from pathlib import Path

from bs4 import BeautifulSoup

from datosdep.pipeline import RAIZ, cargar_config
from datosdep.render import nombres
from datosdep.scraper.origen_a import AccesoRestringido, OrigenA, compartido
from datosdep.scraper.texto import decodificar, limpiar

COMPS = ("dh_masc", "dh_fem")
TEMPORADAS = (2627, 2526, 2425, 2324)  # la primera es la actual
# En data/ (se sube al repo): las temporadas pasadas no cambian y así no hay que bajarlas
CACHE = RAIZ / "data" / "arbitros"

MIN_PARTIDOS_ARBITRO = 5  # para entrar en rankings de árbitros
MIN_CRUCE = 3  # partidos de un equipo con un árbitro para sacar conclusiones


def _norm(s: str) -> str:
    s = unicodedata.normalize("NFKD", s.upper())
    return "".join(c for c in s if not unicodedata.combining(c)).strip()


def _es_comp(comp: str, nombre: str) -> bool:
    n = _norm(nombre)
    if comp == "dh_masc":
        return n == "DIVISION DE HONOR MASCULINA"
    return n.startswith("DIVISION DE HONOR FEMENINA") or n == "LIGA IBERDROLA DE RUGBY"


def _temp_txt(temp: int) -> str:
    return f"20{str(temp)[:2]}/{str(temp)[2:]}"


# ---------------------------------------------------------------- parsers

def parse_previo(raw: bytes) -> dict:
    """Árbitro principal (y asistentes) de previo.php."""
    s = BeautifulSoup(decodificar(raw), "lxml")
    datos: dict = {"arbitro": None, "asistentes": []}
    for div in s.find_all("div", class_=re.compile(r"^div\d+$")):  # div1 árbitro, div2/3 asistentes
        partes = [limpiar(d.get_text(" ")) for d in div.find_all("div", recursive=False)]
        if len(partes) < 2 or not partes[1]:
            continue
        if partes[0] == "ARBITRO" and not datos["arbitro"]:
            datos["arbitro"] = partes[1]
        elif partes[0] == "ARBITRO ASISTENTE":
            datos["asistentes"].append(partes[1])
    return datos


def _club(escudo: str) -> str | None:
    m = re.search(r"afiliacion_clubs/(\d+)/", escudo or "")
    return m.group(1) if m else None


# ---------------------------------------------------------------- descarga

def grupos(comp: str, temp: int, cliente: OrigenA | None = None) -> list[int]:
    """Grupos (todas las fases) de esa competición en esa temporada."""
    if temp == TEMPORADAS[0]:
        return list(cargar_config()["competiciones"][comp]["grupos"].values())
    ruta = CACHE / f"grupos_{comp}_{temp}.json"
    if ruta.exists():
        return json.loads(ruta.read_text())
    c = cliente or compartido()
    base = {"seleccion": 0, "id_ambito": 0, "id_temp": temp, "id_territorial": 9999}
    out: list[int] = []
    for id_comp, nombre in c._opciones(base, "competiciones"):
        if not _es_comp(comp, nombre):
            continue
        pc = {**base, "id_competicion": id_comp}
        for id_fase, _ in c._opciones(pc, "fase") or [(0, "")]:
            pf = {**pc, "id_fase": id_fase} if id_fase else pc
            out += [g for g, _ in c._opciones(pf, "grupo")]
    ruta.parent.mkdir(parents=True, exist_ok=True)
    ruta.write_text(json.dumps(sorted(set(out))))
    return sorted(set(out))


def _arbitro(c: OrigenA, id_partido: int, jugado: bool) -> str | None:
    raw = c._get("previo.php", {"id_partido": id_partido}, cachear=jugado)
    return parse_previo(raw)["arbitro"]


def _tarjetas(c: OrigenA, id_partido: int, local: str, visitante: str) -> dict:
    acta = c.acta(id_partido)
    if not acta.eventos and c.bloqueado_ahora():
        raise AccesoRestringido("acta no disponible")  # no guardar tarjetas a cero como si fueran reales
    t = {"am_l": 0, "ro_l": 0, "am_v": 0, "ro_v": 0}
    for e in acta.eventos:
        lado = "l" if e.equipo == acta.local else "v" if e.equipo == acta.visitante else None
        if not lado:
            continue
        if e.tipo == "amarilla":
            t[f"am_{lado}"] += 1
        elif e.tipo in ("roja", "roja20"):
            t[f"ro_{lado}"] += 1
    return t


def _registros_temporada(comp: str, temp: int, c: OrigenA) -> tuple[list[dict], dict]:
    """Partidos jugados con árbitro y tarjetas + {nombre_equipo: (club, escudo)}."""
    vistos, regs, clubs = set(), [], {}
    for g in grupos(comp, temp, c):
        try:
            clas = c.clasificacion(g)
        except AttributeError:  # fases de eliminatoria: no hay tabla
            clas = []
        for f in clas:
            if f.escudo:
                clubs[f.equipo] = (_club(f.escudo), f.escudo)
        for p in c.competicion(g).partidos:
            if p.id in vistos or p.grupo not in (g, None) or not p.jugado:
                continue
            vistos.add(p.id)
            arb = _arbitro(c, p.id, True)
            if not arb:
                continue
            regs.append({
                "temporada": temp, "id": p.id, "fecha": p.fecha.isoformat() if p.fecha else None,
                "ronda": p.ronda or f"J{p.jornada}", "local": p.local, "visitante": p.visitante,
                "pl": p.puntos_local, "pv": p.puntos_visitante, "arbitro": arb,
                **_tarjetas(c, p.id, p.local, p.visitante),
            })
    return regs, clubs


def registros(comp: str, cliente: OrigenA | None = None) -> tuple[list[dict], dict]:
    """Todos los partidos con árbitro desde 2023/24 y el mapa de clubes.

    Devuelve (registros, equipos) con equipos = {club_id: {"nombre", "escudo"}},
    donde el nombre es el más reciente del club. Cada registro lleva club_l/club_v.
    Las temporadas pasadas se cachean en disco para siempre.
    """
    c = cliente or compartido()
    todos, nombres_club = [], {}
    for temp in TEMPORADAS:
        ruta = CACHE / f"{comp}_{temp}.json"
        if temp != TEMPORADAS[0] and ruta.exists():
            regs, clubs = json.loads(ruta.read_text())
        else:
            try:
                regs, clubs = _registros_temporada(comp, temp, c)
            except AccesoRestringido:
                if not ruta.exists():
                    raise
                regs, clubs = json.loads(ruta.read_text())  # el origen A bloquea: último dato guardado
            else:
                ruta.parent.mkdir(parents=True, exist_ok=True)
                ruta.write_text(json.dumps([regs, clubs], ensure_ascii=False, separators=(",", ":")))
        for r in regs:
            r["club_l"] = (clubs.get(r["local"]) or [None])[0] or f"n:{r['local']}"
            r["club_v"] = (clubs.get(r["visitante"]) or [None])[0] or f"n:{r['visitante']}"
        for nombre, (club, escudo) in clubs.items():
            if club and club not in nombres_club:  # la temporada más reciente manda
                nombres_club[club] = {"nombre": nombre, "escudo": escudo, "actual": temp == TEMPORADAS[0]}
        todos += regs
    for r in todos:  # equipos sin escudo: se identifican por nombre
        for lado in ("l", "v"):
            k = r[f"club_{lado}"]
            if k.startswith("n:") and k not in nombres_club:
                nombres_club[k] = {"nombre": k[2:], "escudo": "", "actual": False}
    return todos, nombres_club


# ---------------------------------------------------------------- estadísticas

def stats_arbitros(regs: list[dict], minimo: int = MIN_PARTIDOS_ARBITRO) -> list[dict]:
    acc: dict[str, dict] = defaultdict(lambda: {"partidos": 0, "amarillas": 0, "rojas": 0,
                                                 "puntos": 0, "gana_local": 0, "temporadas": set()})
    for r in regs:
        a = acc[r["arbitro"]]
        a["partidos"] += 1
        a["amarillas"] += r["am_l"] + r["am_v"]
        a["rojas"] += r["ro_l"] + r["ro_v"]
        a["puntos"] += r["pl"] + r["pv"]
        a["gana_local"] += r["pl"] > r["pv"]
        a["temporadas"].add(r["temporada"])
    out = []
    for nombre, a in acc.items():
        if a["partidos"] < minimo:
            continue
        n = a["partidos"]
        out.append({"arbitro": nombre, "partidos": n, "amarillas": a["amarillas"], "rojas": a["rojas"],
                    "tarjetas_pp": round((a["amarillas"] + a["rojas"]) / n, 2),
                    "puntos_pp": round(a["puntos"] / n, 1),
                    "local_pct": round(100 * a["gana_local"] / n),
                    "temporadas": len(a["temporadas"])})
    return sorted(out, key=lambda x: (-x["tarjetas_pp"], -x["partidos"]))


def cruces(regs: list[dict], minimo: int = MIN_CRUCE) -> list[dict]:
    """Récord de cada club con cada árbitro (con al menos `minimo` partidos)."""
    acc: dict[tuple[str, str], list[str]] = defaultdict(list)
    for r in sorted(regs, key=lambda r: r["fecha"] or ""):
        for lado, pf, pc in (("l", r["pl"], r["pv"]), ("v", r["pv"], r["pl"])):
            acc[(r[f"club_{lado}"], r["arbitro"])].append("G" if pf > pc else "E" if pf == pc else "P")
    out = []
    for (club, arb), res in acc.items():
        if len(res) >= minimo:
            out.append({"club": club, "arbitro": arb, "partidos": len(res), "g": res.count("G"),
                        "e": res.count("E"), "p": res.count("P"), "secuencia": res})
    return out


def curiosidades(regs: list[dict], equipos: dict, n: int = 4) -> list[dict]:
    """Las combinaciones más llamativas, siempre con su tamaño de muestra."""
    out = []
    cr = cruces(regs)
    # Primero equipos que juegan esta temporada (más interesantes para la cuenta)
    actuales = [x for x in cr if equipos.get(x["club"], {}).get("actual")]
    cr = actuales if any(x["g"] == 0 for x in actuales) else cr
    sin_ganar = sorted((x for x in cr if x["g"] == 0), key=lambda x: (-x["partidos"], -x["p"]))
    for x in sin_ganar[:2]:
        out.append({"tipo": "sin_ganar", "club": x["club"], "arbitro": x["arbitro"],
                    "titular": f"Con {_arb(x['arbitro'])}, {_eq(equipos, x['club'])} no gana",
                    "cifra": f"{x['g']}-{x['e']}-{x['p']}", "pie": f"{x['partidos']} partidos: ganados, empatados y perdidos"})
    pleno = sorted((x for x in (actuales or cr) if x["p"] == 0 and x["e"] == 0 and x["partidos"] >= MIN_CRUCE + 1),
                   key=lambda x: -x["partidos"])
    for x in pleno[:1]:
        out.append({"tipo": "talisman", "club": x["club"], "arbitro": x["arbitro"],
                    "titular": f"{_arb(x['arbitro'])}, el talismán de {_eq(equipos, x['club'])}",
                    "cifra": f"{x['g']}-0-0", "pie": f"{x['partidos']} partidos, todos ganados"})
    st = stats_arbitros(regs)
    if st:
        t = st[0]
        out.append({"tipo": "tarjetero", "club": "", "arbitro": t["arbitro"],
                    "titular": f"{_arb(t['arbitro'])}, el más tarjetero",
                    "cifra": _num(t["tarjetas_pp"]), "pie": f"tarjetas por partido en {t['partidos']} partidos"})
        local = sorted((x for x in st if x["partidos"] >= 8), key=lambda x: -x["local_pct"])
        if local and local[0]["local_pct"] >= 70:
            l = local[0]
            out.append({"tipo": "local", "club": "", "arbitro": l["arbitro"],
                        "titular": f"Con {_arb(l['arbitro'])} gana el de casa",
                        "cifra": f"{l['local_pct']} %", "pie": f"victorias locales en {l['partidos']} partidos"})
    return out[:n]


def designaciones(comp: str, cliente: OrigenA | None = None) -> dict | None:
    """Árbitros designados para la próxima jornada y el récord de cada equipo con ellos."""
    c = cliente or compartido()
    regs, equipos = registros(comp, c)
    cr = {(x["club"], x["arbitro"]): x for x in cruces(regs, minimo=1)}
    id_grupo = cargar_config()["competiciones"][comp]["grupos"]["unico"]
    clas = c.clasificacion(id_grupo)
    club_de = {f.equipo: _club(f.escudo) or f"n:{f.equipo}" for f in clas}
    pend = [p for p in c.competicion(id_grupo).partidos if not p.jugado and p.jornada]
    if not pend:
        return None
    jornada = min(p.jornada for p in pend)
    filas = []
    for p in sorted((p for p in pend if p.jornada == jornada), key=lambda p: p.fecha or 0):
        arb = _arbitro(c, p.id, False)
        fila = {"local": p.local, "visitante": p.visitante, "arbitro": arb,
                "fecha": p.fecha.isoformat() if p.fecha else None}
        for lado, eq in (("l", p.local), ("v", p.visitante)):
            x = cr.get((club_de.get(eq), arb)) if arb else None
            fila[f"rec_{lado}"] = f"{x['g']}-{x['e']}-{x['p']}" if x else "sin partidos"
        filas.append(fila)
    return {"jornada": jornada, "filas": filas}


# ---------------------------------------------------------------- formato

def _arb(nombre: str) -> str:
    return nombres.titulo(nombre)


def _eq(equipos: dict, club: str) -> str:
    return nombres.equipo_corto(equipos.get(club, {}).get("nombre", club))


def _n(n: int, palabra: str) -> str:
    return f"{n} {palabra}{'' if n == 1 else 's'}"


def _num(x: float) -> str:
    return f"{x:.1f}".replace(".", ",")


def _periodo() -> str:
    return f"desde {_temp_txt(TEMPORADAS[-1])}"


# ---------------------------------------------------------------- render

def _datos(comp: str, escudos: dict) -> dict:
    return {"competicion": comp, "grupo": "unico", "jornada": None,
            "temporada": cargar_config()["temporada"], "escudos": escudos}


def _escudos(equipos: dict) -> dict:
    return {v["nombre"]: v["escudo"] for v in equipos.values() if v.get("escudo")}


def _render(comp, slides, escudos, destino, formato, tema):
    from datosdep.render.render import renderizar_slides

    return renderizar_slides(_datos(comp, escudos), slides, Path(destino), formato, tema) if slides else []


def renderizar_tarjeteros(comp: str, destino, formato: str = "post", tema: str | None = None) -> list[Path]:
    regs, equipos = registros(comp)
    st = stats_arbitros(regs)[:7]
    if not st:
        return []
    filas = [{"nombre": _arb(x["arbitro"]), "valor": _num(x["tarjetas_pp"]),
              "detalle": f"{x['partidos']} partidos, {_n(x['amarillas'], 'amarilla')}, {_n(x['rojas'], 'roja')}",
              "extra": f"{x['puntos_pp']:.0f} puntos por partido, gana el local el {x['local_pct']} %"} for x in st]
    slide = {"tipo": "arbitros", "clave": "arbitros_tarjetas", "titulo": "Árbitros más tarjeteros",
             "sup": f"Tarjetas por partido, {_periodo()} (mínimo {MIN_PARTIDOS_ARBITRO} partidos)",
             "unidad": "", "filas": filas}
    return _render(comp, [slide], _escudos(equipos), destino, formato, tema)


def renderizar_curiosidades(comp: str, destino, formato: str = "post", tema: str | None = None) -> list[Path]:
    regs, equipos = registros(comp)
    cur = curiosidades(regs, equipos)
    if not cur:
        return []
    for x in cur:
        x["equipo"] = equipos.get(x["club"], {}).get("nombre", "") if x["club"] else ""
    slide = {"tipo": "arbitros_datos", "clave": "arbitros_datos", "titulo": "Árbitros: datos curiosos",
             "sup": f"Partidos {_periodo()}, mínimo {MIN_CRUCE} con el mismo árbitro", "datos": cur}
    return _render(comp, [slide], _escudos(equipos), destino, formato, tema)


def renderizar_designaciones(comp: str, destino, formato: str = "post", tema: str | None = None) -> list[Path]:
    d = designaciones(comp)
    if not d or not any(f["arbitro"] for f in d["filas"]):
        return []
    _, equipos = registros(comp)
    escudos = _escudos(equipos)
    clas = compartido().clasificacion(cargar_config()["competiciones"][comp]["grupos"]["unico"])
    escudos.update({f.equipo: f.escudo for f in clas if f.escudo})
    for f in d["filas"]:
        f["arbitro"] = _arb(f["arbitro"]) if f["arbitro"] else "Sin designar"
    slide = {"tipo": "arbitros_designa", "clave": "arbitros_designaciones",
             "titulo": f"Quién pita la jornada {d['jornada']}",
             "sup": f"Récord de cada equipo con ese árbitro ({_periodo()}): ganados, empatados y perdidos",
             "filas": d["filas"]}
    return _render(comp, [slide], escudos, destino, formato, tema)


def renderizar_equipo(comp: str, equipo: str, destino, formato: str = "post", tema: str | None = None) -> list[Path]:
    """Récord de un equipo con cada árbitro (búsqueda por nombre aproximado)."""
    regs, equipos = registros(comp)
    q = _norm(equipo)
    club = next((k for k, v in equipos.items()
                 if q in _norm(v["nombre"]) or q in _norm(nombres.equipo_corto(v["nombre"]))), None)
    if not club:
        return []
    filas = sorted((x for x in cruces(regs, minimo=2) if x["club"] == club),
                   key=lambda x: (-x["partidos"], -x["g"]))[:8]
    if not filas:
        return []
    nombre = equipos[club]["nombre"]
    slide = {"tipo": "arbitros", "clave": "arbitros_equipo", "titulo": f"{nombres.equipo_corto(nombre)} y sus árbitros",
             "sup": f"Ganados, empatados y perdidos con cada árbitro, {_periodo()} (mínimo 2 partidos)",
             "unidad": "", "equipo": nombre,
             "filas": [{"nombre": _arb(x["arbitro"]), "valor": f"{x['g']}-{x['e']}-{x['p']}",
                        "detalle": f"{x['partidos']} partidos", "extra": ""} for x in filas]}
    return _render(comp, [slide], _escudos(equipos), destino, formato, tema)
