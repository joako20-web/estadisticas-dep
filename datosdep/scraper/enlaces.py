"""Direcciones de imágenes remotas sin escribir el servidor: en los datos se guardan con una marca
("@f/<ruta>" o "$ORIGEN_B_..._URL<ruta>") y el servidor real se lee de variables de entorno al descargar."""
import os
import re

_ABSOLUTA = re.compile(r"^(?:https?:)?//[^/]+/(.*)$", re.S)
_MARCA_B = re.compile(r"^\$(ORIGEN_B\w*_URL)")


def ocultar_a(url: str) -> str:
    if not url or url.startswith("@f/"):
        return url
    m = _ABSOLUTA.match(url)
    return "@f/" + m[1] if m else url


def ocultar_b(url: str) -> str:
    for nombre, valor in os.environ.items():
        if nombre.startswith("ORIGEN_B") and nombre.endswith("_URL") and valor and url.startswith(valor.rstrip("/")):
            return "$" + nombre + url[len(valor.rstrip("/")):]
    return url


def resolver(url: str) -> str:
    if url.startswith("@f/"):
        return os.environ.get("ORIGEN_A_IMG_URL", "").rstrip("/") + "/" + url[3:]
    m = _MARCA_B.match(url)
    if m:
        return os.environ.get(m[1], "").rstrip("/") + url[m.end():]
    return url
