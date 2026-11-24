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

# Bandera de cada selección (nombre en castellano -> fichero de assets/banderas)
BANDERA = {
    "España": "es", "Francia": "fr", "Nueva Zelanda": "nz", "Fiyi": "fj", "Australia": "au", "Argentina": "ar",
    "Sudáfrica": "za", "EEUU": "us", "Gran Bretaña": "gb", "Inglaterra": "gb-eng", "Escocia": "gb-sct",
    "Gales": "gb-wls", "Irlanda": "ie", "Italia": "it", "Portugal": "pt", "Alemania": "de", "Bélgica": "be",
    "Países Bajos": "nl", "Suiza": "ch", "Georgia": "ge", "Rumanía": "ro", "Polonia": "pl", "Chequia": "cz",
    "Ucrania": "ua", "Suecia": "se", "Canadá": "ca", "Uruguay": "uy", "Chile": "cl", "Brasil": "br",
    "Colombia": "co", "Paraguay": "py", "México": "mx", "Samoa": "ws", "Tonga": "to", "Japón": "jp", "China": "cn",
    "Hong Kong": "hk", "Kenia": "ke", "Uganda": "ug", "Zimbabue": "zw", "Madagascar": "mg", "Túnez": "tn",
    "Papúa Nueva Guinea": "pg", "Filipinas": "ph", "Corea del Sur": "kr", "Kazajistán": "kz", "Tailandia": "th",
    "Namibia": "na", "Marruecos": "ma",
}


def banderas(nombres) -> dict[str, str]:
    """{nombre: 'bandera:código'} para el filtro de escudos de las plantillas."""
    return {n: f"bandera:{BANDERA[n]}" for n in nombres if n in BANDERA}

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

def nivel(evento: dict) -> int:
    """1 = circuito principal (donde juega España); 2 y 3 = divisiones de ascenso (SVNS 2, SVNS 3)."""
    m = re.search(r"\bSVNS(?: ([23]))?\b", str(evento.get("label", "")))
    return 0 if not m else int(m[1] or 1)


def _fecha_evento(e: dict, campo: str) -> date:
    return date.fromisoformat(e[campo]["label"])


def _sexo(e: dict) -> str:
    return "f" if e.get("sport") == "wrs" or "Women" in str(e.get("label", "")) else "m"


def torneo(hoy: date | None = None) -> dict | None:
    """El torneo de Sevens en curso o el próximo.

    {'ciudad', 'desde', 'hasta', 'eventos': {'m': ev, 'f': ev} (circuito principal),
     'finde': {id: ev} (todos los torneos de ese fin de semana, de cualquier división)}."""
    hoy = hoy or datetime.now(MADRID).date()
    c = cliente()
    todos = [e for dep in ("mrs", "wrs") for e in c.eventos(dep, hoy - timedelta(days=4), hoy + timedelta(days=120))
             if nivel(e) and _fecha_evento(e, "end") >= hoy]
    principales = sorted((e for e in todos if nivel(e) == 1), key=lambda e: e["start"]["millis"])
    if not principales:
        return None
    sede = principales[0]
    inicio = _fecha_evento(sede, "start")
    por_sexo = {}
    for e in principales:
        if e.get("abbr") == sede.get("abbr") and abs((_fecha_evento(e, "start") - inicio).days) <= 3:
            por_sexo.setdefault(_sexo(e), e)
    desde = min(_fecha_evento(e, "start") for e in por_sexo.values())
    hasta = max(_fecha_evento(e, "end") for e in por_sexo.values())
    finde = {e["id"]: e for e in todos
             if _fecha_evento(e, "start") <= hasta and _fecha_evento(e, "end") >= desde - timedelta(days=2)}
    return {"ciudad": ciudad(sede), "eventos": por_sexo, "desde": desde, "hasta": hasta, "finde": finde}


def _partido(m: dict, evento: dict) -> dict | None:
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
    return {
        "cuando": cuando, "sexo": _sexo(evento), "nivel": nivel(evento), "evento": evento["id"],
        "fin_evento": _fecha_evento(evento, "end"), "fase": fase(m.get("eventPhase")),
        "local": nombre_equipo(crudos[0]), "visitante": nombre_equipo(crudos[1]),
        "hueco_local": es_hueco(crudos[0]), "hueco_visitante": es_hueco(crudos[1]),
        "marcador": f"{puntos[0]}-{puntos[1]}" if (jugado or en_juego) and None not in puntos else "",
        "en_juego": en_juego and not jugado, "gana": gana,
    }


def partidos(t: dict, todo_el_finde: bool = False) -> list[dict]:
    """Partidos del circuito principal o, con todo_el_finde, de todas las divisiones de ese fin de semana."""
    eventos = t["finde"] if todo_el_finde else {e["id"]: e for e in t["eventos"].values()}
    out = []
    for m in cliente().partidos_de(list(eventos)):
        ev = next((eventos[e["id"]] for e in m.get("events") or [] if e.get("id") in eventos), None)
        if ev and (p := _partido(m, ev)):
            out.append(p)
    return sorted(out, key=lambda p: p["cuando"])


def paises(t: dict) -> list[str]:
    """Países que juegan ese fin de semana (cualquier división), por orden alfabético."""
    nombres = {p[lado] for p in partidos(t, True) for lado in ("local", "visitante")
               if not p[f"hueco_{lado}"]}
    return sorted(nombres, key=lambda n: (n != ESPANA, n))


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


# ---- vistas --------------------------------------------------------------------------------------------------------

SEXO = {"m": "Masculino", "f": "Femenino"}
CODIGO_PAIS = {c: n for n, c in BANDERA.items()}


def pais_de(vista: str) -> str | None:
    """'pes' -> 'España', 'par' -> 'Argentina'... None si la vista no es de un país."""
    return CODIGO_PAIS.get(vista[1:]) if vista.startswith("p") else None


def _de_la_vista(t: dict, vista: str) -> tuple[list[dict], str | None]:
    """(partidos de la vista, país destacado)."""
    if pais := pais_de(vista):
        return [p for p in partidos(t, True) if pais in (p["local"], p["visitante"])], pais
    return [p for p in partidos(t) if p["sexo"] == vista], ESPANA


def _fila(p: dict, por_pais: bool, destacado: str) -> dict:
    etiqueta = p["fase"]
    if por_pais:
        partes = ["Masc" if p["sexo"] == "m" else "Fem"]
        if p["nivel"] > 1:
            partes.append(f"Div. {p['nivel']}")  # división de ascenso
        etiqueta = " · ".join(partes + [p["fase"]])
    return {**p, "hora": p["cuando"].strftime("%H:%M"), "fase": etiqueta,
            "esp_local": p["local"] == destacado, "esp_visitante": p["visitante"] == destacado}


def _trocear(filas: list, cabida: int) -> list[list]:
    n = max(1, -(-len(filas) // cabida))
    tam = -(-len(filas) // n)  # partes igual de llenas
    return [filas[i:i + tam] for i in range(0, len(filas), tam)]


def slides(t: dict, lista: list[dict], vista: str, formato: str = "historia", destacado: str = ESPANA) -> list[dict]:
    """Una imagen por día (para subirlas cada día); un día muy largo se parte en varias.

    vista: 'p' + código de país (pes, par, puy...: sus partidos de chicos y chicas, de cualquier división)
    o 'm' / 'f' (circuito principal entero de un sexo)."""
    if not lista:
        return []
    pais = pais_de(vista)
    dias = sorted({p["cuando"].date() for p in lista})
    nota = ""
    if pais:
        fin = max(p["fin_evento"] for p in lista)  # aún le quedan días de torneo sin rival decidido
        if fin > dias[-1]:
            nota = f"El {etiqueta_dia(fin).lower()} juega las eliminatorias según su puesto en el grupo."
    sub = (f"{pais} en {t['ciudad']}" if pais else f"Sevens {SEXO[vista].lower()} · {t['ciudad']}") + " · hora española"
    out = []
    for d in dias:
        del_dia = [_fila(p, bool(pais), destacado) for p in lista if p["cuando"].date() == d]
        for i, trozo in enumerate(_trocear(del_dia, FILAS[formato]), 1):
            out.append({"tipo": "sevens", "clave": f"sevens_{vista}_{d:%m%d}_{i}", "titulo": etiqueta_dia(d),
                        "subtitulo": sub, "pagina": "", "bloques": [{"nombre": "", "partidos": trozo}], "nota": "",
                        "alto_fila": max(ALTO_FILA[formato][0], min(ALTO_FILA[formato][1], ALTO_UTIL[formato] // max(1, len(trozo))))})
    if nota:
        out[-1]["nota"] = nota
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
    """Imágenes de la vista ('pes'/'par'/... = un país, 'm', 'f', 'g' = grupos) del torneo en curso o el próximo."""
    t = torneo(hoy)
    if not t:
        return [], None
    desde, hasta = t["desde"], t["hasta"]
    if vista == "g":
        lista = slides_grupos(t)
    else:
        ps, destacado = _de_la_vista(t, vista)
        lista = slides(t, ps, vista, formato, destacado)
        if ps and pais_de(vista):  # un país de otra división puede empezar antes (p. ej. el viernes)
            desde = min(desde, ps[0]["cuando"].date())
    if not lista:
        return [], t
    destino = destino or Path(tempfile.mkdtemp(prefix="sevens_"))
    cfg = cargar_config()
    base = {"competicion": next(iter(cfg["competiciones"])), "grupo": "unico", "jornada": None,
            "temporada": cfg["temporada"], "escudos": banderas(BANDERA),
            "cabecera": {"nombre": f"Sevens · {t['ciudad']}", "sub": rango_fechas(desde, hasta), "grupo": None}}
    return renderizar_slides(base, lista, destino, formato, tema), t


def texto(vista: str, hoy: date | None = None) -> str:
    """Resumen en texto para Telegram."""
    t = torneo(hoy)
    if not t:
        return ""
    lista, _ = _de_la_vista(t, vista)
    por_pais = bool(pais_de(vista))
    lineas, dia = [], None
    for p in lista:
        if p["cuando"].date() != dia:
            dia = p["cuando"].date()
            lineas.append(f"\n📅 {etiqueta_dia(dia)}")
        sexo = f"{'♂' if p['sexo'] == 'm' else '♀'} " if por_pais else ""
        div = f"Div. {p['nivel']} · " if por_pais and p["nivel"] > 1 else ""
        lineas.append(f"  {p['cuando']:%H:%M} {sexo}{p['local']} {p['marcador'] or 'vs'} {p['visitante']}  ({div}{p['fase']})")
    return f"🏉 Sevens · {t['ciudad']} (hora española){''.join(chr(10) + x for x in lineas)}".strip()
