"""Guarda en caché, poco a poco, las actas aún no descargadas.

Un acta por llamada y con pausa larga entre estructuras; si el origen A rechaza (403/429) el cliente
se frena solo y aquí se espera. No esquiva nada: solo reparte las peticiones en el tiempo.
"""
from __future__ import annotations

import time

from datosdep import estado
from datosdep.pipeline import cargar_config
from datosdep.scraper.origen_a import cliente_para, compartido

REFRESCO_COLA_S = 6 * 3600  # cada cuánto se vuelven a listar los partidos
_cola: list[tuple[str, int]] = []
_grupos: list[tuple[dict, int]] = []  # grupos aún por listar en este ciclo
_ultima_cola = float("-inf")


# Primero lo importante; las regionales (Castilla y León, OrigenB…) no se precalientan.
PRIORIDAD = ("dh_masc", "dh_fem", "dh_elite", "dhb_masc", "dhb_fem", "copa", "m23")


def _todos_los_grupos() -> list[tuple[dict, int]]:
    comps = cargar_config()["competiciones"]
    grupos = [(comps[k], g) for k in PRIORIDAD if k in comps and comps[k].get("fuente") != "origen_b"
              for g in comps[k]["grupos"].values()]
    return grupos[::-1]  # se van sacando del final: primero DH


def paso() -> int | None:
    """Una sola petición como mucho: lista un grupo o descarga un acta. Devuelve el id del acta, si la hubo."""
    global _ultima_cola, _grupos
    cliente = compartido()
    if cliente.bloqueado_ahora() or not 2 <= estado.ahora().hour < 7:
        return None  # solo de madrugada: de día la web se deja libre para lo que se pide en el momento
    if not _cola and not _grupos and time.monotonic() - _ultima_cola > REFRESCO_COLA_S:
        _ultima_cola = time.monotonic()
        _grupos = _todos_los_grupos()
    if _grupos:
        cfg, id_grupo = _grupos.pop()
        try:
            comp = cliente_para(cfg).competicion(id_grupo)
        except Exception:
            return None
        for p in comp.partidos:
            if p.jugado:
                if not cliente.acta_en_cache(p.id):
                    _cola.append(("acta", p.id))
                elif not cliente.tiene_extra(p.id):
                    _cola.append(("extra", p.id))  # acta guardada sin cambios: se completa para los minutos
                if not cliente.previo_en_cache(p.id):
                    _cola.append(("previo", p.id))  # árbitro del partido
        return None
    while _cola:
        tipo, id_partido = _cola.pop()
        if tipo == "acta" and not cliente.acta_en_cache(id_partido):
            cliente.acta(id_partido)
            return id_partido
        if tipo == "extra" and not cliente.tiene_extra(id_partido):
            cliente.refrescar_extra(id_partido)
            return id_partido
        if tipo == "previo" and not cliente.previo_en_cache(id_partido):
            try:
                cliente._get("previo.php", {"id_partido": id_partido}, cachear=True)
            except Exception:
                pass
            return id_partido
    return None
