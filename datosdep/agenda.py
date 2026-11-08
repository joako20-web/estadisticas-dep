"""Agenda del finde: todos los partidos de la semana de la próxima jornada, de
todas las competiciones configuradas, por día y por liga.

Uso:
    rutas = agenda()                                   # todo, historia 9:16
    rutas = agenda(categorias=["nacional"], formato="post")
    rutas = agenda(region="Madrid")
"""
from __future__ import annotations

import tempfile
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict
from datetime import date, datetime, timedelta
from pathlib import Path

from datosdep.core.partido_jornada import etiqueta_dia, proximo_finde, rango_fechas
from datosdep.pipeline import cargar_config, es_descanso
from datosdep.render.nombres import equipo_corto
from datosdep.render.render import renderizar_slides
from datosdep.scraper.origen_a import cliente_para

ORDEN_CATEGORIA = {"nacional": 0, "copa": 1, "regional": 2}
# Filas que caben por imagen (una cabecera de liga cuenta como fila)
FILAS_POR_PAGINA = {"historia": 16, "post": 10}
ALTO_UTIL = {"historia": 1180, "post": 760}  # px disponibles para filas en cada formato
ALTO_FILA = {"historia": (66, 92), "post": (62, 78)}  # alto mínimo y máximo de fila


def _p(p) -> dict:
    d = asdict(p)
    d["fecha"] = p.fecha.isoformat() if p.fecha else None
    return d


def _ligas(categorias: list[str] | None, region: str | None) -> list[tuple[str, str, object, dict]]:
    out = []
    for comp, cfg in cargar_config()["competiciones"].items():
        cat = cfg.get("categoria", "nacional")
        if categorias and cat not in categorias:
            continue
        if region and cfg.get("region") != region:
            continue
        for grupo, id_grupo in cfg["grupos"].items():
            out.append((comp, grupo, id_grupo, cfg))
    return out


def _datos_grupo(comp: str, grupo: str, id_grupo, cfg: dict) -> dict:
    cliente = cliente_para(cfg)
    clas = cliente.clasificacion(id_grupo)
    competicion = cliente.competicion(id_grupo).filtrar(id_grupo, {f.equipo for f in clas})
    return {"comp": comp, "grupo": grupo, "cfg": cfg,
            "partidos": [d for p in competicion.partidos if not es_descanso(d := _p(p))],
            "escudos": {f.equipo: f.escudo for f in clas if f.escudo}}


def recopilar(categorias: list[str] | None = None, region: str | None = None) -> list[dict]:
    """Partidos y escudos de cada liga/grupo. Un hilo por plataforma (el origen A y cada
    región de OrigenB), y dentro de cada una en serie para no saturarla."""
    por_cliente: dict[int, list] = defaultdict(list)
    for comp, grupo, id_grupo, cfg in _ligas(categorias, region):
        por_cliente[id(cliente_para(cfg))].append((comp, grupo, id_grupo, cfg))

    def serie(tareas):
        res = []
        for t in tareas:
            try:
                res.append(_datos_grupo(*t))
            except Exception:
                continue  # una liga caída no tumba la agenda
        return res

    with ThreadPoolExecutor(max_workers=max(1, len(por_cliente))) as ex:
        return [d for lote in ex.map(serie, por_cliente.values()) for d in lote]


def datos_agenda(desde: date | None = None, categorias: list[str] | None = None,
                 region: str | None = None, hoy: date | None = None) -> dict:
    """Partidos de la semana (lunes-domingo) que contiene `desde` o, si no se da,
    la del próximo partido pendiente. Devuelve días -> ligas -> partidos."""
    grupos = recopilar(categorias, region)
    todos = [p for g in grupos for p in g["partidos"]]
    if desde:
        lunes = desde - timedelta(days=desde.weekday())
        ventana = (lunes, lunes + timedelta(days=6))
    else:
        ventana = proximo_finde(todos, hoy)
    if not ventana:
        return {"ventana": None, "dias": [], "sin_fecha": [], "escudos": {}, "total": 0}
    ini, fin = ventana

    escudos: dict[str, str] = {}
    dias: dict[date, dict] = defaultdict(lambda: defaultdict(list))
    sin_fecha: dict[str, list] = defaultdict(list)
    orden_liga: dict[str, tuple] = {}
    comps = list(cargar_config()["competiciones"])
    for g in grupos:
        cfg = g["cfg"]
        liga = cfg["nombre"] + ("" if g["grupo"] == "unico" else f" · Grupo {g['grupo']}")
        orden_liga[liga] = (ORDEN_CATEGORIA.get(cfg.get("categoria", "nacional"), 9), comps.index(g["comp"]), g["grupo"])
        escudos.update(g["escudos"])
        pendientes = [p for p in g["partidos"] if p["puntos_local"] is None]
        en_ventana = [p for p in pendientes if p["fecha"] and ini <= datetime.fromisoformat(p["fecha"]).date() <= fin]
        for p in en_ventana:
            dias[datetime.fromisoformat(p["fecha"]).date()][liga].append(p)
        # Sin fecha: solo si su jornada se juega esta semana en el mismo grupo
        jornadas = {p["jornada"] for p in en_ventana}
        sin_fecha[liga] += [p for p in pendientes if not p["fecha"] and p["jornada"] in jornadas]

    def ordenar(bloques: dict[str, list]) -> list[dict]:
        out = []
        for liga, ps in bloques.items():
            ps = sorted(ps, key=lambda p: p["fecha"] or "")
            # Primero las ligas principales (categoría y orden de config); dentro, por hora
            out.append({"liga": liga, "partidos": ps, "_orden": orden_liga[liga]})
        return [{k: v for k, v in b.items() if k != "_orden"} for b in sorted(out, key=lambda b: b["_orden"])]

    dias_out = [{"fecha": d.isoformat(), "titulo": etiqueta_dia(d), "ligas": ordenar(b)}
                for d, b in sorted(dias.items())]
    sin_out = ordenar({k: v for k, v in sin_fecha.items() if v})
    total = sum(len(b["partidos"]) for d in dias_out for b in d["ligas"]) + sum(len(b["partidos"]) for b in sin_out)
    return {"ventana": (ini.isoformat(), fin.isoformat()), "dias": dias_out, "sin_fecha": sin_out,
            "escudos": escudos, "total": total}


def _filas(ligas: list[dict]) -> int:
    return sum(1 + len(b["partidos"]) for b in ligas)


def _paginar(titulo: str, ligas: list[dict], capacidad: int) -> list[dict]:
    """Reparte ligas y partidos en páginas equilibradas de como mucho `capacidad`
    filas (la cabecera de cada liga cuenta como una fila). Evita páginas casi
    vacías y cabeceras huérfanas."""
    total_filas = _filas(ligas)
    n_paginas = max(1, -(-total_filas // capacidad))
    objetivo = -(-total_filas // n_paginas)  # filas por página si se reparte por igual
    paginas, actual, usadas = [], [], 0
    for b in ligas:
        restantes = list(b["partidos"])
        continuacion = False
        while restantes:
            hueco = objetivo - usadas - 1
            # Si lo que queda de la liga cabe en la página (hasta el máximo), no se parte
            if usadas + 1 + len(restantes) <= capacidad and len(restantes) - max(hueco, 0) <= 1:
                hueco = len(restantes)
            if hueco < 1 or (hueco < 2 and len(restantes) > 1):  # no dejar cabeceras huérfanas
                paginas.append(actual)
                actual, usadas = [], 0
                continue
            trozo, restantes = restantes[:hueco], restantes[hueco:]
            actual.append({"liga": b["liga"], "continua": continuacion, "partidos": trozo})
            usadas += 1 + len(trozo)
            continuacion = True
    if actual:
        paginas.append(actual)
    total = len(paginas)
    return [{"titulo": titulo, "pagina": f"{i}/{total}" if total > 1 else "", "bloques": pag}
            for i, pag in enumerate(paginas, 1)]


def _hora(p: dict) -> str:
    if not p["fecha"]:
        return "--:--"
    f = datetime.fromisoformat(p["fecha"])
    return "--:--" if (f.hour, f.minute) == (0, 0) else f.strftime("%H:%M")  # 00:00 = hora sin fijar


def slides_agenda(datos: dict, formato: str = "historia") -> tuple[list[dict], str]:
    """Slides de la agenda y texto de la etiqueta de cabecera ("Agenda · 10-11 oct")."""
    if not datos["dias"] and not datos["sin_fecha"]:
        return [], ""
    ini, fin = (date.fromisoformat(x) for x in datos["ventana"])
    capacidad = FILAS_POR_PAGINA[formato]
    paginas = []
    for d in datos["dias"]:
        paginas += _paginar(d["titulo"], d["ligas"], capacidad)
    if datos["sin_fecha"]:
        sin = [{**b, "liga": f"Por confirmar · {b['liga']}"} for b in datos["sin_fecha"]]
        if paginas and _filas(paginas[-1]["bloques"]) + _filas(sin) <= capacidad:
            paginas[-1]["bloques"] += sin  # cabe en la última página
        else:
            paginas += _paginar("Por confirmar", sin, capacidad)
    etiqueta = f"Agenda · {rango_fechas(ini, fin)}"
    slides = []
    for i, pag in enumerate(paginas, 1):
        for b in pag["bloques"]:
            for p in b["partidos"]:
                p["hora"] = _hora(p)
        slides.append({
            "tipo": "agenda", "clave": "agenda", **pag,
            "subtitulo": f"{datos['total']} partidos esta semana" if i == 1 else "",
            # Filas más altas cuando la página va holgada (sin pasar de un máximo)
            "alto_fila": max(ALTO_FILA[formato][0],
                             min(ALTO_FILA[formato][1], ALTO_UTIL[formato] // max(1, _filas(pag["bloques"])))),
        })
    return slides, etiqueta


def _renderizar(base: dict, slides: list[dict], destino: Path, formato: str, tema: str | None,
                etiqueta: str, pie: str) -> list[Path]:
    """renderizar_slides con cabecera propia (la agenda no es de una sola competición)."""
    base = {**base, "cabecera": {"nombre": etiqueta, "sub": pie, "grupo": None}}
    return renderizar_slides(base, slides, destino, formato, tema)


def agenda(desde: date | None = None, categorias: list[str] | None = None, region: str | None = None,
           formato: str = "historia", destino: Path | None = None, tema: str | None = None) -> list[Path]:
    """Imágenes de la agenda de la semana. Lista vacía si no hay partidos pendientes."""
    datos = datos_agenda(desde, categorias, region)
    slides, etiqueta = slides_agenda(datos, formato)
    if not slides:
        return []
    destino = destino or Path(tempfile.mkdtemp(prefix="agenda_"))
    base = {"competicion": next(iter(cargar_config()["competiciones"])), "grupo": "unico",
            "jornada": None, "temporada": cargar_config()["temporada"], "escudos": datos["escudos"]}
    filtro = region or (" · ".join(c.capitalize() for c in categorias) if categorias else "")
    pie = f"Agenda del finde{' · ' + filtro if filtro else ''} · {cargar_config()['temporada']}"
    return _renderizar(base, slides, destino, formato, tema, etiqueta, pie)


def texto_agenda(datos: dict) -> str:
    """Resumen en texto (para el post o para Telegram)."""
    lineas = []
    for d in datos["dias"]:
        lineas.append(f"📅 {d['titulo']}")
        for b in d["ligas"]:
            lineas.append(f"  {b['liga']}")
            for p in b["partidos"]:
                lineas.append(f"   {_hora(p)}  {equipo_corto(p['local'])} - {equipo_corto(p['visitante'])}")
    return "\n".join(lineas)
