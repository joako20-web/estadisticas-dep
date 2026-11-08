"""Carteles de partido sueltos (imágenes bajo pedido).

- "Matchday": un partido de la próxima jornada con los dos escudos en grande, nombres,
  posición en la tabla, competición y jornada, día y hora, y campo. En post (1080x1350)
  o historia (1080x1920) y en cualquiera de los temas de temas.css.

Uso típico (bot): un botón por partido de la próxima jornada que llame a
`renderizar_matchday(comp, grupo, partido["id"], destino, formato)`; con `id_partido=None`
se usa el partido destacado (`especiales.partido_destacado`).
"""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from datosdep.especiales import partido_destacado
from datosdep.pipeline import es_descanso, preparar_jornada, ruta_jornada
from datosdep.render.render import DIAS, renderizar_slides

MESES_LARGOS = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto",
                "septiembre", "octubre", "noviembre", "diciembre"]


def _datos(comp: str, grupo: str, jornada: int | None) -> dict:
    """JSON de la jornada `jornada` si está guardado; si no (o sin jornada), se descarga
    la última disputada, cuya `proxima_jornada` es la que se anuncia."""
    ruta = ruta_jornada(comp, grupo, jornada) if jornada else None
    if not (ruta and ruta.exists()):
        ruta = preparar_jornada(comp, grupo, jornada)
    return json.loads(Path(ruta).read_text(encoding="utf-8"))


def slide_matchday(datos: dict, id_partido: int | None = None) -> dict:
    """Datos del slide `matchday` para un partido de la próxima jornada (o el destacado).

    Lanza RuntimeError si no hay próxima jornada o el partido no está en ella."""
    prox = datos.get("proxima_jornada") or {}
    if not prox.get("partidos"):
        raise RuntimeError(f"no hay próxima jornada tras la jornada {datos['jornada']}")
    if id_partido:
        p = next((x for x in prox["partidos"] if x["id"] == id_partido), None)
        if not p:
            raise RuntimeError(f"el partido {id_partido} no está en la jornada {prox['numero']}")
    else:
        p = partido_destacado(datos) or next(x for x in prox["partidos"] if not es_descanso(x))

    tabla = {f["equipo"]: f for f in datos.get("clasificacion", [])}
    f = datetime.fromisoformat(p["fecha"]) if p.get("fecha") else None
    hora = f.strftime("%H:%M") if f else ""
    lados = [{"equipo": eq, "posicion": tabla.get(eq, {}).get("posicion"), "pt": tabla.get(eq, {}).get("pt")}
             for eq in (p["local"], p["visitante"])]
    return {
        "tipo": "matchday", "clave": f"matchday_{p['id']}", "id": p["id"], "numero": prox["numero"],
        "lados": lados,
        "dia": f"{DIAS[f.weekday()]} {f.day} de {MESES_LARGOS[f.month - 1]}" if f else "Fecha por confirmar",
        "hora": "" if hora in ("", "00:00") else hora,  # 00:00 en el origen A = hora sin fijar
        "campo": (p.get("campo") or "").split("(")[0].strip(),
    }


def renderizar_matchday(comp: str, grupo: str, id_partido: int | None, destino: Path,
                        formato: str = "post", tema: str | None = None, jornada: int | None = None) -> Path:
    """Cartel "Matchday" de un partido de la próxima jornada. Devuelve la ruta del JPEG.

    - id_partido: id de el origen A del partido (de `proxima_jornada.partidos`); None = el destacado.
    - formato: "post" (1080x1350) o "historia" (1080x1920), a doble resolución.
    - tema: noche | brutal | prensa | tele | retro (None = el elegido en el bot).
    - jornada: jornada disputada cuyos datos se usan (None = la última, se descarga).
    Ojo: `renderizar_slides` vacía los .jpg de `destino`; usa una carpeta por cartel.
    """
    datos = _datos(comp, grupo, jornada)
    slide = slide_matchday(datos, id_partido)
    cabecera = {"competicion": datos["competicion"], "grupo": datos["grupo"], "jornada": slide["numero"],
                "temporada": datos["temporada"], "escudos": datos.get("escudos", {})}
    return renderizar_slides(cabecera, [slide], destino, formato, tema)[0]
