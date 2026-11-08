"""Junta los datos de una jornada en un JSON editable (data/.../jNN.json)."""
from __future__ import annotations

import io
import json
from dataclasses import asdict
from pathlib import Path


from datosdep.core import datos as D
from datosdep.models import JugadorTemporada
from datosdep.core import rankings as R
from datosdep.core import estadisticas as E
from datosdep.scraper.origen_a import OrigenA, cliente_para

FOTO_MIN_PX = 600


def elegir_foto_portada(candidatos: list[E.LineaJugador], cliente: OrigenA) -> dict | None:
    """Primer candidato con una foto de calidad suficiente para la portada.

    Muchas fotos de el origen A son de carnet (153 px); esas no sirven a sangre.
    """
    from PIL import Image

    vistos = set()
    for ln in candidatos:
        if not ln.foto or ln.foto in vistos:
            continue
        vistos.add(ln.foto)
        try:
            ancho, alto = Image.open(io.BytesIO(cliente.imagen(ln.foto))).size
        except Exception:
            continue
        if min(ancho, alto) >= FOTO_MIN_PX:
            return {"url": ln.foto, "jugador": ln.nombre, "equipo": ln.equipo, "motivo": ""}
    return None

from datosdep.rutas import CONFIG, DATA, RAIZ, leer_yaml  # noqa: F401  (se reexportan)


def cargar_config() -> dict:
    return leer_yaml(CONFIG / "competiciones.yaml")


def ruta_jornada(comp: str, grupo: str, jornada: int) -> Path:
    temporada = cargar_config()["temporada"].replace("/", "-")
    return DATA / temporada / comp / grupo / f"j{jornada:02d}.json"


def es_descanso(p) -> bool:
    """Fila de jornada de descanso: OrigenB la publica como un partido contra «DESCANSO»."""
    local, visitante = (p["local"], p["visitante"]) if isinstance(p, dict) else (p.local, p.visitante)
    return "DESCANSO" in f"{local} {visitante}".upper()


def separar_descansos(partidos: list) -> tuple[list, list[str]]:
    """(partidos de verdad, equipos que descansan)."""
    reales, descansan = [], []
    for p in partidos:
        if es_descanso(p):
            local, visitante = (p["local"], p["visitante"]) if isinstance(p, dict) else (p.local, p.visitante)
            descansan.append(visitante if "DESCANSO" in local.upper() else local)
        else:
            reales.append(p)
    return reales, descansan


def _partido(p) -> dict:
    d = asdict(p)
    d["fecha"] = p.fecha.isoformat() if p.fecha else None
    return d


def jornadas_jugadas(comp: str, grupo: str = "unico", cliente: OrigenA | None = None) -> list[int]:
    cfg = cargar_config()["competiciones"][comp]
    cliente = cliente or cliente_para(cfg)
    id_grupo = cfg["grupos"][grupo]
    equipos = {f.equipo for f in cliente.clasificacion(id_grupo)}
    competicion = cliente.competicion(id_grupo).filtrar(id_grupo, equipos)
    return sorted({p.jornada for p in competicion.partidos if p.jugado})


def _fila_resumen(ln: E.LineaJugador) -> list:
    """[nombre, equipo, puntos, ensayos, conversiones, golpes, drops, amarillas, rojas, dorsal]"""
    rojas = sum(t in ("roja", "roja20") for t in ln.tarjetas)
    return [ln.nombre, ln.equipo, ln.puntos, ln.ensayos, ln.conversiones, ln.golpes, ln.drops,
            ln.tarjetas.count("amarilla"), rojas, ln.dorsal]


def jugadores_desde_resumen(resumen: dict[str, list], todos: bool = False) -> list[JugadorTemporada]:
    """Tabla de temporada (puntos, ensayos, tarjetas) sumando el resumen de partidos."""
    acum: dict[tuple[str, str], JugadorTemporada] = {}
    for filas in resumen.values():
        for f in filas:
            nombre, equipo, puntos, ensayos = f[0], f[1], f[2], f[3]
            j = acum.setdefault((nombre, equipo), JugadorTemporada(None, nombre, equipo, 0, 0, 0, 0, 0))
            j.pj += 1  # partidos convocado
            j.puntos += puntos
            j.ensayos += ensayos
            if len(f) > 8:
                j.amarillas += f[7]
                j.rojas += f[8]
    return list(acum.values()) if todos else [j for j in acum.values() if j.puntos or j.ensayos]


def actualizar_resumen(comp: str, grupo: str) -> dict[str, list]:
    """Rehace/completa el resumen de partidos de una competición (actas en caché)."""
    cfg = cargar_config()["competiciones"][comp]
    cliente = cliente_para(cfg)
    id_grupo = cfg["grupos"][grupo]
    equipos = {f.equipo for f in cliente.clasificacion(id_grupo)}
    competicion = cliente.competicion(id_grupo).filtrar(id_grupo, equipos)
    return resumen_temporada(comp, grupo, competicion, cliente)


def resumen_temporada(comp: str, grupo: str, competicion, cliente: OrigenA) -> dict[str, list]:
    """Estadísticas de cada jugador en cada partido jugado de la temporada.

    Se guarda en data/ (se commitea) para no volver a bajar las actas antiguas.
    Formato: {id_partido: [[nombre, equipo, puntos, ensayos, conversiones, golpes,
    drops, amarillas, rojas, dorsal], ...]} — solo jugadores convocado.
    Si el fichero tiene el formato antiguo ([nombre, equipo, puntos, ensayos]) se
    regenera (las actas están en caché).
    """
    ruta = ruta_jornada(comp, grupo, 0).with_name("resumen_partidos.json")
    resumen = json.loads(ruta.read_text(encoding="utf-8")) if ruta.exists() else {}
    # Formato antiguo (menos campos, o solo anotadores: pocas filas por partido) -> rehacer
    if any(len(j) != R.CAMPOS_RESUMEN for jugadores in resumen.values() for j in jugadores) or (
            resumen and max(len(js) for js in resumen.values()) < 26):
        resumen = {}  # formato antiguo
    for p in competicion.partidos:
        if not p.jugado or str(p.id) in resumen:
            continue
        acta = cliente.acta(p.id)
        if acta.marcador_por_eventos() != (p.puntos_local, p.puntos_visitante):
            continue  # acta incompleta: se reintenta la próxima vez
        resumen[str(p.id)] = [
            _fila_resumen(ln) for ln in E.lineas_partido(p, acta)  # todos los convocados
        ]
    ruta.parent.mkdir(parents=True, exist_ok=True)
    ruta.write_text(json.dumps(resumen, ensure_ascii=False), encoding="utf-8")
    return resumen


def preparar_jornada(
    comp: str, grupo: str = "unico", jornada: int | None = None, cliente: OrigenA | None = None
) -> Path:
    cfg = cargar_config()["competiciones"][comp]
    id_grupo = cfg["grupos"][grupo]
    cliente = cliente or cliente_para(cfg)

    clasificacion = cliente.clasificacion(id_grupo)
    if not clasificacion:
        raise RuntimeError(
            f"{cfg['nombre']}: el origen no publica clasificación en el grupo {id_grupo}. "
            "Puede que haya rehecho los grupos; hay que actualizar el id en config/competiciones.yaml"
        )
    competicion = cliente.competicion(id_grupo).filtrar(id_grupo, {f.equipo for f in clasificacion})
    jornada = jornada or competicion.ultima_jornada_jugada()
    if jornada is None:
        raise RuntimeError(f"{comp}/{grupo}: aún no hay jornadas jugadas")

    partidos, descansan = separar_descansos(competicion.jornada(jornada))
    lineas: list[E.LineaJugador] = []
    pendientes = []
    actas_jornada = []
    for p in partidos:
        if not p.jugado:
            continue  # aplazado o sin resultado: sale como "Sin resultado", no es un acta pendiente
        acta = cliente.acta(p.id)
        if acta.marcador_por_eventos() != (p.puntos_local, p.puntos_visitante):
            # Acta incompleta: el marcador vale, pero no sus estadísticas.
            pendientes.append(p.id)
            continue
        lineas += E.lineas_partido(p, acta)
        actas_jornada.append((_partido(p), [asdict(e) for e in acta.eventos]))
    resumen = resumen_temporada(comp, grupo, competicion, cliente)
    # OrigenB no publica tabla de jugadores: se calcula con las actas de la temporada
    jugadores_temporada = competicion.jugadores or jugadores_desde_resumen(resumen)

    xv = E.xv_ideal(lineas) if cfg.get("xv_ideal") and lineas else {}
    mejores = sorted(xv.values(), key=lambda ln: -ln.nota) + E.anotadores(lineas, 5)
    foto = elegir_foto_portada(mejores, cliente) if cargar_config().get("foto_portada_auto") else None
    if foto:
        foto["motivo"] = (
            "Mejor jugador de la jornada"
            if xv and foto["jugador"] == mejores[0].nombre
            else "Protagonista de la jornada"
        )

    siguiente, descansan_sig = separar_descansos(competicion.jornada(jornada + 1))
    ruta = ruta_jornada(comp, grupo, jornada)
    previo = json.loads(ruta.read_text(encoding="utf-8")) if ruta.exists() else {}
    # el origen A solo da la clasificación actual: al rehacer una jornada ya pasada se conserva
    # la tabla (y los máximos de temporada) que se guardaron entonces.
    pasada = jornada < (competicion.ultima_jornada_jugada() or jornada) and bool(previo.get("clasificacion"))
    datos = {
        "competicion": comp,
        "nombre": cfg["nombre"],
        "grupo": grupo,
        "temporada": cargar_config()["temporada"],
        "jornada": jornada,
        "partidos": [_partido(p) for p in partidos],
        "descansa": descansan,
        "partidos_temporada": [_partido(p) for p in competicion.partidos
                               if p.jugado and p.jornada <= jornada and not es_descanso(p)],
        "actas_pendientes": pendientes,
        "anotadores": [asdict(x) for x in E.anotadores(lineas, 10)],
        "ensayadores": [asdict(x) for x in E.maximos_ensayadores(lineas, 5)],
        "xv_ideal": {str(d): asdict(ln) for d, ln in xv.items()} or None,
        "foto_portada": foto,
        "candidatos_xv": sorted(
            (asdict(ln) for ln in lineas if 1 <= ln.dorsal <= 15),
            key=lambda x: (x["dorsal"], -x["nota"]),
        ),
        "clasificacion": previo["clasificacion"] if pasada else [asdict(f) for f in clasificacion],
        "escudos": {**previo.get("escudos", {}), **{f.equipo: f.escudo for f in clasificacion if f.escudo}},
        "temporada_anotadores": [
            asdict(j)
            for j in sorted(jugadores_temporada, key=lambda j: (-j.puntos, -j.ensayos))[:10]
        ],
        "temporada_ensayadores": [
            asdict(j)
            for j in sorted(jugadores_temporada, key=lambda j: (-j.ensayos, -j.puntos))[:5]
        ],
        **({k: previo[k] for k in ("temporada_anotadores", "temporada_ensayadores") if k in previo} if pasada else {}),
        "proxima_jornada": {
            "numero": jornada + 1,
            "partidos": [_partido(p) for p in siguiente],
            "descansa": descansan_sig,
        }
        if siguiente
        else None,
    }

    anterior = ruta_jornada(comp, grupo, jornada - 1)
    lider_anterior = None
    if anterior.exists():
        clas_ant = json.loads(anterior.read_text(encoding="utf-8")).get("clasificacion") or []
        lider_anterior = clas_ant[0]["equipo"] if clas_ant else None
    datos["rankings"] = R.calcular([asdict(ln) for ln in lineas], resumen, datos["clasificacion"])
    datos["datos_jornada"] = D.calcular(
        datos["partidos_temporada"], jornada, datos["candidatos_xv"] + [
            asdict(ln) for ln in lineas if not 1 <= ln.dorsal <= 15],
        actas_jornada, resumen, datos["clasificacion"], lider_anterior,
        [asdict(j) for j in competicion.jugadores],
    )

    ruta.parent.mkdir(parents=True, exist_ok=True)
    if previo.get("foto_portada", {}) and previo["foto_portada"].get("archivo"):
        datos["foto_portada"] = previo["foto_portada"]  # foto puesta a mano
    if previo.get("mvp_votacion"):
        datos["mvp_votacion"] = previo["mvp_votacion"]  # ganador de la votación de la red
    if previo.get("xv_editado"):
        # No pisar los cambios manuales del XV al regenerar.
        datos["xv_ideal"] = previo["xv_ideal"]
        datos["xv_editado"] = True
    ruta.write_text(json.dumps(datos, ensure_ascii=False, indent=2), encoding="utf-8")
    return ruta
