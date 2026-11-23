"""Estado persistente del bot, guardado en el repo (estado/*.json).

El workflow de GitHub Actions lo lee al empezar y lo commitea al acabar.
"""
from __future__ import annotations

import json
import os
from datetime import datetime
from zoneinfo import ZoneInfo

from datosdep import archivos
from datosdep.pipeline import RAIZ

MADRID = ZoneInfo("Europe/Madrid")
# ESTADO_DIR permite una segunda instancia (laboratorio) con su propio estado,
# sin tocar el de producción. Ruta relativa = respecto a la raíz del repo.
ESTADO = RAIZ / os.environ.get("ESTADO_DIR", "estado")
FOTOS = RAIZ / "data" / "fotos"


def _leer(nombre: str, defecto):
    """Si el fichero está roto (corte a medias, conflicto de git...), se usa la copia anterior; si tampoco
    vale, el valor por defecto. El bot no se cae por un estado ilegible."""
    ruta = ESTADO / nombre
    for candidata in (ruta, ruta.with_name(nombre + ".bak")):
        if not candidata.exists():
            continue
        try:
            return json.loads(candidata.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            print(f"⚠️ estado ilegible: {candidata}; pruebo con la copia anterior")
    return defecto


def _escribir(nombre: str, datos) -> None:
    archivos.escribir(ESTADO / nombre, json.dumps(datos, ensure_ascii=False, indent=2), copia=True)


def posts() -> dict[str, dict]:
    """Jornadas ya preparadas: {id: {competicion, grupo, jornada, json, enviado}}."""
    return _leer("posts.json", {})


def guardar_posts(p: dict[str, dict]) -> None:
    _escribir("posts.json", p)


def bot() -> dict:
    return _leer("bot.json", {"offset": 0, "chat_id": None, "esperando": None})


def guardar_bot(b: dict) -> None:
    _escribir("bot.json", b)


def id_post(temporada: str, comp: str, grupo: str, jornada: int) -> str:
    return f"{temporada.replace('/', '-')}_{comp}_{grupo}_j{jornada:02d}"


def ahora() -> datetime:
    return datetime.now(MADRID)
