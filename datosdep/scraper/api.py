"""Respuestas JSON de la web nueva del origen A -> modelos del bot (partidos, clasificación, árbitro)."""
from __future__ import annotations

from datetime import datetime

from datosdep.models import FilaClasificacion, Partido
from datosdep.scraper.enlaces import ocultar_a
from datosdep.scraper.texto import limpiar

ESTADOS = {"Finalizado": "jugado", "Pendiente": "pendiente", "En progreso": "en_juego"}


def _fecha(s) -> datetime | None:
    """'2026-11-08 12:00:00' (confirmada) o '2027-04-18' (solo el día)."""
    for formato in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
        try:
            return datetime.strptime(str(s), formato)
        except ValueError:
            continue
    return None


def equipos_de_torneo(t: dict) -> dict[int, tuple[str, str]]:
    """{id de equipo: (nombre, escudo)} de los partidos del torneo (la clasificación solo trae ids)."""
    out: dict[int, tuple[str, str]] = {}
    for p in t.get("partidos", []):
        for lado in ("l", "v"):
            e = p.get(lado) or {}
            if e.get("id") is not None:
                out.setdefault(int(e["id"]), (limpiar(e.get("n") or ""), ocultar_a(e.get("e") or "")))
    return out


def partidos_de_torneo(t: dict) -> list[Partido]:
    nombres_ronda = {int(n["jornada"]): limpiar(n.get("nombre") or "") for n in (t.get("nombres") or [])
                     if isinstance(n, dict) and str(n.get("jornada", "")).isdigit()}
    partidos = []
    # Como la web antigua: por jornada, luego por fecha y hora y, a igualdad, por el orden que da la federación.
    for p in sorted(t.get("partidos", []), key=lambda p: (int(p.get("j") or 0), str(p.get("fecha") or ""),
                                                           int(p.get("orden") or 0), int(p["id"]))):
        estado = ESTADOS.get(p.get("estado"), str(p.get("estado") or "").lower())
        j = int(p.get("j") or 0)
        ronda = nombres_ronda.get(j, "")
        if not ronda and "FINAL" in str(p.get("fase") or "").upper():
            ronda = limpiar(p.get("grupo") or "")  # eliminatoria: "CUARTOS DE FINAL", "SEMIFINALES"...
        partidos.append(Partido(
            id=int(p["id"]), jornada=0 if ronda else j, fecha=_fecha(p.get("fecha")),
            local=limpiar(p["l"]["n"]), visitante=limpiar(p["v"]["n"]),
            puntos_local=p.get("gl"), puntos_visitante=p.get("gv"), campo=limpiar(p.get("campo") or ""),
            estado=estado, grupo=None, ronda=ronda,  # como la página antigua: sin grupo cuando el torneo es uno solo
        ))
    return partidos


def ultima_jornada_jugada(t: dict) -> int:
    """Última jornada con algún partido finalizado (si no hay, la actual del torneo, o 1)."""
    jugadas = [int(p["j"]) for p in t.get("partidos", []) if p.get("estado") == "Finalizado" and p.get("j")]
    return max(jugadas) if jugadas else int(t.get("actual") or 1)


def filas_clasificacion(c: dict, equipos: dict[int, tuple[str, str]]) -> list[FilaClasificacion]:
    racha = c.get("racha") or {}
    out = []
    for r in sorted(c.get("filas") or [], key=lambda r: r["posicion"]):
        tid = int(r["id_equipo"])
        nombre, escudo = equipos.get(tid, (str(tid), ""))
        cols = r.get("cols") or {}
        resultados = [x.get("resultado") for x in sorted(racha.get(str(tid)) or [], key=lambda x: x["jornada"])]
        out.append(FilaClasificacion(
            posicion=r["posicion"], equipo=nombre, racha=[x for x in resultados if x and x != "-"][-5:],  # la tabla enseña los 5 últimos
            pt=r["puntos"], pj=r["jugados"], pg=r["ganados"], pe=r["empatados"], pp=r["perdidos"],
            tf=cols.get("TF", r["goles_a_favor"]), tc=cols.get("TC", r["goles_en_contra"]),
            dt=cols.get("DT", r["diferencia_goles"]), ef=cols.get("EF", r["ensayos"]),
            ec=cols.get("EC", r["ensayos_en_contra"]), de=cols.get("DE", r["ensayos"] - r["ensayos_en_contra"]),
            bo=r.get("bonus_ofensivo") or 0, bd=r.get("bonus_defensivo") or 0, escudo=escudo,
        ))
    return out


def arbitro_de_previo(p: dict) -> str | None:
    """El árbitro principal (no los asistentes ni el delegado) de la respuesta de `previo`."""
    for a in p.get("arbitros") or []:
        rol = str(a.get("rol") or "").upper()
        if rol.startswith("ARBITRO") and "ASISTENTE" not in rol:
            return limpiar(a.get("n") or "") or None
    return None
