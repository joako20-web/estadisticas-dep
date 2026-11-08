"""Cambios manuales en el XV ideal ("9 Araña" -> pone a ese jugador de 9)."""
from __future__ import annotations

import re
import unicodedata

from datosdep.core.estadisticas import GRUPOS_POSICION


def _norm(s: str) -> str:
    s = unicodedata.normalize("NFKD", s.lower())
    return "".join(c for c in s if not unicodedata.combining(c))


def cambiar_xv(datos: dict, orden: str) -> str:
    """Aplica una orden "<dorsal> <nombre>" sobre datos["xv_ideal"].

    Busca primero entre los titulares que jugaron en esa posición (o la
    intercambiable: 4/5, 6/7, 11/14, 12/13) y, si no, entre todos los titulares.
    Devuelve un mensaje para el usuario. Lanza ValueError si no puede aplicarla.
    """
    m = re.fullmatch(r"\s*(\d{1,2})\s+(.+?)\s*", orden)
    if not m or not 1 <= int(m.group(1)) <= 15:
        raise ValueError('Escribe el dorsal y el nombre, por ejemplo: "9 Araña"')
    dorsal, busqueda = int(m.group(1)), _norm(m.group(2))
    trozos = busqueda.split()

    candidatos = datos.get("candidatos_xv") or []
    coinciden = [c for c in candidatos if all(t in _norm(c["nombre"]) for t in trozos)]
    if not coinciden:
        raise ValueError(f'No encuentro a ningún titular de la jornada que coincida con "{m.group(2)}"')

    grupo = next(g for g in GRUPOS_POSICION if dorsal in g)
    en_posicion = [c for c in coinciden if c["dorsal"] in grupo]
    elegidos = en_posicion or coinciden
    if len(elegidos) > 1:
        lista = "\n".join(f"· {c['nombre']} ({c['equipo']}, jugó de {c['dorsal']})" for c in elegidos[:8])
        raise ValueError(f"Hay varios jugadores que coinciden, afina más:\n{lista}")

    nuevo = dict(elegidos[0])
    nuevo["dorsal"] = dorsal
    anterior = datos["xv_ideal"].get(str(dorsal), {}).get("nombre", "—")
    datos["xv_ideal"][str(dorsal)] = nuevo
    datos["xv_editado"] = True
    aviso = "" if en_posicion else f" (ojo: en el partido jugó de {elegidos[0]['dorsal']})"
    return f"{dorsal}: {anterior} → {nuevo['nombre']}{aviso}"
