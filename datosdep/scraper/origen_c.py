"""Origen C: partidos internacionales (selecciones de XV y de Sevens de todos los países).

API pública de solo lectura. Se pide con calma: pausa entre consultas, lo reciente se guarda unos minutos en
memoria y lo ya terminado en disco. La dirección va en el secreto ORIGEN_C_URL (no se escribe en el código).
"""
from __future__ import annotations

import gzip
import hashlib
import json
import os
import time
from datetime import date
from pathlib import Path

import requests

BASE = os.environ.get("ORIGEN_C_URL", "").rstrip("/")
AGENTE = "rugby-es-datos/0.1"
PAUSA_S = 1.0
TTL_S = 300  # lo de un torneo en marcha cambia: se vuelve a pedir a los 5 minutos
POR_PAGINA = 100  # el máximo que acepta
MAX_PAGINAS = 20
CACHE = Path(__file__).resolve().parents[2] / ".cache" / "origen_c"


class SinAcceso(RuntimeError):
    """No configurado, limitando peticiones (403/429) o respuesta que no es la esperada."""


class OrigenC:
    def __init__(self):
        self.sesion = requests.Session()
        self.sesion.headers["User-Agent"] = AGENTE
        self._memoria: dict[str, tuple[float, object]] = {}
        self._ultima = 0.0
        self._bloqueado_hasta = 0.0

    def _get(self, ruta: str, params: dict | None = None, guardar: bool = False):
        """JSON de `ruta`. guardar=True: lo ya pedido se lee del disco (datos que ya no cambian)."""
        if not BASE:
            raise SinAcceso("falta configurar ORIGEN_C_URL")
        clave = hashlib.sha1(json.dumps([ruta, params], sort_keys=True).encode()).hexdigest()[:20]
        disco = CACHE / f"{clave}.json.gz"
        if guardar and disco.exists():
            try:
                return json.loads(gzip.decompress(disco.read_bytes()))
            except (OSError, ValueError):
                pass
        if clave in self._memoria and time.monotonic() - self._memoria[clave][0] < TTL_S:
            return self._memoria[clave][1]
        try:
            datos = self._pedir(ruta, params)
        except (SinAcceso, requests.RequestException):
            if clave in self._memoria:  # sin red o limitados: lo último que se tuvo
                return self._memoria[clave][1]
            raise
        self._memoria[clave] = (time.monotonic(), datos)
        if guardar:
            CACHE.mkdir(parents=True, exist_ok=True)
            tmp = disco.with_suffix(".tmp")
            tmp.write_bytes(gzip.compress(json.dumps(datos).encode(), 9))
            os.replace(tmp, disco)
        return datos

    def _pedir(self, ruta: str, params: dict | None):
        if time.time() < self._bloqueado_hasta:
            raise SinAcceso("limitando peticiones; se espera antes de volver a pedir")
        for intento in range(3):
            espera = PAUSA_S - (time.monotonic() - self._ultima)
            if espera > 0:
                time.sleep(espera)
            try:
                r = self.sesion.get(f"{BASE}/{ruta}", params=params, timeout=30)
            except (requests.ConnectionError, requests.Timeout):
                if intento == 2:
                    raise
                time.sleep(5 * (intento + 1))
                continue
            finally:
                self._ultima = time.monotonic()
            if r.status_code in (403, 429):
                self._bloqueado_hasta = time.time() + 3600
                raise SinAcceso(f"{ruta}: {r.status_code}")
            if r.status_code >= 500 and intento < 2:
                time.sleep(5 * (intento + 1))
                continue
            r.raise_for_status()
            try:
                return r.json()
            except ValueError as e:
                raise SinAcceso(f"{ruta}: respuesta que no es JSON") from e
        raise SinAcceso(f"{ruta}: sin respuesta")

    # ---- consultas -------------------------------------------------------------------------------------------

    def _lista(self, ruta: str, params: dict, guardar: bool = False) -> list[dict]:
        out, pagina = [], 0
        while pagina < MAX_PAGINAS:
            d = self._get(ruta, {**params, "sort": "asc", "pageSize": POR_PAGINA, "page": pagina}, guardar)
            if not isinstance(d, dict) or not isinstance(d.get("content"), list):
                raise SinAcceso(f"{ruta}: respuesta sin lista")
            out += d["content"]
            pagina += 1
            if pagina >= int((d.get("pageInfo") or {}).get("numPages") or 0):
                break
        return out

    def eventos(self, deporte: str, desde: date, hasta: date) -> list[dict]:
        """Torneos de un deporte (mru, wru: XV; mrs, wrs: Sevens) que empiezan entre dos fechas."""
        return self._lista("rugby/v3/event", {"sports": deporte, "startDate": desde.isoformat(),
                                              "endDate": hasta.isoformat()})

    def partidos_de(self, ids_eventos: list[str]) -> list[dict]:
        """Partidos de uno o varios torneos."""
        return self._lista("rugby/v3/match", {"events": ",".join(ids_eventos)}) if ids_eventos else []

    def partidos_equipo(self, id_equipo: str, desde: date, hasta: date) -> list[dict]:
        return self._lista("rugby/v3/match", {"teams": id_equipo, "startDate": desde.isoformat(),
                                              "endDate": hasta.isoformat()}, guardar=hasta < date.today())

    def evento(self, id_evento: str) -> dict:
        return self._get(f"rugby/v3/event/{id_evento}")

    def clasificacion(self, id_evento: str) -> list[dict]:
        d = self._get(f"rugby/v3/event/{id_evento}/standings")
        return d.get("tables") or [] if isinstance(d, dict) else []


_CLIENTE: OrigenC | None = None


def cliente() -> OrigenC:
    global _CLIENTE
    if _CLIENTE is None:
        _CLIENTE = OrigenC()
    return _CLIENTE
