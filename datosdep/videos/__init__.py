"""Vídeos verticales para vídeos con motion graphics (Remotion, en video/).

Cada plantilla es un módulo de este paquete con:
- `COMPOSICION`: id de la composición en video/src/Root.tsx
- `props(...)`: construye sus props a partir de los datos (sin IA, sin red salvo escudos)
y se registra en PLANTILLAS con su nombre para el bot y cómo se obtienen sus datos.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from datosdep.pipeline import cargar_config
from datosdep.rutas import RAIZ
from datosdep.videos import base, clasificacion, dato, final, jornada, mvp, previa, rankings, xv


@dataclass(frozen=True)
class Plantilla:
    clave: str
    nombre: str  # botón del bot
    composicion: str
    # (comp, grupo, jornada, extra) -> props
    construir: Callable[..., dict]
    por_liga: bool = True  # aparece en el menú 🎬 de cada liga
    requiere: str | None = None  # clave de config/competiciones.yaml que debe estar activa (p. ej. "xv_ideal")

    def disponible(self, cfg: dict) -> bool:
        return self.por_liga and not cfg.get("torneo") and (self.requiere is None or bool(cfg.get(self.requiere)))


def _jornada(comp: str, grupo: str, jornada_: int | None, **_) -> dict:
    props = jornada.props(base.datos_jornada(comp, grupo, jornada_))
    if not props["partidos"]:
        raise RuntimeError(f"la jornada {props['jornada']} aún no tiene resultados")
    return props


def _previa(comp: str, grupo: str, jornada_: int | None, id_partido: int | None = None, **_) -> dict:
    """Previa de la jornada SIGUIENTE a `jornada_` (la última disputada si es None);
    `id_partido` cambia el partido destacado."""
    return previa.props(base.datos_jornada(comp, grupo, jornada_), id_destacado=id_partido)


def _xv(comp: str, grupo: str, jornada_: int | None, **_) -> dict:
    cfg = cargar_config()["competiciones"][comp]
    if not cfg.get("xv_ideal"):
        raise RuntimeError(f"{cfg['nombre']} no tiene XV ideal")
    return xv.props(base.datos_jornada(comp, grupo, jornada_))


def _mvp(comp: str, grupo: str, jornada_: int | None, **_) -> dict:
    return mvp.props(base.datos_jornada(comp, grupo, jornada_))


def _clasificacion(comp: str, grupo: str, jornada_: int | None, **_) -> dict:
    datos = base.datos_jornada(comp, grupo, jornada_)
    return clasificacion.props(datos, clasificacion.anterior(datos))


def _rankings(comp: str, grupo: str, jornada_: int | None, **_) -> dict:
    return rankings.props(base.datos_jornada(comp, grupo, jornada_))


def _dato(comp: str, grupo: str, jornada_: int | None, indice: int | str = 0, **_) -> dict:
    return dato.props(base.datos_jornada(comp, grupo, jornada_), int(indice or 0))


PLANTILLAS: dict[str, Plantilla] = {p.clave: p for p in [
    Plantilla("jornada", "📊 Resultados de la jornada", jornada.COMPOSICION, _jornada),
    # por partido: reel(comp, grupo, jornada, tipo="final", id_partido=17648)
    Plantilla("final", "🏉 Así fue el partido", final.COMPOSICION, final.construir, por_liga=False),
    Plantilla("previa", "🗓️ Previa de la jornada", previa.COMPOSICION, _previa),
    Plantilla("xv", "⭐ XV ideal", xv.COMPOSICION, _xv, requiere="xv_ideal"),
    Plantilla("mvp", "🏅 Jugador de la jornada", mvp.COMPOSICION, _mvp),
    Plantilla("clasificacion", "🏆 Clasificación", clasificacion.COMPOSICION, _clasificacion),
    Plantilla("rankings", "🎯 Rankings de temporada", rankings.COMPOSICION, _rankings),
    Plantilla("dato", "💡 El dato de la jornada", dato.COMPOSICION, _dato),
]}


def reel(comp: str, grupo: str = "unico", jornada: int | None = None, tipo: str = "jornada",
         salida: Path | None = None, props_usadas: dict | None = None, **extra) -> Path:
    """Genera el vídeo `tipo` y devuelve la ruta del MP4 (en `props_usadas`, si se pasa,
    se copian las props con que se ha hecho)."""
    p = PLANTILLAS[tipo]
    props = p.construir(comp, grupo, jornada, **extra)
    if props_usadas is not None:
        props_usadas.update(props)
    sufijo = f"_p{extra['id_partido']}" if extra.get("id_partido") else ""
    salida = salida or RAIZ / "out" / f"reel_{tipo}_{comp}_{grupo}_j{props.get('jornada', 0):02d}{sufijo}.mp4"
    return base.renderizar(p.composicion, props, salida)
