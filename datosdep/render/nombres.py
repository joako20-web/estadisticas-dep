"""Nombres cortos de equipos y jugadores para las imágenes."""
from __future__ import annotations



from datosdep.rutas import CONFIG, leer_yaml

_RELLENO = {"RUGBY", "CLUB", "RC", "CR", "C.R.", "R.C.", "RT", "DE", "DEL", "LA", "EL", "DH", "DHB", "XV"}
_MINUSCULAS = {"de", "del", "la", "el", "y", "i"}


def _yaml(nombre: str) -> dict:
    return leer_yaml(CONFIG / nombre, {}, copia=False)  # solo se consulta


def _equipos() -> dict:
    return _yaml("equipos.yaml")


def titulo(s: str) -> str:
    def cap(p: str) -> str:
        if "." in p.strip("."):  # siglas tipo C.A.R. o A.D.
            return p.upper()
        if 2 <= len(p) <= 4 and p.isalpha() and not set(p) & set("aeiouáéíóú"):  # CRC, UES
            return p.upper()
        return "-".join(x[:1].upper() + x[1:] for x in p.split("-"))

    palabras = s.lower().split()
    return " ".join(p if i and p in _MINUSCULAS else cap(p) for i, p in enumerate(palabras))


_SANTOS = {"SAN", "SANT", "SANTA", "SANTO", "SAINT"}


def equipo_corto(oficial: str) -> str:
    if oficial in _equipos():
        return _equipos()[oficial]["corto"]
    limpio = " ".join(oficial.replace(" -", " - ").split())
    if len(limpio) <= 18:  # corto de por sí: entero
        return titulo(limpio)
    utiles = [p for p in limpio.split() if p not in _RELLENO and p.strip("-")]
    if len(utiles) > 2 and utiles[-3].upper() in _SANTOS:
        # «SAN ISIDRO FUENCARRAL» → «San Isidro», no «Isidro Fuencarral»
        return titulo(" ".join(utiles[-3:-1]))
    return titulo(" ".join(utiles[-2:] if len(utiles) > 2 else utiles))


def equipo_abr(oficial: str) -> str:
    if oficial in _equipos():
        return _equipos()[oficial]["abr"]
    utiles = [p for p in oficial.split() if p not in _RELLENO] or oficial.split()
    return utiles[-1][:3].upper()


def jugador(nombre: str) -> dict:
    """Divide en nombre de pila y apellidos para mostrarlo en dos líneas.

    En los nombres de 3+ palabras no se sabe si hay uno o dos nombres de pila
    (SANTIAGO IGNACIO MANSILLA vs JUAN PEREZ GARCIA); se toma la primera palabra
    como nombre y el resto como apellidos, salvo que config/jugadores.yaml diga otra cosa.
    """
    if nombre in _yaml("jugadores.yaml"):
        pila, apellidos = _yaml("jugadores.yaml")[nombre]
        return {"nombre": pila, "apellidos": apellidos, "completo": f"{pila} {apellidos}", "corto": apellidos}
    partes = titulo(nombre).split()
    if len(partes) == 1:
        return {"nombre": "", "apellidos": partes[0], "completo": partes[0], "corto": partes[0]}
    apellidos = partes[1:]
    # Para fichas pequeñas (XV): se quitan apellidos del final hasta que quepa.
    corto = list(apellidos)
    while len(" ".join(corto)) > 17 and len(corto) > 1:
        corto.pop()
    while len(corto) > 1 and corto[-1].lower() in _MINUSCULAS:
        corto.pop()
    return {"nombre": partes[0], "apellidos": " ".join(apellidos), "completo": " ".join(partes),
            "corto": " ".join(corto)}


def clubes_conjunto(oficial: str) -> list[str] | None:
    """Clubes de un equipo conjunto (config/equipos.yaml: `clubes: [...]`), o None."""
    cfg = _equipos().get(oficial) or {}
    return cfg.get("clubes")
