"""Reel de previa de la jornada: cara a cara del partido destacado, cada partido
de la próxima jornada con día, hora y campo, la agenda completa y cierre."""
from __future__ import annotations

from datetime import datetime

from datosdep.especiales import partido_destacado
from datosdep.pipeline import es_descanso
from datosdep.render import nombres
from datosdep.videos.base import equipo, props_base

COMPOSICION = "ReelPrevia"
MAX_PARTIDOS = 8  # con más, el reel pasa de 22 s

DIAS_CORTOS = ["LUN", "MAR", "MIÉ", "JUE", "VIE", "SÁB", "DOM"]
MESES_CORTOS = ["ENE", "FEB", "MAR", "ABR", "MAY", "JUN", "JUL", "AGO", "SEP", "OCT", "NOV", "DIC"]


def cuando(fecha_iso: str | None) -> dict:
    """Día de la semana, hora y fecha cortos ("SÁB", "16:00", "10 OCT").

    Sin fecha, todo vacío; a las 00:00 el origen A suele indicar "hora sin fijar"."""
    if not fecha_iso:
        return {"dia": "", "hora": "", "fecha": ""}
    f = datetime.fromisoformat(fecha_iso)
    hora = f.strftime("%H:%M")
    return {"dia": DIAS_CORTOS[f.weekday()], "hora": "" if hora == "00:00" else hora,
            "fecha": f"{f.day} {MESES_CORTOS[f.month - 1]}"}


def campo(texto: str | None) -> str:
    """Nombre del campo sin la coletilla entre paréntesis y en tipo título."""
    return nombres.titulo((texto or "").split("(")[0].strip())


def _orden(p: dict) -> tuple:
    return (p["fecha"] is None, p["fecha"] or "", p["id"])


def props(datos: dict, tema: str = "tele", id_destacado: int | None = None) -> dict:
    """`id_destacado` fuerza el partido del cara a cara (si no, lo elige `partido_destacado`)."""
    prox = datos.get("proxima_jornada") or {}
    pendientes = sorted((p for p in prox.get("partidos") or []
                         if p.get("puntos_local") is None and not es_descanso(p)), key=_orden)
    if not pendientes:
        raise RuntimeError(f"no hay próxima jornada con partidos pendientes tras la jornada {datos['jornada']}")
    escudos = datos["escudos"]
    tabla = {f["equipo"]: f for f in datos.get("clasificacion", [])}

    forzado = next((p for p in pendientes if p["id"] == id_destacado), None) if id_destacado else None
    destacado = forzado or partido_destacado(datos) or pendientes[0]
    lados = []
    for eq in (destacado["local"], destacado["visitante"]):
        fila = tabla.get(eq, {})
        lados.append({**equipo(eq, escudos), "pos": fila.get("posicion"), "pt": fila.get("pt")})

    # El destacado siempre entra en la lista aunque haya más partidos que el máximo
    lista = pendientes[:MAX_PARTIDOS]
    if destacado not in lista:
        lista = sorted(lista[:-1] + [destacado], key=_orden)
    partidos = [{"local": equipo(p["local"], escudos), "visitante": equipo(p["visitante"], escudos),
                 **cuando(p["fecha"]), "campo": campo(p.get("campo")), "destacado": p["id"] == destacado["id"]}
                for p in lista]

    return {
        **props_base(datos["competicion"], prox["numero"], datos["temporada"], tema),
        "destacado": {"local": lados[0], "visitante": lados[1], **cuando(destacado["fecha"]),
                      "campo": campo(destacado.get("campo"))},
        "partidos": partidos,
        "total": len(pendientes),
        "equiposTabla": len(tabla),
        "idDestacado": destacado["id"],  # para el botón «Cambiar destacado» (Remotion lo ignora)
    }
