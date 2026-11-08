"""Imágenes especiales bajo pedido:

- Encuestas para historias (9:16) con hueco para el sticker de encuesta de la red:
  "Vota el MVP" (4 candidatos de la jornada) y "¿Quién gana?" (un partido de la próxima).
- XV de la temporada y MVP de la temporada (acumulado de notas de jornada).
"""
from __future__ import annotations

import json
from dataclasses import asdict
from datetime import datetime
from pathlib import Path

from datosdep.core import temporada as T
from datosdep.core.estadisticas import POSICIONES
from datosdep.pipeline import cargar_config, es_descanso, preparar_jornada
from datosdep.render.render import DIAS, FILAS_XV, MESES, fila_anotador, renderizar_slides
from datosdep.scraper.origen_a import cliente_para


def _datos_jornada(comp: str, grupo: str, jornada: int | None) -> dict:
    return json.loads(Path(preparar_jornada(comp, grupo, jornada)).read_text(encoding="utf-8"))


def _cabecera(datos: dict, jornada: int | None) -> dict:
    return {"competicion": datos["competicion"], "grupo": datos["grupo"], "jornada": jornada,
            "temporada": datos["temporada"], "escudos": datos.get("escudos", {})}


# ---------- Encuesta "Vota el MVP" ----------

def candidatos_mvp(datos: dict, n: int = 4) -> list[dict]:
    """Los n mejores de la jornada por nota (sin repetir jugador)."""
    vistos, out = set(), []
    for c in sorted(datos.get("candidatos_xv") or [], key=lambda x: -x["nota"]):
        if c["nombre"] in vistos:
            continue
        vistos.add(c["nombre"])
        detalle = fila_anotador(c)["detalle"]
        out.append({**c, "posicion": POSICIONES.get(c["dorsal"], ""),
                    "linea": " · ".join(x for x in (f"{c['puntos']} pts" if c["puntos"] else "", detalle) if x)})
        if len(out) == n:
            break
    if len(out) < n:  # sin actas con alineaciones: tirar de anotadores
        for a in datos.get("anotadores", []):
            if a["nombre"] not in vistos and len(out) < n:
                vistos.add(a["nombre"])
                out.append({**a, "posicion": "", "linea": f"{a['puntos']} pts · {fila_anotador(a)['detalle']}"})
    return out


def renderizar_vota_mvp(comp: str, grupo: str, destino: Path, jornada: int | None = None,
                        tema: str | None = None) -> list[Path]:
    datos = _datos_jornada(comp, grupo, jornada)
    cands = candidatos_mvp(datos)
    if len(cands) < 2:
        return []
    slide = {"tipo": "encuesta_mvp", "clave": "encuesta_mvp", "candidatos": cands,
             "letras": "ABCD", "jornada_n": datos["jornada"]}
    return renderizar_slides(_cabecera(datos, datos["jornada"]), [slide], destino, "historia", tema)


# ---------- Encuesta "¿Quién gana?" ----------

def partido_destacado(datos: dict) -> dict | None:
    """El partido más atractivo de la próxima jornada: dos equipos de arriba y
    parejos (suma de posiciones + doble de la diferencia, cuanto menor mejor)."""
    prox = (datos.get("proxima_jornada") or {}).get("partidos") or []
    pos = {f["equipo"]: f["posicion"] for f in datos.get("clasificacion", [])}
    n = len(pos) or 99
    candidatos = [p for p in prox if p["puntos_local"] is None and not es_descanso(p)]
    if not candidatos:
        return None
    return min(candidatos, key=lambda p: (pos.get(p["local"], n) + pos.get(p["visitante"], n)
                                          + 2 * abs(pos.get(p["local"], n) - pos.get(p["visitante"], n))))


def renderizar_quien_gana(comp: str, grupo: str, destino: Path, id_partido: int | None = None,
                          tema: str | None = None) -> list[Path]:
    datos = _datos_jornada(comp, grupo, None)
    prox = datos.get("proxima_jornada") or {}
    if id_partido:
        p = next((x for x in prox.get("partidos", []) if x["id"] == id_partido), None)
    else:
        p = partido_destacado(datos)
    if not p:
        return []
    tabla = {f["equipo"]: f for f in datos.get("clasificacion", [])}
    f = datetime.fromisoformat(p["fecha"]) if p["fecha"] else None
    cuando = f"{DIAS[f.weekday()]} {f.day} {MESES[f.month - 1]} · {f:%H:%M}" if f else "Fecha por confirmar"
    lados = []
    for eq in (p["local"], p["visitante"]):
        t = tabla.get(eq, {})
        lados.append({"equipo": eq, "posicion": t.get("posicion"), "pt": t.get("pt"),
                      "racha": t.get("racha", [])[-3:]})
    slide = {"tipo": "encuesta_partido", "clave": "encuesta_partido", "lados": lados,
             "cuando": cuando, "campo": (p.get("campo") or "").split("(")[0].strip()}
    return renderizar_slides(_cabecera(datos, prox.get("numero")), [slide], destino, "historia", tema)


# ---------- XV y MVP de la temporada ----------

def datos_temporada(comp: str, grupo: str = "unico") -> dict:
    cfg = cargar_config()["competiciones"][comp]
    cliente = cliente_para(cfg)
    por_jornada = T.lineas_temporada(comp, grupo, cliente)
    acum = T.acumular(por_jornada)
    id_grupo = cfg["grupos"][grupo]
    escudos = {f.equipo: f.escudo for f in cliente.clasificacion(id_grupo) if f.escudo}
    return {"jornadas": sorted(por_jornada), "acumulados": acum, "escudos": escudos}


def _cab_temporada(comp: str, grupo: str, escudos: dict) -> dict:
    return {"competicion": comp, "grupo": grupo, "jornada": None,
            "temporada": cargar_config()["temporada"], "escudos": escudos}


def renderizar_xv_temporada(comp: str, grupo: str, destino: Path, formato: str = "post",
                            tema: str | None = None) -> list[Path]:
    dt = datos_temporada(comp, grupo)
    n = len(dt["jornadas"])
    xv = T.xv_temporada(dt["acumulados"], n)
    if len(xv) < 15:
        return []
    xv_d = {str(d): asdict(ln) for d, ln in xv.items()}
    mvp = max(xv_d, key=lambda d: xv_d[d]["nota"])
    slide = {"tipo": "xv_temporada", "clave": "xv_temporada", "xv": xv_d, "mvp": int(mvp),
             "filas": [{"dorsales": d} for d in FILAS_XV], "jornadas": n}
    return renderizar_slides(_cab_temporada(comp, grupo, dt["escudos"]), [slide], destino, formato, tema)


def renderizar_mvp_temporada(comp: str, grupo: str, destino: Path, formato: str = "post",
                             tema: str | None = None) -> list[Path]:
    dt = datos_temporada(comp, grupo)
    top = T.mvp_temporada(dt["acumulados"], 7)
    if not top:
        return []
    filas = []
    for a in top:
        partes = [f"{a.partidos} partido{'s' if a.partidos != 1 else ''}"]
        if a.puntos:
            partes.append(f"{a.puntos} pts")
        if a.ensayos:
            partes.append(f"{a.ensayos} ensayo{'s' if a.ensayos != 1 else ''}")
        filas.append({"nombre": a.nombre, "equipo": a.equipo, "valor": round(a.nota),
                      "detalle": " · ".join(partes), "extra": POSICIONES.get(a.dorsal, "")})
    slide = {"tipo": "ranking", "clave": "mvp_temporada", "titulo": "MVP de la temporada",
             "sup": f"Valoración acumulada · {len(dt['jornadas'])} jornadas", "unidad": "VAL", "filas": filas}
    return renderizar_slides(_cab_temporada(comp, grupo, dt["escudos"]), [slide], destino, formato, tema)
