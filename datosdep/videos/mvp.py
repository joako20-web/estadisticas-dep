"""Reel "Jugador de la jornada": gancho, presentación (foto o tipografía + escudo),
estadísticas en contador, rival y resultado, y cierre.

`jugador_jornada()` y `ficha()` también los usa el cartel (datosdep/carteles_mvp.py).
"""
from __future__ import annotations

from datosdep.core.estadisticas import POSICIONES
from datosdep.render import nombres
from datosdep.videos import base
from datosdep.videos.base import props_base

COMPOSICION = "ReelMvp"
RESULTADO = {"G": "Victoria", "E": "Empate", "P": "Derrota"}


def jugador_jornada(datos: dict) -> tuple[dict, int | None] | None:
    """La mejor línea de la jornada (nota máxima del XV ideal; si no hay XV, el máximo
    anotador) y su puesto en el XV (1-15) si sale de él. Si se ha guardado el ganador
    de la votación de la red (`mvp_votacion`), es ese."""
    xv = datos.get("xv_ideal") or {}
    ganador = (datos.get("mvp_votacion") or {}).get("ganador")
    if ganador:
        for puesto, ln in xv.items():
            if ln["nombre"] == ganador:
                return ln, int(puesto)
        for ln in (datos.get("candidatos_xv") or []) + (datos.get("anotadores") or []):
            if ln["nombre"] == ganador:
                return ln, None
    if xv:
        puesto = max(xv, key=lambda d: (xv[d].get("nota", 0), xv[d]["puntos"]))
        return xv[puesto], int(puesto)
    anotadores = datos.get("anotadores") or []
    if anotadores:
        return max(anotadores, key=lambda x: (x.get("nota", 0), x["puntos"])), None
    return None


def _partido(datos: dict, m: dict) -> dict | None:
    """Rival y marcador desde el punto de vista del jugador."""
    escudos = datos.get("escudos", {})
    for p in datos.get("partidos", []):
        if p.get("puntos_local") is None or m["equipo"] not in (p["local"], p["visitante"]):
            continue
        local = p["local"] == m["equipo"]
        rival = p["visitante"] if local else p["local"]
        if m.get("rival") and rival != m["rival"]:
            continue
        propios, contra = ((p["puntos_local"], p["puntos_visitante"]) if local
                           else (p["puntos_visitante"], p["puntos_local"]))
        letra = "G" if propios > contra else "E" if propios == contra else "P"
        return {"rival": nombres.equipo_corto(rival), "rivalOficial": rival,
                "escudoRival": base.R.escudo_equipo(rival, escudos),
                "propios": propios, "contra": contra, "letra": letra, "texto": RESULTADO[letra]}
    if m.get("rival"):  # el partido no está en la lista: solo el rival
        letra = m.get("resultado", "")
        return {"rival": nombres.equipo_corto(m["rival"]), "rivalOficial": m["rival"],
                "escudoRival": base.R.escudo_equipo(m["rival"], escudos),
                "propios": None, "contra": None, "letra": letra, "texto": RESULTADO.get(letra, "")}
    return None


def ficha(datos: dict, con_foto: bool = True) -> dict:
    """Todo lo que muestran el vídeo y el cartel del jugador de la jornada."""
    elegido = jugador_jornada(datos)
    if not elegido:
        raise RuntimeError(f"la jornada {datos['jornada']} no tiene datos de jugadores (¿actas sin publicar?)")
    m, puesto = elegido
    j = nombres.jugador(m["nombre"])
    dorsal = m.get("dorsal")
    posicion = POSICIONES.get(puesto or dorsal, "")
    stats = [{"clave": k, "valor": m.get(k) or 0, "texto": t} for k, t in
             (("ensayos", "Ensayos"), ("conversiones", "Transf."), ("golpes", "Golpes"))]
    if m.get("drops"):
        stats.append({"clave": "drops", "valor": m["drops"], "texto": "Drops"})
    return {
        "nombre": j["nombre"], "apellidos": j["apellidos"], "corto": j["corto"], "completo": j["completo"],
        "equipo": nombres.equipo_corto(m["equipo"]), "equipoOficial": m["equipo"],
        "abr": nombres.equipo_abr(m["equipo"]),
        "escudo": base.R.escudo_equipo(m["equipo"], datos.get("escudos", {})),
        "posicion": posicion, "dorsal": dorsal, "puesto": puesto,
        "puntos": m["puntos"], "nota": round(float(m.get("nota") or 0), 1),
        "stats": stats, "partido": _partido(datos, m),
        "foto": base.foto_jugador(m.get("foto", "")) if con_foto else "",
        "motivo": ("Elegido por la afición" if (datos.get("mvp_votacion") or {}).get("ganador")
                   else "Mejor nota del XV ideal" if puesto else "Máximo anotador"),
    }


def props(datos: dict, tema: str = "tele") -> dict:
    return {**props_base(datos["competicion"], datos["jornada"], datos["temporada"], tema),
            "jugador": ficha(datos)}
