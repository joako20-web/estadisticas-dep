"""Acta completa en PDF -> JSON con el formato del proxy de el origen A.

El PDF tiene dos columnas (local a la izquierda, visitante a la derecha). Las alineaciones salen de
la página 1 y los eventos de la "Línea temporal" (por dorsal y minuto). No trae fotos de jugadores.
Si algo no cuadra (marcador, dorsales) se lanza ValueError y no se guarda nada.
"""
from __future__ import annotations

import io
import json
import re

from datosdep.scraper.texto import limpiar

COL = 290  # x que separa la columna del local de la del visitante
NOMBRE_X = 62  # x donde empieza el nombre del jugador en la columna del local (en la del visitante, +COL)
TOL_Y = 3  # fragmentos a menos de esta distancia vertical son la misma fila
Fila = list[tuple[float, str]]  # (x, texto) ordenado por x


def fragmentos(raw: bytes) -> list[list[tuple[float, float, str]]]:
    """Por página, los trozos de texto del PDF como (y, x, texto)."""
    from pypdf import PdfReader

    if not raw.startswith(b"%PDF"):
        raise ValueError("la respuesta no es un PDF")
    paginas = []
    for pagina in PdfReader(io.BytesIO(raw)).pages:
        trozos: list[tuple[float, float, str]] = []

        def visitar(texto, cm, tm, fd, fs, _t=trozos):
            if texto.strip():
                _t.append((tm[5], tm[4], texto.strip()))

        pagina.extract_text(visitor_text=visitar)
        paginas.append(trozos)
    return paginas


def _filas(trozos: list[tuple[float, float, str]]) -> list[tuple[float, Fila]]:
    filas: list[tuple[float, Fila]] = []
    for y, x, t in sorted(trozos, key=lambda f: (-f[0], f[1])):
        if filas and abs(filas[-1][0] - y) <= TOL_Y:
            filas[-1][1].append((x, t))
        else:
            filas.append((y, [(x, t)]))
    return [(y, sorted(f)) for y, f in filas]


def _nombre(apellidos_nombre: str) -> str:
    """'GIL COMESAÑA, AGUSTIN SEBASTIAN' -> 'AGUSTIN SEBASTIAN GIL COMESAÑA' (como en el JSON del proxy)."""
    s = limpiar(apellidos_nombre)
    if "," not in s:
        return s
    ape, nom = s.split(",", 1)
    return limpiar(f"{nom} {ape}")


def _lado(x: float) -> int:
    return 0 if x < COL else 1


def _alineaciones(paginas) -> tuple[dict[int, str], dict[int, str]]:
    """Dorsal -> nombre de cada equipo, entre 'JUGADORES' y 'STAFF TÉCNICO'."""
    crudo: tuple[dict[int, str], dict[int, str]] = ({}, {})
    ultimo: list[int | None] = [None, None]
    dentro = False
    for trozos in paginas:
        for _, fila in _filas(trozos):
            textos = " ".join(t for _, t in fila)
            if textos.strip() == "JUGADORES":
                dentro = True
                continue
            if "STAFF" in textos:
                dentro = False
                break
            if "APELLIDOS" in textos:  # cabecera de titulares o de suplentes
                ultimo = [None, None]
                continue
            if not dentro:
                continue
            for lado in (0, 1):
                x_nombre = NOMBRE_X + lado * COL  # la columna de posición ("PI", "T,PD") queda a su izquierda
                celdas = [(x, t) for x, t in fila if _lado(x) == lado]
                dorsal = next((int(t) for x, t in celdas if t.isdigit() and x < x_nombre - 10), None)
                nombre = next((t for x, t in celdas if "," in t and x >= x_nombre - 3), None)
                if dorsal and nombre:
                    crudo[lado][dorsal] = nombre
                    ultimo[lado] = dorsal
                elif dorsal is None and ultimo[lado]:
                    resto = next((t for x, t in celdas if x >= x_nombre - 3 and not t.isdigit() and t.isupper()), None)
                    if resto:  # nombre largo partido en dos líneas
                        d = ultimo[lado]
                        unir = "" if crudo[lado][d].endswith("-") else " "
                        crudo[lado][d] += unir + resto
    return ({d: _nombre(n) for d, n in crudo[0].items()}, {d: _nombre(n) for d, n in crudo[1].items()})


def _marcador(paginas) -> tuple[int, int]:
    for _, fila in _filas(paginas[0]):
        izq = [int(t) for x, t in fila if t.isdigit() and 200 <= x < COL and len(t) <= 3]
        der = [int(t) for x, t in fila if t.isdigit() and x >= 480 and len(t) <= 3]
        if izq and der:
            return izq[0], der[0]
    raise ValueError("no encuentro el marcador en el PDF")


def _linea_temporal(paginas) -> tuple[list[str], list[str], list[tuple[int, int, str, int]]]:
    """Nombres de los equipos y eventos (lado, segundos, texto, dorsal) de la 'Línea temporal'."""
    nombres: list[list[str]] = [[], []]
    eventos: list[tuple[int, int, str, int]] = []
    ultimo: dict[int, list | None] = {0: None, 1: None}
    estado = 0  # 0 = busco el título, 1 = nombres de equipo, 2 = tabla de eventos
    for trozos in paginas:
        for _, fila in _filas(trozos):
            textos = " ".join(t for _, t in fila)
            if "LÍNEA TEMPORAL" in textos or "LINEA TEMPORAL" in textos:
                estado = 1
                continue
            if estado == 0:
                continue
            if "Minuto" in textos and "EVENTO" in textos:
                estado = 2
                continue
            if estado == 1:
                if not re.search(r"Página|^\d+$", textos):
                    for x, t in fila:
                        nombres[_lado(x)].append(t)
                continue
            if "Página" in textos or "TCPDF" in textos or re.fullmatch(r"\d{8}-\d{6}", textos.strip()):
                continue
            for lado in (0, 1):
                celdas = [(x, t) for x, t in fila if _lado(x) == lado]
                if not celdas:
                    continue
                m = re.fullmatch(r"(\d+):(\d+)", celdas[0][1])
                if m:
                    resto = [t for _, t in celdas[1:] if t.upper() != "EQUIPO"]  # ensayo de castigo: "EQUIPO" en vez de dorsal
                    dorsal = int(resto[0]) if resto and resto[0].isdigit() else 0
                    texto = next((t for t in resto if not t.isdigit()), "")
                    ev = [lado, int(m[1]) * 60 + int(m[2]), texto, dorsal]
                    eventos.append(ev)  # type: ignore[arg-type]
                    ultimo[lado] = ev
                elif ultimo[lado] is not None and celdas[0][1] and not celdas[0][1].isdigit():
                    ultimo[lado][2] += " " + celdas[0][1]  # texto del evento partido en dos líneas
    if not nombres[0] or not nombres[1]:
        raise ValueError("no encuentro los nombres de los equipos en el PDF")
    return limpiar(" ".join(nombres[0])), limpiar(" ".join(nombres[1])), [tuple(e) for e in eventos]  # type: ignore[misc]


def acta_a_json(paginas) -> bytes:
    """Páginas ya extraídas (ver `fragmentos`) -> bytes JSON como los del proxy de el origen A."""
    from datosdep.models import PUNTOS
    from datosdep.scraper.parsers import tipo_evento

    local, visitante, crudos = _linea_temporal(paginas)
    equipos = [local, visitante]
    # El nombre puede venir repetido (equipo y club con el mismo nombre en dos líneas)
    for i, n in enumerate(equipos):
        mitad = len(n) // 2
        if len(n) % 2 == 0 and n[:mitad].strip() == n[mitad:].strip():
            equipos[i] = n[:mitad].strip()
    al = _alineaciones(paginas)
    marcador = _marcador(paginas)
    eventos = []
    puntos = [0, 0]
    puntos_jugador: dict[tuple[int, int], int] = {}
    for lado, seg, texto, dorsal in sorted(crudos, key=lambda e: (e[1], e[0])):
        if texto.lower().startswith("reemplazo"):
            continue
        tipo = tipo_evento(texto)
        jugador = al[lado].get(dorsal, "")
        if dorsal and not jugador:
            raise ValueError(f"el dorsal {dorsal} ({texto}) no está en la alineación")
        pts = PUNTOS.get(tipo, 0)
        puntos[lado] += pts
        if pts and dorsal:
            puntos_jugador[(lado, dorsal)] = puntos_jugador.get((lado, dorsal), 0) + pts
        eventos.append({"id_jugador": None, "tipo_evento": texto, "minuto": f"{seg // 60:02d}:{seg % 60:02d}",
                        "jugador": jugador, "id_equipo": lado + 1, "tantos": pts})
    if (puntos[0], puntos[1]) != marcador:
        raise ValueError(f"los eventos suman {tuple(puntos)} y el marcador del PDF es {marcador}")
    alineaciones = [
        {"id_equipo": lado + 1, "dorsal": d, "nombre_jugador": n, "goles": puntos_jugador.get((lado, d), 0), "url_foto": ""}
        for lado in (0, 1) for d, n in sorted(al[lado].items())
    ]
    datos = {"status": True, "data": {
        "partido": {"local": {"id_equipo": 1, "nombre": equipos[0], "resultado": marcador[0]},
                    "visitante": {"id_equipo": 2, "nombre": equipos[1], "resultado": marcador[1]}},
        "eventos": eventos, "alineaciones": alineaciones, "equipos": {}}}
    return json.dumps(datos, ensure_ascii=False).encode("utf-8")


def pdf_a_json(raw_pdf: bytes) -> bytes:
    return acta_a_json(fragmentos(raw_pdf))
