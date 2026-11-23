"""Escritura segura de ficheros: si el proceso se corta a medias, queda el fichero anterior entero, nunca uno roto."""
from __future__ import annotations

import os
from pathlib import Path


def escribir(ruta: Path, contenido: str | bytes, copia: bool = False) -> None:
    """Escribe en un temporal y lo pone en su sitio de golpe. `copia`: guarda antes la versión anterior en .bak."""
    ruta = Path(ruta)
    ruta.parent.mkdir(parents=True, exist_ok=True)
    tmp = ruta.with_name(ruta.name + ".tmp")
    if isinstance(contenido, str):
        tmp.write_text(contenido, encoding="utf-8")
    else:
        tmp.write_bytes(contenido)
    if copia and ruta.exists():
        os.replace(ruta, ruta.with_name(ruta.name + ".bak"))
    os.replace(tmp, ruta)
