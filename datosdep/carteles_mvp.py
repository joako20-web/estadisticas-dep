"""Cartel "Jugador de la jornada" (post 4:5 o historia 9:16, en los 5 temas).

Tarjeta tipo MVP: foto de el origen A si tiene calidad (si no, el escudo en grande),
dorsal, posición, nombre, puntos y desglose, rival y resultado. El jugador es el
mismo que el del vídeo (datosdep/videos/mvp.py: nota máxima del XV ideal).
"""
from __future__ import annotations

from pathlib import Path

from datosdep.render import nombres
from datosdep.render.render import renderizar_slides
from datosdep.videos.base import datos_jornada
from datosdep.videos.mvp import ficha


def votos(datos: dict) -> list[dict]:
    """Porcentajes de la votación guardados (`mvp_votacion.votos`), de más a menos votado."""
    vot = datos.get("mvp_votacion") or {}
    out = [{"nombre": nombres.jugador(n)["completo"], "corto": nombres.jugador(n)["corto"], "pct": pct,
            "gana": n == vot.get("ganador")} for n, pct in (vot.get("votos") or {}).items()]
    return sorted(out, key=lambda v: (-v["pct"], not v["gana"]))


def slide_mvp(datos: dict) -> dict:
    aficion = bool((datos.get("mvp_votacion") or {}).get("ganador"))
    return {"tipo": "mvp", "clave": "mvp", "j": ficha(datos), "jornada_n": datos["jornada"],
            "aficion": aficion, "votos": votos(datos) if aficion else []}


def guardar_votacion(datos: dict, ganador: str | None, votos: dict[str, int] | None = None) -> None:
    """Apunta en el JSON de la jornada el ganador de la votación de la red (None = volver
    al elegido por nota) y, si se dan, los porcentajes por jugador."""
    if ganador is None:
        datos.pop("mvp_votacion", None)
    else:
        datos["mvp_votacion"] = {"ganador": ganador, "votos": votos or {}}


def leer_porcentajes(texto: str, n: int) -> list[int]:
    """«62 25 13», «62/25/13», «62%, 25%, 13%»… → [62, 25, 13]. Tantos números como
    candidatos (n) o uno menos (el último se completa hasta 100)."""
    import re

    nums = [int(x) for x in re.findall(r"\d+", texto)]
    if len(nums) == n - 1 and sum(nums) <= 100:
        nums.append(100 - sum(nums))
    if len(nums) != n:
        raise ValueError(f"Necesito {n} porcentajes, uno por candidato en el orden de la encuesta (p. ej. "
                         + " ".join(str(x) for x in ([55, 25, 15, 5][:n] if n <= 4 else [100 // n] * n)) + ").")
    if not 97 <= sum(nums) <= 103:  # la red redondea: se tolera ±3
        raise ValueError(f"Suman {sum(nums)}%, deberían sumar 100.")
    return nums


def renderizar_mvp(comp: str, grupo: str, destino: Path, jornada: int | None = None,
                   formato: str = "post", tema: str | None = None) -> list[Path]:
    """Pinta el cartel en `destino` (borra los .jpg que hubiera) y devuelve [ruta]."""
    datos = datos_jornada(comp, grupo, jornada)
    return renderizar_slides(datos, [slide_mvp(datos)], Path(destino), formato, tema)
