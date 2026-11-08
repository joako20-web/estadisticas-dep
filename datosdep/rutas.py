"""Rutas del proyecto (módulo sin dependencias, para evitar importaciones circulares)."""
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
CONFIG = RAIZ / "config"
DATA = RAIZ / "data"

import copy
import os
import threading

import yaml

_YAML: dict[Path, tuple[float, object]] = {}
_YAML_LOCK = threading.Lock()


def _expandir(o):
    """Sustituye $VARIABLES de entorno en los textos (direcciones que no se publican)."""
    if isinstance(o, str):
        return os.path.expandvars(o) if "$" in o else o
    if isinstance(o, list):
        return [_expandir(x) for x in o]
    if isinstance(o, dict):
        return {k: _expandir(v) for k, v in o.items()}
    return o


def leer_yaml(ruta: Path, defecto=None, copia: bool = True):
    """YAML ya leído en memoria mientras el fichero no cambie (se mira su fecha).

    Los menús del bot leían config/competiciones.yaml decenas de veces por pulsación.
    Se devuelve una copia para que nadie modifique sin querer la versión guardada
    (`copia=False` para lecturas muy frecuentes que solo consultan, como los nombres).
    """
    try:
        mtime = ruta.stat().st_mtime
    except FileNotFoundError:
        return copy.deepcopy(defecto)
    with _YAML_LOCK:
        guardado = _YAML.get(ruta)
        if guardado is None or guardado[0] != mtime:
            datos = yaml.load(ruta.read_text(encoding="utf-8"), Loader=getattr(yaml, "CSafeLoader", yaml.SafeLoader))
            datos = _expandir(datos)
            guardado = _YAML[ruta] = (mtime, datos if datos is not None else defecto)
    return copy.deepcopy(guardado[1]) if copia else guardado[1]
