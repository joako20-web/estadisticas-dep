"""Reel de resultados de la jornada: gancho, resultados, jugador de la jornada, top 4 y cierre."""
from __future__ import annotations

from datosdep.core.estadisticas import POSICIONES
from datosdep.render import nombres
from datosdep.render import render as R
from datosdep.videos.base import equipo, props_base

COMPOSICION = "ReelJornada"
MAX_PARTIDOS = 8  # 2 s por partido: con más, el reel se hace largo


def props(datos: dict, tema: str = "tele") -> dict:
    escudos = datos["escudos"]
    partidos = []
    for p in datos["partidos"]:
        if p.get("puntos_local") is None:
            continue
        pl, pv = p["puntos_local"], p["puntos_visitante"]
        partidos.append({"local": equipo(p["local"], escudos, pl, pl > pv),
                         "visitante": equipo(p["visitante"], escudos, pv, pv > pl)})

    dato = next(iter(datos.get("datos_jornada") or []), None)
    gancho = {"numero": dato["numero"], "unidad": dato["unidad"], "titular": dato["titular"],
              "escudo": R.escudo_equipo(dato["equipo"], escudos) if dato.get("equipo") else ""} if dato else None
    if not gancho and partidos:  # sin "dato de la jornada": la victoria más amplia
        p = max(partidos, key=lambda p: abs(p["local"]["puntos"] - p["visitante"]["puntos"]))
        ganador = p["local"] if p["local"]["gana"] else p["visitante"]
        gancho = {"numero": str(abs(p["local"]["puntos"] - p["visitante"]["puntos"])), "unidad": "puntos de diferencia",
                  "titular": f"Exhibición de {ganador['nombre']}" if ganador["gana"] else "Reparto de puntos",
                  "escudo": ganador["escudo"] if ganador["gana"] else ""}

    mvp = None
    candidatos = list((datos.get("xv_ideal") or {}).values()) or datos.get("anotadores") or []
    if candidatos:
        m = max(candidatos, key=lambda x: (x.get("nota", 0), x["puntos"]))
        j = nombres.jugador(m["nombre"])
        mvp = {"nombre": j["nombre"], "apellidos": j["apellidos"], "equipo": nombres.equipo_corto(m["equipo"]),
               "escudo": R.escudo_equipo(m["equipo"], escudos), "posicion": POSICIONES.get(m.get("dorsal"), ""),
               "dorsal": m.get("dorsal"), "puntos": m["puntos"],
               "stats": [{"valor": m[k], "texto": t} for k, t in
                         (("ensayos", "ensayos"), ("conversiones", "transf."), ("golpes", "golpes"), ("drops", "drops"))
                         if m.get(k)]}

    filas, leyenda = R.con_zonas(datos["clasificacion"], datos["competicion"], datos["grupo"])
    top = [{"pos": f["posicion"], "nombre": nombres.equipo_corto(f["equipo"]), "escudo": R.escudo_equipo(f["equipo"], escudos),
            "pt": f["pt"], "pj": f["pj"], "zona": f["zona"]} for f in filas[:4]]
    tras = max((f["pj"] for f in datos["clasificacion"]), default=datos["jornada"])

    return {
        **props_base(datos["competicion"], datos["jornada"], datos["temporada"], tema),
        "gancho": gancho, "partidos": partidos[:MAX_PARTIDOS], "mvp": mvp,
        "top": top, "trasJornada": tras, "zonaTop": leyenda[0]["texto"] if leyenda else "",
    }
