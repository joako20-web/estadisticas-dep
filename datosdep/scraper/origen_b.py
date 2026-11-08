"""Cliente de OrigenB, otra plataforma de resultados (regiones).

Misma interfaz que OrigenA (competicion, clasificacion, acta, imagen) para que el
resto del sistema funcione igual. El id de "grupo" es "<temporada>/<competicion>"
tal como aparece en la URL pública: .../public/calendar/67/54/combined/.
"""
from __future__ import annotations

import re
import zlib
from datetime import datetime
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from datosdep.models import Acta, Competicion, Evento, FilaClasificacion, Jugador, Partido
from datosdep.scraper.enlaces import ocultar_b
from datosdep.scraper.origen_a import OrigenA
from datosdep.scraper.texto import limpiar

TIPOS = {"E": "ensayo", "T": "conversion", "PC": "golpe", "P": "golpe", "D": "drop",
         "EC": "ensayo_castigo", "EP": "ensayo_castigo"}


def _soup(raw: bytes) -> BeautifulSoup:
    return BeautifulSoup(raw.decode("utf-8", "replace"), "lxml")


def _t(tag) -> str:
    return limpiar(tag.get_text(" ")) if tag is not None else ""


def _int(s: str, defecto: int = 0) -> int:
    m = re.search(r"-?\d+", s or "")
    return int(m.group()) if m else defecto


def _equipo(nombre: str) -> str:
    return limpiar(nombre).upper()


def _jugador(apellidos_nombre: str) -> str:
    """'Perez Arribas, Iraia' -> 'Iraia Perez Arribas' (nombre de pila primero)."""
    s = limpiar(apellidos_nombre)
    if "," in s:
        apellidos, nombre = (x.strip() for x in s.split(",", 1))
        s = f"{nombre} {apellidos}"
    return s.upper()


def _seccion(s: BeautifulSoup, titulo: str) -> list:
    """Bloques (portlets) cuyo título empieza por `titulo`, en orden de aparición."""
    out = []
    for h in s.find_all("h4"):
        if _t(h).startswith(titulo):
            out.append(h.find_parent("div", class_="portlet"))
    return out


def competicion(raw: bytes, id_grupo: str) -> Competicion:
    s = _soup(raw)
    comp = Competicion()
    for portlet in s.find_all(id=re.compile(r"^workingDayPortlet_\d+")):
        titulo = portlet.find_previous(lambda t: t.name in ("h3", "h4") and "jornada" in _t(t).lower())
        m = re.search(r"jornada\s*(\d+)", _t(titulo).lower()) if titulo else None  # "1. Jardunaldia/Jornada 1"
        jornada = int(m.group(1)) if m else 0
        for tr in portlet.find_all("tr", class_="eventRow"):
            td = tr.find_all("td")
            if len(td) < 6:
                continue
            fecha_txt = " ".join(td[0].get_text(" ").split())
            try:
                fecha = datetime.strptime(fecha_txt, "%d/%m/%Y %H:%M")
            except ValueError:
                fecha = None
            local = _equipo(td[1].find("span").get_text(" "))
            visitante = _equipo(td[5].find("span").get_text(" "))
            enlace = td[3].find("a", href=re.compile(r"match_statistics"))
            nums = re.findall(r"\d+", _t(td[3]))
            jugado = "eventEnded" in tr.get("class", []) and len(nums) == 2
            campo = td[5].find("small", class_="text-success")
            id_partido = _int(enlace["href"]) if enlace else None
            comp.partidos.append(Partido(
                # Sin enlace (partido sin jugar): id estable derivado del cruce
                id=id_partido or zlib.crc32(f"{id_grupo}|{jornada}|{local}|{visitante}".encode()),
                jornada=jornada, fecha=fecha, local=local, visitante=visitante,
                puntos_local=int(nums[0]) if jugado else None,
                puntos_visitante=int(nums[1]) if jugado else None,
                campo=_t(campo), estado="jugado" if jugado else "pendiente",
            ))
    return comp


def clasificacion(raw: bytes, base: str) -> list[FilaClasificacion]:
    s = _soup(raw)
    tab = s.find(id="classificationTab")
    tabla = tab.find("table") if tab else None
    if tabla is None:
        return []
    filas = []
    for i, tr in enumerate(tabla.find_all("tr")[1:], 1):
        td = tr.find_all("td")
        if len(td) < 14:
            continue
        img = td[1].find("img")
        escudo = ocultar_b(urljoin(base, img["src"])) if img and img.get("src") else ""
        n = [_int(_t(x)) for x in td[2:14]]  # J G E P TF TC DT EF EC BO BD PUNTOS
        pj, pg, pe, pp, tf, tc, dt, ef, ec, bo, bd, pt = n
        filas.append(FilaClasificacion(_int(_t(td[0])) or i, _equipo(_t(td[1])), [], pt, pj, pg, pe, pp,
                                       tf, tc, dt, ef, ec, ef - ec, bo, bd, escudo=escudo))
    return filas


def posiciones(titulares: list[Jugador], suplentes: list[Jugador]) -> list[Jugador]:
    """Pone en `dorsal` la posición real de cada jugador.

    En las regiones de OrigenB (Madrid, Cataluña, Euskadi, Andalucía) el número
    de la camiseta es libre (90, 111...), pero el acta lista a los titulares en orden de
    posición: el 9.º de la lista es el medio melé aunque lleve el 12. Si el equipo usa
    justo los dorsales 1-15 se respeta el dorsal (a veces la lista viene algo desordenada).
    Los suplentes van del 16 en adelante aunque su camiseta sea más baja.
    """
    numerados = sorted(j.dorsal for j in titulares) == list(range(1, 16))
    for i, j in enumerate(titulares):
        posicion = j.dorsal if numerados else i + 1
        if posicion != j.dorsal:
            j.camiseta, j.dorsal = j.dorsal, posicion
    for i, j in enumerate(suplentes):
        if j.dorsal <= 15:
            j.camiseta, j.dorsal = j.dorsal, 16 + i
    return titulares + suplentes


def acta(raw: bytes, id_partido: int, local: str, visitante: str) -> Acta:
    """Acta a partir de la página de estadísticas del partido.

    `local` y `visitante` son los nombres del calendario (los del acta pueden variar).
    """
    s = _soup(raw)
    alineaciones: list[list[Jugador]] = []
    for tabla in s.find_all("table"):
        cab = [_t(th) for th in tabla.find_all("th")]
        if not cab or cab[0] != "Dorsal":
            continue
        jugadores = []
        for tr in tabla.find_all("tr")[1:]:
            td = tr.find_all("td")
            if len(td) >= 3 and _int(_t(td[0]), -1) >= 0:
                jugadores.append(Jugador(_jugador(_t(td[2])), _int(_t(td[0]))))
        alineaciones.append(jugadores)
    # Orden en la página: titulares local, suplentes local, titulares visitante, suplentes visitante
    # (algunas actas no traen alineaciones o no traen banquillo)
    if len(alineaciones) >= 4:
        tit_l, sup_l, tit_v, sup_v = alineaciones[:4]
    elif len(alineaciones) >= 2:
        (tit_l, tit_v), sup_l, sup_v = alineaciones[:2], [], []
    else:
        tit_l, sup_l, tit_v, sup_v = (alineaciones or [[]])[0], [], [], []
    al_local = posiciones(tit_l, sup_l)
    al_vis = posiciones(tit_v, sup_v)

    eventos: list[Evento] = []
    for equipo, portlet in zip((local, visitante), _seccion(s, "Anotadores")):
        for tr in (portlet.find("tbody") or portlet).find_all("tr"):
            td = [_t(x) for x in tr.find_all("td")]
            if len(td) >= 3:
                eventos.append(Evento(_int(td[0]), TIPOS.get(td[1].upper(), "otro"), td[1], None, equipo, _jugador(td[2])))
    for titulo, tipo in (("Expulsiones temporales", "amarilla"), ("Expulsiones definitivas", "roja")):
        for portlet in _seccion(s, titulo):
            equipo = local if "local" in _t(portlet.find("h4")).lower() else visitante
            for tr in (portlet.find("tbody") or portlet).find_all("tr"):
                td = [_t(x) for x in tr.find_all("td")]
                if len(td) >= 3:
                    eventos.append(Evento(_int(td[2]), tipo, td[1], None, equipo, _jugador(td[0])))

    # Marcador acumulado tras cada evento (OrigenB no lo da)
    eventos.sort(key=lambda e: e.minuto)
    pl = pv = 0
    for e in eventos:
        if e.equipo == local:
            pl += e.puntos
        else:
            pv += e.puntos
        if e.puntos:
            e.marcador = (pl, pv)
    tantos: dict[tuple[str, str], int] = {}
    for e in eventos:
        tantos[(e.equipo, e.jugador)] = tantos.get((e.equipo, e.jugador), 0) + e.puntos
    for equipo, alineacion in ((local, al_local), (visitante, al_vis)):
        for j in alineacion:
            j.tantos = tantos.get((equipo, j.nombre), 0)
    return Acta(id_partido, local, visitante, eventos, al_local, al_vis)


class OrigenB(OrigenA):
    """Reutiliza la caché, las pausas y los reintentos del cliente de el origen A."""

    def __init__(self, base: str, **kw):
        super().__init__(**kw)
        self.base = base.rstrip("/")  # p. ej. $ORIGEN_B_URL/es
        self._partidos: dict[int, tuple[str, str]] = {}

    def _pagina(self, id_grupo: str) -> bytes:
        return self._get(f"{self.base}/public/calendar/{id_grupo}/combined/", {}, cachear=False)

    def competicion(self, id_grupo) -> Competicion:
        comp = competicion(self._pagina(str(id_grupo)), str(id_grupo))
        for p in comp.partidos:
            self._partidos[p.id] = (p.local, p.visitante)
        return comp

    def clasificacion(self, id_grupo) -> list[FilaClasificacion]:
        return clasificacion(self._pagina(str(id_grupo)), self.base)

    def acta(self, id_partido: int) -> Acta:
        raw = self._get(f"{self.base}/public/competition/{id_partido}/match_statistics/", {}, cachear=True)
        local, visitante = self._partidos.get(id_partido, ("", ""))
        if not local:  # sin calendario cargado: nombres del propio acta
            nombres = [_equipo(_t(h)) for h in _soup(raw).find_all("h4")]
            idx = nombres.index("EQUIPO LOCAL") if "EQUIPO LOCAL" in nombres else -1
            local, visitante = (nombres[idx + 1], nombres[idx + 3]) if idx >= 0 else ("", "")
        return acta(raw, id_partido, local, visitante)
