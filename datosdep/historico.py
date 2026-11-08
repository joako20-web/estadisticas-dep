"""Histórico de temporadas anteriores en el origen A (solo competiciones nacionales).

- campeones(comp)                -> palmarés de las últimas temporadas (final jugada)
- palmares(comp, formato)        -> [Path]
- hace_un_ano(comp, jornada, formato) -> [Path]  (resultados de esa jornada la temporada pasada)
- cara_a_cara(cand_a, cand_b, formato) -> [Path] (candidatos de datosdep.fichas.buscar_equipo)
- partidos_cara_a_cara(cand_a, cand_b) -> datos sin renderizar

Los equipos se emparejan entre temporadas por el id de club de el origen A (el número
de la ruta de su escudo), que no cambia aunque cambie el patrocinador:
"DH VRAC QUESOS ENTREPINARES" (2025/26) y "VRAC QUESOS ENTREPINARES" (2026/27)
son el club 23. Lo histórico no cambia y se cachea para siempre.
"""
from __future__ import annotations

import json
import re
import tempfile
from datetime import datetime
from pathlib import Path

from datosdep.fichas import CACHE, _club, indice_equipos, norm
from datosdep.pipeline import cargar_config
from datosdep.render.render import MESES, renderizar_slides
from datosdep.scraper.origen_a import compartido
from datosdep.scraper import parsers

# Temporadas con competiciones senior publicadas (2022/23 solo tiene escuelas)
TEMPORADAS = [(2526, "2025/26"), (2425, "2024/25"), (2324, "2023/24")]
HISTORICO = CACHE / "historico"
# Tipos (claves de config) por género, para no mezclar el equipo masculino y el
# femenino de un mismo club en el cara a cara
MASCULINAS = ["dh_masc", "dh_elite", "copa"]
FEMENINAS = ["dh_fem"]
EXCLUIR = ("promocion", "supercopa", "ascenso", "cobertura", "sevens", " 7s", "torneo", "festival",
           "campeonato", "reina", "prueba")


def tipo_competicion(nombre: str) -> str | None:
    """Clave de config equivalente a un nombre de competición de el origen A de cualquier temporada."""
    n = f" {norm(nombre)} "
    if any(x in n for x in EXCLUIR):
        return None
    if "copa del rey" in n or "copa sm el rey" in n:
        return "copa"
    if " m23 " in n:
        return "m23"
    if "honor b" in n:
        return "dhb_fem" if "femenin" in n else "dhb_masc"
    if "elite" in n:
        return "dh_elite"
    if "liga iberdrola" in n or ("honor" in n and "femenin" in n):
        return "dh_fem"
    if "division de honor" in n:
        return "dh_masc"
    return None


def _cliente():
    return compartido()


def _opciones(params: dict, select: str) -> list[tuple[int, str]]:
    return _cliente()._opciones(params, select)


def datos_temporada(id_temp: int, tipo: str) -> dict | None:
    """Partidos, clubes y escudos de una competición en una temporada pasada (cacheado)."""
    ruta = HISTORICO / f"{id_temp}_{tipo}.json"
    if ruta.exists():
        datos = json.loads(ruta.read_text(encoding="utf-8"))
        return datos or None
    base = {"seleccion": 0, "id_ambito": 0, "id_temp": id_temp, "id_territorial": 9999}
    comp = next(((i, n) for i, n in _opciones(base, "competiciones") if tipo_competicion(n) == tipo), None)
    datos: dict = {}
    if comp:
        pc = {**base, "id_competicion": comp[0]}
        grupos = []
        for id_fase, fase in _opciones(pc, "fase") or [(0, "")]:
            pf = {**pc, "id_fase": id_fase} if id_fase else pc
            grupos += [{"id": g, "nombre": n, "fase": fase} for g, n in _opciones(pf, "grupo")]
        cli = _cliente()
        partidos: dict[int, dict] = {}
        clubes: dict[str, int] = {}
        escudos: dict[str, str] = {}
        con_partidos: set = set()
        for g in grupos:
            if g["id"] not in con_partidos:
                raw = cli._get("mostrar_estadisticas.php", cli._params(g["id"]), cachear=True)
                for p in parsers.estadisticas(raw).partidos:
                    partidos[p.id] = {
                        "id": p.id, "jornada": p.jornada, "ronda": p.ronda, "grupo": p.grupo or g["id"],
                        "fecha": p.fecha.isoformat() if p.fecha else None, "local": p.local,
                        "visitante": p.visitante, "pl": p.puntos_local, "pv": p.puntos_visitante,
                    }
                    con_partidos.add(p.grupo or g["id"])
            if "FINAL" in (g["fase"] or "").upper():
                continue  # las eliminatorias no tienen tabla
            try:
                raw = cli._get("clasificacion.php", cli._params(g["id"]), cachear=True)
                for f in parsers.clasificacion(raw):
                    if _club(f.escudo):
                        clubes[f.equipo] = _club(f.escudo)
                        escudos[f.equipo] = f.escudo
            except Exception:
                pass
        datos = {"id_temp": id_temp, "temporada": dict(TEMPORADAS)[id_temp], "tipo": tipo,
                 "competicion": comp[1], "grupos": grupos, "partidos": list(partidos.values()),
                 "clubes": clubes, "escudos": escudos}
    HISTORICO.mkdir(parents=True, exist_ok=True)
    ruta.write_text(json.dumps(datos, ensure_ascii=False), encoding="utf-8")
    return datos or None


# ---------- nombres actuales ----------

def _actuales(comp: str | None = None) -> dict[int, dict]:
    """Club -> equipo actual (prefiere la competición dada y las nacionales)."""
    out: dict[int, dict] = {}
    for c in indice_equipos():
        if not c.get("club"):
            continue
        prioridad = (c["comp"] != comp, c["categoria"] != "nacional")
        if c["club"] not in out or prioridad < out[c["club"]]["_p"]:
            out[c["club"]] = {**c, "_p": prioridad}
    return out


def _parecido(nombre: str, tipo: str) -> dict | None:
    """Equipo actual nacional del mismo género cuyo nombre contiene todas las palabras del histórico."""
    from datosdep.fichas import _puntuar

    femenino = tipo in FEMENINAS or "fem" in tipo
    nombre = nombre.replace("?", "Ñ")  # el origen A guarda a veces la Ñ como "?"
    mejores, vistos = [], set()
    for c in indice_equipos():
        if c["categoria"] == "regional" or ("fem" in c["comp"]) != femenino or norm(c["equipo"]) in vistos:
            continue
        vistos.add(norm(c["equipo"]))  # el mismo equipo en liga y Copa cuenta una vez
        p = _puntuar(nombre, [c["equipo"].replace("?", "Ñ")], [c["equipo"]])
        if p >= 80:
            # a igual puntuación, el que menos palabras añade ("...APAREJADORES" antes que "...APAREJADORES M23")
            sobran = len(set(norm(c["equipo"]).split()) - set(norm(nombre).split()))
            mejores.append(((p, -sobran), c))
    mejores.sort(key=lambda x: x[0], reverse=True)
    if not mejores or (len(mejores) > 1 and mejores[0][0] == mejores[1][0]):
        return None  # ninguno o empate: mejor no adivinar
    return mejores[0][1]


def _presentar(nombre: str, datos: dict, actuales: dict[int, dict], escudos: dict) -> str:
    """Nombre a mostrar: el actual del club si existe (con su escudo), si no el histórico."""
    club = datos["clubes"].get(nombre)
    actual = actuales.get(club) if club else _parecido(nombre, datos.get("tipo", ""))
    if actual:
        escudos.setdefault(actual["equipo"], actual["escudo"])
        return actual["equipo"]
    if nombre in datos["escudos"]:
        escudos.setdefault(nombre, datos["escudos"][nombre])
    return nombre


# ---------- palmarés ----------

def _final(datos: dict) -> dict | None:
    finales = [p for p in datos["partidos"] if norm(p["ronda"]) == "final" and p["pl"] is not None]
    return max(finales, key=lambda p: p["fecha"] or "") if finales else None


def campeones(comp: str) -> list[dict]:
    out = []
    actuales = _actuales(comp)
    for id_temp, etiqueta in TEMPORADAS:
        datos = datos_temporada(id_temp, comp)
        f = _final(datos) if datos else None
        if not f or f["pl"] == f["pv"]:
            continue
        escudos: dict = {}
        gana_local = f["pl"] > f["pv"]
        campeon = _presentar(f["local"] if gana_local else f["visitante"], datos, actuales, escudos)
        sub = _presentar(f["visitante"] if gana_local else f["local"], datos, actuales, escudos)
        out.append({"temporada": etiqueta, "campeon": campeon, "subcampeon": sub,
                    "marcador": f"{max(f['pl'], f['pv'])}-{min(f['pl'], f['pv'])}", "escudos": escudos})
    return out


def _render(comp: str, slide: dict, escudos: dict, temporada: str, formato: str, destino: Path | None) -> list[Path]:
    datos = {"competicion": comp, "grupo": "unico", "jornada": None, "temporada": temporada, "escudos": escudos}
    return renderizar_slides(datos, [slide], destino or Path(tempfile.mkdtemp(prefix="historico_")), formato)


def palmares(comp: str, formato: str = "post", destino: Path | None = None) -> list[Path]:
    lista = campeones(comp)
    if not lista:
        return []
    escudos = {k: v for c in lista for k, v in c["escudos"].items()}
    titulos: dict[str, int] = {}
    for c in lista:
        titulos[c["campeon"]] = titulos.get(c["campeon"], 0) + 1
    slide = {"tipo": "palmares", "clave": "palmares", "filas": lista, "titulos": titulos,
             "nombre": cargar_config()["competiciones"][comp]["nombre"]}
    return _render(comp, slide, escudos, "Palmarés", formato, destino)


# ---------- hace un año ----------

def datos_hace_un_ano(comp: str, jornada: int) -> dict | None:
    datos = datos_temporada(TEMPORADAS[0][0], comp)
    if not datos:
        return None
    # Primera fase de liga: el grupo de jornadas numeradas con más partidos en esa jornada
    candidatos = [p for p in datos["partidos"] if p["jornada"] == jornada and not p["ronda"] and p["pl"] is not None]
    if not candidatos:
        return None
    por_grupo: dict = {}
    for p in candidatos:
        por_grupo.setdefault(p["grupo"], []).append(p)
    nombres_grupo = {g["id"]: g["nombre"] for g in datos["grupos"]}
    primera = [g for g in por_grupo if "1" in (nombres_grupo.get(g) or "") and "2" not in (nombres_grupo.get(g) or "")]
    grupo = (primera or sorted(por_grupo, key=lambda g: -len(por_grupo[g])))[0]
    actuales = _actuales(comp)
    escudos: dict = {}
    partidos = []
    for p in sorted(por_grupo[grupo], key=lambda p: p["fecha"] or ""):
        partidos.append({"local": _presentar(p["local"], datos, actuales, escudos),
                         "visitante": _presentar(p["visitante"], datos, actuales, escudos),
                         "puntos_local": p["pl"], "puntos_visitante": p["pv"]})
    mayor = max(partidos, key=lambda p: abs(p["puntos_local"] - p["puntos_visitante"]))
    f = _final(datos)
    campeon = None
    if f and f["pl"] != f["pv"]:
        campeon = _presentar(f["local"] if f["pl"] > f["pv"] else f["visitante"], datos, actuales, escudos)
    fechas = sorted(p["fecha"] for p in por_grupo[grupo] if p["fecha"])
    cuando = ""
    if fechas:
        d = datetime.fromisoformat(fechas[0])
        cuando = f"{d.day} {MESES[d.month - 1]} {d.year}"
    return {"temporada": datos["temporada"], "jornada": jornada, "partidos": partidos, "mayor": mayor,
            "campeon": campeon, "cuando": cuando, "escudos": escudos}


def hace_un_ano(comp: str, jornada: int, formato: str = "post", destino: Path | None = None) -> list[Path]:
    d = datos_hace_un_ano(comp, jornada)
    if not d:
        return []
    slide = {"tipo": "hace_un_ano", "clave": "hace_un_ano", **d}
    return _render(comp, slide, d["escudos"], d["temporada"], formato, destino)


# ---------- cara a cara ----------

def partidos_cara_a_cara(cand_a: dict, cand_b: dict) -> dict | None:
    """Enfrentamientos entre dos equipos (de buscar_equipo) en temporadas pasadas y en la actual."""
    club_a, club_b = cand_a.get("club"), cand_b.get("club")
    if not club_a or not club_b or club_a == club_b:
        return None
    femenino = any("fem" in c["comp"] for c in (cand_a, cand_b))
    tipos = FEMENINAS if femenino else MASCULINAS
    comps = cargar_config()["competiciones"]
    escudos = {cand_a["equipo"]: cand_a["escudo"], cand_b["equipo"]: cand_b["escudo"]}
    lista = []

    def anadir(p: dict, datos: dict, etiqueta: str, corto: str):
        cl, cv = datos["clubes"].get(p["local"]), datos["clubes"].get(p["visitante"])
        if {cl, cv} != {club_a, club_b} or p["pl"] is None:
            return
        local_es_a = cl == club_a
        lista.append({
            "temporada": etiqueta, "competicion": corto,
            "fase": f"{corto} · " + (re.sub(r"(?i)\s+de\s+final", "", p["ronda"]) or (f"J{p['jornada']}" if p["jornada"] else "")),
            "local": cand_a["equipo"] if local_es_a else cand_b["equipo"],
            "visitante": cand_b["equipo"] if local_es_a else cand_a["equipo"],
            "pl": p["pl"], "pv": p["pv"], "fecha": p["fecha"] or "",
        })

    # Temporada actual
    cli = _cliente()
    for tipo in tipos:
        cfg = comps.get(tipo)
        if not cfg or cfg.get("fuente") == "origen_b":
            continue
        for g, id_grupo in cfg["grupos"].items():
            try:
                clas = cli.clasificacion(id_grupo)
                clubes = {f.equipo: _club(f.escudo) for f in clas}
                if not {club_a, club_b} <= set(clubes.values()):
                    continue
                for p in cli.competicion(id_grupo).filtrar(id_grupo, set(clubes)).partidos:
                    d = {"id": p.id, "jornada": p.jornada, "ronda": p.ronda, "fecha": p.fecha.isoformat() if p.fecha else None,
                         "local": p.local, "visitante": p.visitante, "pl": p.puntos_local, "pv": p.puntos_visitante}
                    anadir(d, {"clubes": clubes}, cargar_config()["temporada"], cfg["corto"])
            except Exception:
                continue
    # Temporadas pasadas
    for id_temp, etiqueta in TEMPORADAS:
        for tipo in tipos:
            datos = datos_temporada(id_temp, tipo)
            if not datos:
                continue
            for p in datos["partidos"]:
                anadir(p, datos, etiqueta, comps.get(tipo, {}).get("corto", tipo))
    if not lista:
        return {"a": cand_a, "b": cand_b, "partidos": [], "ga": 0, "gb": 0, "e": 0, "escudos": escudos}
    lista.sort(key=lambda x: x["fecha"], reverse=True)
    ga = sum(1 for x in lista if (x["pl"] > x["pv"]) == (x["local"] == cand_a["equipo"]) and x["pl"] != x["pv"])
    e = sum(1 for x in lista if x["pl"] == x["pv"])
    return {"a": cand_a, "b": cand_b, "partidos": lista, "ga": ga, "gb": len(lista) - ga - e, "e": e,
            "escudos": escudos}


def cara_a_cara(cand_a: dict, cand_b: dict, formato: str = "post", destino: Path | None = None) -> list[Path]:
    d = partidos_cara_a_cara(cand_a, cand_b)
    if not d or not d["partidos"]:
        return []
    slide = {"tipo": "cara_a_cara", "clave": "cara_a_cara", **d, "partidos": d["partidos"][:6],
             "total": len(d["partidos"])}
    comp = cand_a["comp"] if cand_a["categoria"] == "nacional" else cand_b["comp"]
    return _render(comp, slide, d["escudos"], "Histórico", formato, destino)
