"""Interpreta pedidos escritos en Telegram, sin IA, con palabras clave.

"quiero el xv de dhb"            -> XV de los 4 grupos de DH B
"clasificación de la élite"      -> clasificación de DH Élite
"resultados dh jornada 1"        -> resultados de DH, jornada 1
"todo de la liga iberdrola"      -> carrusel completo de DH Femenina
"""
from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass

from datosdep.pipeline import cargar_config


@dataclass
class Pedido:
    ligas: list[tuple[str, str]]  # (competición, grupo)
    claves: list[str] | None  # None = carrusel completo
    jornada: int | None = None


def _norm(s: str) -> str:
    s = unicodedata.normalize("NFKD", s.lower())
    return " ".join("".join(c for c in s if not unicodedata.combining(c)).split())


TIPOS = [
    ("xv", r"\bxv\b|\bquince\b|equipo ideal|once ideal|\b15 ideal"),
    ("resultados", r"resultad|marcador"),
    ("temporada", r"anotador\w* de (la )?(temporada|liga)|anotador\w* (de la )?temporada|acumulad|pichichi"),
    ("anotadores", r"anotador|goleador|maximos|puntos"),
    ("clasificacion", r"clasific|\btabla\b|posiciones"),
    ("previa", r"previa|proxim|siguiente|calendario|horario|cuando juega"),
    ("portada", r"portada|mvp|mejor jugador"),
    ("datos", r"\bdatos?\b|curiosidad|record"),
    ("grupos", r"todos los grupos|fase de grupos|\bgrupos\b"),
    ("encuesta_mvp", r"vota|votacion|encuesta mvp"),
    ("encuesta_partido", r"quien gana|pronostico|encuesta partido"),
    ("evolucion", r"evolucion|grafico|asi va"),
    ("xv_temporada", r"xv de la temporada|equipo de la temporada"),
    ("mvp_temporada", r"mvp de la temporada"),
    ("ensayadores", r"ensayador|\btry\b|\btries\b"),
    ("pateadores", r"pateador|pie\b|patada|pateo|palos"),
    ("disciplina", r"tarjeta|amarilla|roja|disciplina|expulsi"),
    ("banquillo", r"banquillo|suplente"),
    ("equipos", r"en numeros|mejor ataque|mejor defensa|\bequipos\b"),
    ("cuadro", r"cuadro|play.?off|eliminatoria|semifinal|cruces"),
]
TODO = r"\btodo\b|carrusel|completo|resumen|\bpost\b"


def _ligas(t: str) -> list[tuple[str, str]]:
    cfg = cargar_config()["competiciones"]
    if re.search(r"\bcopa\b", t):
        m = re.search(r"\bgrupo ([a-f])\b", t)
        grupos = list(cfg["copa"]["grupos"])
        return [("copa", m.group(1).upper())] if m else [("copa", g) for g in grupos]
    fem = re.search(r"\bfem|femenin|chicas|mujeres|\bdhf\b|iberdrola", t)
    es_b = re.search(r"\bdhb\w*|honor b\b|\bdh b\b", t)
    if es_b and fem:
        return [("dhb_fem", "unico")]
    if es_b:
        m = re.search(r"\bgrupo ([abcd])\b|\bdhb ?([abcd])\b|\bdh b ([abcd])\b", t)
        grupos = list(cfg["dhb_masc"]["grupos"])
        if m:
            g = next(x for x in m.groups() if x).upper()
            return [("dhb_masc", g)]
        return [("dhb_masc", g) for g in grupos]
    if re.search(r"elite", t):
        return [("dh_elite", "unico")]
    if fem:
        return [("dh_fem", "unico")]
    if re.search(r"\bdh\b|division de honor|\bhonor\b", t):
        return [("dh_masc", "unico")]
    if re.search(r"\btodas?\b.*\bligas?\b|\bligas\b", t):
        return [(c, g) for c, v in cfg.items() for g in v["grupos"]]
    return []


def interpretar(texto: str) -> Pedido | None:
    t = _norm(texto)
    ligas = _ligas(t)
    if not ligas:
        return None
    claves = []
    temporada = re.search(r"temporada|de la liga|acumulad|total", t)
    for clave, patron in TIPOS:
        if re.search(patron, t) and not (clave == "anotadores" and "temporada" in claves):
            if temporada and clave in ("ensayadores", "pateadores"):
                clave += "_t"
            claves.append(clave)
    # Las versiones "de temporada" mandan sobre las de jornada
    for largo, corto in (("xv_temporada", "xv"), ("mvp_temporada", "portada"), ("encuesta_mvp", "portada")):
        if largo in claves and corto in claves:
            claves.remove(corto)
    if re.search(TODO, t) or not claves:
        claves = None
    m = re.search(r"\b(?:jornada|j)\s*(\d{1,2})\b", t)
    return Pedido(ligas, claves, int(m.group(1)) if m else None)
