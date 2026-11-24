"""Selecciones: torneos de Sevens (horario y resultados de todos los países, España y los grupos).

Las horas van en hora española. Los nombres de países, fases y cruces se traducen al castellano.
"""
from __future__ import annotations

import re
import tempfile
from datetime import date, datetime, timedelta
from pathlib import Path

from datosdep.core.partido_jornada import etiqueta_dia, rango_fechas
from datosdep.estado import MADRID
from datosdep.pipeline import cargar_config
from datosdep.render.render import renderizar_slides
from datosdep.scraper.origen_c import cliente

PAISES = {
    "Spain": "España", "France": "Francia", "New Zealand": "Nueva Zelanda", "Fiji": "Fiyi", "Australia": "Australia",
    "Argentina": "Argentina", "South Africa": "Sudáfrica", "USA": "EEUU", "United States": "EEUU",
    "Great Britain": "Gran Bretaña", "England": "Inglaterra", "Scotland": "Escocia", "Wales": "Gales",
    "Ireland": "Irlanda", "Italy": "Italia", "Portugal": "Portugal", "Germany": "Alemania", "Belgium": "Bélgica",
    "Netherlands": "Países Bajos", "Switzerland": "Suiza", "Georgia": "Georgia", "Romania": "Rumanía",
    "Poland": "Polonia", "Czechia": "Chequia", "Ukraine": "Ucrania", "Sweden": "Suecia",
    "Canada": "Canadá", "Uruguay": "Uruguay", "Chile": "Chile", "Brazil": "Brasil", "Colombia": "Colombia",
    "Paraguay": "Paraguay", "Mexico": "México", "Samoa": "Samoa", "Tonga": "Tonga", "Japan": "Japón",
    "China": "China", "Hong Kong China": "Hong Kong", "Hong Kong": "Hong Kong", "Kenya": "Kenia",
    "Uganda": "Uganda", "Zimbabwe": "Zimbabue", "Madagascar": "Madagascar", "Tunisia": "Túnez",
    "Papua New Guinea": "Papúa Nueva Guinea", "Philippines": "Filipinas", "Korea": "Corea del Sur",
    "Kazakhstan": "Kazajistán", "Thailand": "Tailandia", "Namibia": "Namibia", "Morocco": "Marruecos",
}
ESPANA = "España"

ORDINAL = {"1st": "1.º", "2nd": "2.º", "3rd": "3.º", "4th": "4.º", "5th": "5.º", "6th": "6.º", "7th": "7.º", "8th": "8.º"}

ESTADOS_JUGADO = {"C"}  # terminado
ESTADOS_EN_JUEGO = {"L", "L1", "L2", "LHT", "LT1", "LT2", "LT", "HT"}
ESTADOS_ANULADO = {"CC", "A", "P"}  # cancelado, abandonado, aplazado

FILAS = {"historia": 15, "post": 9}
ALTO_UTIL = {"historia": 1160, "post": 740}
ALTO_FILA = {"historia": (70, 96), "post": (64, 80)}


# ---- traducciones -----------------------------------------------------------------------------------------------

def nombre_equipo(crudo: str) -> str:
    """'Spain 7s' -> 'España'; '1st Pool A' -> '1.º Grupo A'; 'Winner M15' -> 'Ganador P15'."""
    n = re.sub(r"\s+7s$", "", (crudo or "").strip())
    if m := re.fullmatch(r"(1st|2nd|3rd|4th|5th|6th|7th|8th) Pool (\w+)", n):
        return f"{ORDINAL[m[1]]} Grupo {m[2]}"
    if m := re.fullmatch(r"(Winner|Loser) [MW]?(\d+)", n):
        return f"{'Ganador' if m[1] == 'Winner' else 'Perdedor'} P{m[2]}"
    return PAISES.get(n, n)


def es_hueco(crudo: str) -> bool:
    """Equipo aún sin decidir (depende de otro resultado)."""
    return bool(re.match(r"(1st|2nd|3rd|4th|5th|6th|7th|8th) Pool |(Winner|Loser) ", crudo or ""))


def fase(crudo: str | None) -> str:
    f = (crudo or "").strip()
    if m := re.fullmatch(r"Pool (\w)", f):
        return f"Grupo {m[1]}"
    fijas = {"Pool Pool": "Grupo", "Cup Final": "Final", "Cup Semi Finals": "Semifinal", "Cup Semi Final": "Semifinal",
             "Cup Quarter Finals": "Cuartos", "Cup Quarter Final": "Cuartos", "3rd Place Play-Off": "3.er puesto",
             "5th Place Semi Final": "Semi 5.º puesto", "5th Place Play-Off": "5.º puesto",
             "7th Place Play-Off": "7.º puesto", "9th Place Play-Off": "9.º puesto"}
    if f in fijas:
        return fijas[f]
    if m := re.fullmatch(r"(\d+)\w\w Place (Play-Off|Semi Finals?)", f):
        return f"{'Semi ' if 'Semi' in m[2] else ''}{m[1]}.º puesto"
    return f


def ciudad(evento: dict) -> str:
    c = (evento.get("abbr") or str(evento.get("label", "")).rsplit(" - ", 1)[-1]).strip()
    return {"Cape Town": "Ciudad del Cabo", "Dubai": "Dubái", "Singapore": "Singapur", "New York": "Nueva York",
            "Sao Paulo": "São Paulo", "Bordeaux": "Burdeos", "Hong Kong": "Hong Kong"}.get(c, c)


# ---- datos ---------------------------------------------------------------------------------------------------------

def _primera(evento: dict) -> bool:
    """Circuito principal (donde juega España), no las divisiones de ascenso (SVNS 2, SVNS 3)."""
    return bool(re.search(r"\bSVNS\b(?! [23]\b)", str(evento.get("label", ""))))


def _fecha_evento(e: dict, campo: str) -> date:
    return date.fromisoformat(e[campo]["label"])


def torneo(hoy: date | None = None) -> dict | None:
    """El torneo de Sevens en curso o el próximo: {'ciudad', 'desde', 'hasta', 'eventos': {'m': ev, 'f': ev}}."""
    hoy = hoy or datetime.now(MADRID).date()
    c = cliente()
    eventos = [e for dep in ("mrs", "wrs") for e in c.eventos(dep, hoy - timedelta(days=4), hoy + timedelta(days=120))
               if _primera(e) and _fecha_evento(e, "end") >= hoy]
    if not eventos:
        return None
    eventos.sort(key=lambda e: e["start"]["millis"])
    sede = eventos[0]
    pareja = [e for e in eventos if e.get("abbr") == sede.get("abbr")
              and abs((_fecha_evento(e, "start") - _fecha_evento(sede, "start")).days) <= 3]
    por_sexo = {}
    for e in pareja:
        sexo = "f" if e.get("sport") == "wrs" or "Women" in e["label"] else "m"
        por_sexo.setdefault(sexo, e)
    return {"ciudad": ciudad(sede), "eventos": por_sexo,
            "desde": min(_fecha_evento(e, "start") for e in por_sexo.values()),
            "hasta": max(_fecha_evento(e, "end") for e in por_sexo.values())}


def _partido(m: dict, sexo: str) -> dict | None:
    equipos = m.get("teams") or []
    if len(equipos) != 2 or not (m.get("time") or {}).get("millis"):
        return None
    estado = str(m.get("status") or "U")
    if estado in ESTADOS_ANULADO:
        return None
    crudos = [t.get("name") or "" for t in equipos]
    cuando = datetime.fromtimestamp(m["time"]["millis"] / 1000, MADRID)
    jugado, en_juego = estado in ESTADOS_JUGADO, estado in ESTADOS_EN_JUEGO or estado.startswith("L")
    puntos = list(m.get("scores") or [None, None])
    gana = None
    if jugado and None not in puntos and puntos[0] != puntos[1]:
        gana = 0 if puntos[0] > puntos[1] else 1
    loc, vis = nombre_equipo(crudos[0]), nombre_equipo(crudos[1])
    return {
        "cuando": cuando, "sexo": sexo, "fase": fase(m.get("eventPhase")), "local": loc, "visitante": vis,
        "hueco_local": es_hueco(crudos[0]), "hueco_visitante": es_hueco(crudos[1]),
        "esp_local": loc == ESPANA, "esp_visitante": vis == ESPANA,
        "marcador": f"{puntos[0]}-{puntos[1]}" if (jugado or en_juego) and None not in puntos else "",
        "en_juego": en_juego and not jugado, "gana": gana,
    }


def partidos(t: dict) -> list[dict]:
    ids = {e["id"]: sexo for sexo, e in t["eventos"].items()}
    out = []
    for m in cliente().partidos_de(list(ids)):
        sexo = next((ids[e["id"]] for e in m.get("events") or [] if e.get("id") in ids), None)
        if sexo and (p := _partido(m, sexo)):
            out.append(p)
    return sorted(out, key=lambda p: p["cuando"])


def grupos(t: dict) -> list[dict]:
    """Clasificación de cada grupo (masculino y femenino)."""
    out = []
    for sexo, e in sorted(t["eventos"].items(), key=lambda x: x[0] != "m"):
        for tabla in cliente().clasificacion(e["id"]):
            filas = []
            for i, f in enumerate(tabla.get("entries") or [], 1):
                filas.append({"posicion": f.get("positionLabel") or i, "equipo": nombre_equipo((f.get("team") or {}).get("name")),
                              "pj": f.get("played") or 0, "pt": f.get("points") or 0,
                              "zona": "titulo" if i <= 2 else ""})
            if filas:
                out.append({"nombre": f"{'Masculino' if sexo == 'm' else 'Femenino'} · {fase(tabla.get('label'))}",
                            "filas": filas})
    return out


# ---- imágenes ----------------------------------------------------------------------------------------------------

SEXO = {"m": "Masculino", "f": "Femenino"}


def _fila(p: dict, con_sexo: bool) -> dict:
    etiqueta = p["fase"] if not con_sexo else f"{'Masc' if p['sexo'] == 'm' else 'Fem'} · {p['fase']}"
    return {**p, "hora": p["cuando"].strftime("%H:%M"), "fase": etiqueta}


def _trocear(filas: list, cabida: int) -> list[list]:
    n = max(1, -(-len(filas) // cabida))
    tam = -(-len(filas) // n)  # páginas igual de llenas
    return [filas[i:i + tam] for i in range(0, len(filas), tam)]


def slides(t: dict, lista: list[dict], vista: str, formato: str = "historia") -> list[dict]:
    """vista: 'es' (España, chicos y chicas), 'm' o 'f' (torneo entero de un sexo)."""
    if vista == "es":
        lista = [p for p in lista if ESPANA in (p["local"], p["visitante"])]
    else:
        lista = [p for p in lista if p["sexo"] == vista]
    if not lista:
        return []
    dias = sorted({p["cuando"].date() for p in lista})
    cabida = FILAS[formato]
    # Cada página: uno o varios días enteros (si caben, con su cabecera); un día largo se reparte en varias.
    paginas: list[list[tuple[date, list]]] = []
    for d in dias:
        del_dia = [_fila(p, vista == "es") for p in lista if p["cuando"].date() == d]
        filas_pag = sum(1 + len(f) for _, f in paginas[-1]) if paginas else 0
        if paginas and filas_pag + 1 + len(del_dia) <= cabida:
            paginas[-1].append((d, del_dia))
            continue
        for trozo in _trocear(del_dia, cabida):
            paginas.append([(d, trozo)])
    nota = ""
    if vista == "es" and t["hasta"] not in dias:
        nota = f"El {etiqueta_dia(t['hasta']).lower()} juega las eliminatorias según su puesto en el grupo."
    sub = {"es": f"España en {t['ciudad']} · hora española", "m": f"Sevens masculino · {t['ciudad']} · hora española",
           "f": f"Sevens femenino · {t['ciudad']} · hora española"}[vista]
    total = len(paginas)
    out = []
    for i, pag in enumerate(paginas, 1):
        if len(pag) == 1:
            titulo, bloques = etiqueta_dia(pag[0][0]), [{"nombre": "", "partidos": pag[0][1]}]
        else:
            titulo = {"es": "España", "m": "Masculino", "f": "Femenino"}[vista]
            bloques = [{"nombre": etiqueta_dia(d), "partidos": f} for d, f in pag]
        n_filas = sum(len(b["partidos"]) + (1 if b["nombre"] else 0) for b in bloques)
        out.append({"tipo": "sevens", "clave": f"sevens_{vista}_{i}", "titulo": titulo, "subtitulo": sub,
                    "pagina": f"{i}/{total}" if total > 1 else "", "bloques": bloques,
                    "nota": nota if i == total else "",
                    "alto_fila": max(ALTO_FILA[formato][0], min(ALTO_FILA[formato][1], ALTO_UTIL[formato] // max(1, n_filas)))})
    return out


def slides_grupos(t: dict) -> list[dict]:
    g = grupos(t)
    if not any(f["pj"] for x in g for f in x["filas"]):
        return []  # aún no se ha jugado nada: la tabla saldría toda a cero
    return [{"tipo": "grupos", "clave": "sevens_grupos", "grupos": g, "compacto": len(g) > 4,
             "titulo": f"Grupos · {t['ciudad']}", "bajada": "Clasificación de cada grupo",
             "leyenda": [{"color": "titulo", "texto": "A semifinales"}]}] if g else []


def imagenes(vista: str, formato: str = "historia", destino: Path | None = None, tema: str | None = None,
             hoy: date | None = None) -> tuple[list[Path], dict | None]:
    """Imágenes de la vista ('es', 'm', 'f', 'g' = grupos) del torneo de Sevens en curso o el próximo."""
    t = torneo(hoy)
    if not t:
        return [], None
    lista = slides_grupos(t) if vista == "g" else slides(t, partidos(t), vista, formato)
    if not lista:
        return [], t
    destino = destino or Path(tempfile.mkdtemp(prefix="sevens_"))
    cfg = cargar_config()
    base = {"competicion": next(iter(cfg["competiciones"])), "grupo": "unico", "jornada": None,
            "temporada": cfg["temporada"], "escudos": {},
            "cabecera": {"nombre": f"Sevens · {t['ciudad']}", "sub": rango_fechas(t["desde"], t["hasta"]), "grupo": None}}
    return renderizar_slides(base, lista, destino, formato, tema), t


def texto(vista: str, hoy: date | None = None) -> str:
    """Resumen en texto para Telegram."""
    t = torneo(hoy)
    if not t:
        return ""
    lista = partidos(t)
    if vista == "es":
        lista = [p for p in lista if ESPANA in (p["local"], p["visitante"])]
    elif vista in SEXO:
        lista = [p for p in lista if p["sexo"] == vista]
    lineas, dia = [], None
    for p in lista:
        if p["cuando"].date() != dia:
            dia = p["cuando"].date()
            lineas.append(f"\n📅 {etiqueta_dia(dia)}")
        sexo = f"{'♂' if p['sexo'] == 'm' else '♀'} " if vista == "es" else ""
        medio = p["marcador"] or "vs"
        lineas.append(f"  {p['cuando']:%H:%M} {sexo}{p['local']} {medio} {p['visitante']}  ({p['fase']})")
    return f"🏉 Sevens · {t['ciudad']} (hora española){''.join(chr(10) + x for x in lineas)}".strip()
