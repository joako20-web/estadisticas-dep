"""Parsers puros (bytes -> modelos) de las páginas de el origen A."""
from __future__ import annotations

import re
from datetime import datetime
from urllib.parse import parse_qs, urlparse

from bs4 import BeautifulSoup

from datosdep.models import (
    PUNTOS,
    Acta,
    Competicion,
    Evento,
    FilaClasificacion,
    Jugador,
    JugadorTemporada,
    Partido,
)
from datosdep.scraper.enlaces import ocultar_a
from datosdep.scraper.texto import decodificar, limpiar


def _soup(raw: bytes) -> BeautifulSoup:
    return BeautifulSoup(decodificar(raw), "lxml")


def _txt(tag) -> str:
    return limpiar(tag.get_text(" ")) if tag is not None else ""


def _int(s: str, default: int = 0) -> int:
    m = re.search(r"-?\d+", s or "")
    return int(m.group()) if m else default


def _qs(url: str, key: str) -> int | None:
    v = parse_qs(urlparse(url).query).get(key)
    return int(v[0]) if v else None


def tipo_evento(original: str) -> str:
    o = original.lower()
    if o.startswith("ensayo de castigo"):
        return "ensayo_castigo"
    if o.startswith("ensayo"):
        return "ensayo"
    if o.startswith("conversion"):
        return "conversion"
    if "castigo a palos" in o or o.startswith("golpe"):
        return "golpe"
    if o.startswith("drop"):
        return "drop"
    if "definitiva" in o:
        return "roja"
    if "(roja)" in o:
        return "roja20"
    if o.startswith("expulsion temporal"):
        return "amarilla"
    return "otro"


def estadisticas(raw: bytes) -> Competicion:
    """mostrar_estadisticas.php: todos los partidos de la fase + tabla de jugadores."""
    s = _soup(raw)
    comp = Competicion()

    tabla = s.find("table", class_="stx-tabla--partidos")
    for tr in tabla.find_all("tr", class_="stx-fila-link"):
        td = tr.find_all("td")
        res = re.findall(r"\d+", _txt(td[3]))
        try:
            fecha = datetime.strptime(_txt(td[1]), "%d/%m/%Y %H:%M")
        except ValueError:
            fecha = None
        etiqueta = _txt(td[0])
        es_jornada = re.fullmatch(r"J\d+", etiqueta)
        comp.partidos.append(
            Partido(
                id=_qs(tr["data-href"], "id_partido"),
                jornada=_int(etiqueta) if es_jornada else 0,
                fecha=fecha,
                local=_txt(td[2]),
                visitante=_txt(td[4]),
                puntos_local=int(res[0]) if len(res) == 2 else None,
                puntos_visitante=int(res[1]) if len(res) == 2 else None,
                campo=_txt(td[5]),
                estado=tr.get("data-stx-estado", ""),
                grupo=int(tr["data-stx-grupo"]) if tr.get("data-stx-grupo", "").isdigit() else None,
                ronda="" if es_jornada else etiqueta,
            )
        )

    for t in s.find_all("table", class_="stx-tabla"):
        cab = [_txt(th) for th in t.find_all("th")]
        if cab[:2] != ["Jugador", "Equipo"]:
            continue
        for tr in t.find_all("tr", class_="stx-fila-link"):
            td = tr.find_all("td")
            comp.jugadores.append(
                JugadorTemporada(
                    id=_qs(tr["data-href"], "id_jugador"),
                    nombre=_txt(td[0]),
                    equipo=_txt(td[1]),
                    pj=_int(_txt(td[2])),
                    puntos=_int(_txt(td[3])),
                    ensayos=_int(_txt(td[4])),
                    amarillas=_int(_txt(td[5])),
                    rojas=_int(_txt(td[6])),
                )
            )
    return comp


def acta(raw: bytes, id_partido: int) -> Acta:
    s = _soup(raw)

    eventos: list[Evento] = []
    cab_eventos = s.find("h2", string=lambda x: x and "Eventos" in x)
    if cab_eventos:
        tabla = cab_eventos.find_next("table")
        for tr in tabla.find("tbody").find_all("tr"):
            td = tr.find_all("td")
            if len(td) < 5:
                continue
            original = _txt(td[1])
            nums = re.findall(r"\d+", _txt(td[2]))
            eventos.append(
                Evento(
                    minuto=_int(_txt(td[0])),
                    tipo=tipo_evento(original),
                    tipo_original=original,
                    marcador=(int(nums[0]), int(nums[1])) if len(nums) == 2 else None,
                    equipo=_txt(td[3]),
                    jugador=_txt(td[4]),
                )
            )

    def alineacion(div) -> tuple[str, list[Jugador]]:
        # Acta aún sin rellenar (o rehecha por el origen): sin cabecera ni alineación.
        if div is None or div.find("tbody") is None:
            return "", []
        thead = div.find("thead")
        img = thead.find("img") if thead else None
        equipo = limpiar(img.get("alt", "")) if img else ""
        jugadores = []
        for tr in div.find("tbody").find_all("tr"):
            nombre = tr.find("td", class_="nombre-jugador")
            td = tr.find_all("td")
            if nombre is None or len(td) < 4:
                continue  # cabecera "Técnicos" y cuerpo técnico
            dorsal = _int(_txt(td[2]), default=-1)
            if dorsal < 0:
                continue
            img = tr.find("img", class_="foto_jugador_acta")
            foto = ocultar_a(img["src"]) if img and img.get("src") else ""
            jugadores.append(Jugador(_txt(nombre), dorsal, _int(_txt(td[3])), foto))
        return equipo, jugadores

    local, al_local = alineacion(s.find("div", class_="local"))
    visitante, al_vis = alineacion(s.find("div", class_="visitante"))
    return Acta(id_partido, local, visitante, eventos, al_local, al_vis)


def acta_json(raw: bytes, id_partido: int) -> Acta:
    """Acta desde el JSON del proxy de el origen A (la página HTML ahora se pinta con JavaScript)."""
    import json

    resp = json.loads(raw)
    if not resp.get("status"):
        raise ValueError(f"acta {id_partido}: {resp.get('message', 'respuesta sin datos')}")
    d = resp["data"]
    part = d["partido"]
    local, visitante = limpiar(part["local"]["nombre"]), limpiar(part["visitante"]["nombre"])
    nombres = {int(k): limpiar(v.get("nombre", "")) for k, v in (d.get("equipos") or {}).items()}
    nombres[int(part["local"]["id_equipo"])] = local
    nombres[int(part["visitante"]["id_equipo"])] = visitante

    eventos: list[Evento] = []
    marcador = {local: 0, visitante: 0}
    for e in d.get("eventos") or []:
        tipo = tipo_evento(e["tipo_evento"])
        equipo = nombres.get(int(e["id_equipo"]), "")
        if tipo in PUNTOS and equipo in marcador:
            marcador[equipo] += PUNTOS[tipo]
        eventos.append(
            Evento(
                minuto=_int(str(e.get("minuto", "")).split(":")[0]),
                tipo=tipo,
                tipo_original=limpiar(e["tipo_evento"]),
                marcador=(marcador[local], marcador[visitante]),
                equipo=equipo,
                jugador=limpiar(e.get("jugador") or ""),
            )
        )

    def foto(url: str) -> str:
        return ocultar_a(url or "")

    al: dict[str, list[Jugador]] = {local: [], visitante: []}
    for j in d.get("alineaciones") or []:
        equipo = nombres.get(int(j["id_equipo"]), "")
        if equipo in al and j.get("dorsal") is not None and int(j["dorsal"]) > 0:  # dorsal 0 = fuera de la convocatoria
            al[equipo].append(Jugador(limpiar(j["nombre_jugador"] or ""), int(j["dorsal"]), _int(str(j.get("goles", 0))), foto(j.get("url_foto") or "")))
    eventos.reverse()  # como la página antigua: el más reciente primero
    return Acta(id_partido, local, visitante, eventos, al[local], al[visitante])


def clasificacion(raw: bytes) -> list[FilaClasificacion]:
    s = _soup(raw)
    filas = []
    tabla = s.find("table", class_="clasificacion")
    if tabla is None:
        # La origen a veces rehace los grupos (cambio de fase): el viejo queda sin tabla.
        return filas
    for i, tr in enumerate(tabla.find_all("tr")[1:], 1):
        td = tr.find_all("td")
        if len(td) < 16:
            continue
        a = td[1].find("a")
        nombre = limpiar(
            " ".join(t for t in a.find_all(string=True, recursive=False))
        )
        racha = [limpiar(x.get_text()) for x in td[2].find_all("span", class_="racha")]
        n = [_int(_txt(x)) for x in td[3:16]]
        img = td[1].find("img", class_="escudo_tabla_clasificacion")
        escudo = ocultar_a(img["src"]) if img and img.get("src") else ""
        filas.append(
            # Sin partidos jugados el origen A pone posición 0: se usa el orden de la tabla
            FilaClasificacion(_int(_txt(td[0])) or i, nombre, [r for r in racha if r != "-"], *n, escudo=escudo)
        )
    return filas


def ids_partidos_jornada(raw: bytes) -> list[int]:
    """competicion.php: ids de partido de la jornada mostrada."""
    return sorted({int(x) for x in re.findall(rb"mostrarActa\((\d+)\)", raw)})
