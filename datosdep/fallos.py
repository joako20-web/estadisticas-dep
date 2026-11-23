"""Qué se le dice a quien usa el bot cuando algo falla, y qué le llega al dueño.

Nadie ve código de error salvo el dueño, y al dueño le llega cada fallo distinto una sola vez al día
(con el detalle técnico, para poder pegarlo y arreglarlo).
"""
from __future__ import annotations

import hashlib
import html
import traceback

import requests

from datosdep import estado


def es_pasajero(e: BaseException) -> bool:
    """Cortes de red, tiempo agotado o servidor caído: lo normal es que se arregle solo reintentando."""
    if isinstance(e, (requests.ConnectionError, requests.Timeout)):
        return True
    if isinstance(e, requests.HTTPError) and e.response is not None and e.response.status_code >= 500:
        return True
    nombre = type(e).__name__
    return nombre in ("TimeoutError", "ConnectionResetError", "BrokenPipeError") or "Target page, context or browser has been closed" in str(e)


def explicar(e: BaseException, que: str = "esto") -> str:
    """Mensaje para quien pidió algo, sin código."""
    from datosdep.scraper.origen_a import AccesoRestringido, FuenteCambiada

    if isinstance(e, FuenteCambiada):
        return "⚠️ la web de resultados ha cambiado y ahora mismo no puedo leerla. Ya está avisado; vuelve a probar más tarde."
    if isinstance(e, AccesoRestringido):
        return ("⏳ la web de resultados está limitando las peticiones y esto no está guardado todavía. "
                "Lo estoy bajando poco a poco; prueba en unos minutos.")
    if es_pasajero(e):
        return f"⏳ la web de resultados no responde ahora mismo y no he podido preparar {que}. Prueba en unos minutos."
    return f"😕 no he podido preparar {que}. Ya he pasado el detalle para arreglarlo; prueba con otra cosa mientras tanto."


def _firma(e: BaseException) -> str:
    """Igual para el mismo fallo en el mismo sitio (aunque cambien los datos del mensaje)."""
    tb = traceback.extract_tb(e.__traceback__)
    sitio = f"{tb[-1].filename.rsplit('/', 1)[-1]}:{tb[-1].lineno}" if tb else ""
    return hashlib.sha1(f"{type(e).__name__}|{sitio}".encode()).hexdigest()[:12]


def avisar(tg, e: BaseException, contexto: str = "", a_quien=None) -> None:
    """Avisa al dueño con el detalle técnico, como mucho una vez al día por fallo distinto. Nunca lanza."""
    try:
        traceback.print_exception(e)
        b = estado.bot()
        dueno = a_quien or b.get("chat_id")
        if not dueno:
            return
        hoy = estado.ahora().strftime("%Y-%m-%d")
        vistos = b.get("fallos_avisados") or {}
        clave = _firma(e)
        if vistos.get(clave) == hoy:
            return
        vistos = {k: v for k, v in vistos.items() if v == hoy}  # solo los de hoy: no crece sin fin
        vistos[clave] = hoy
        b["fallos_avisados"] = vistos
        estado.guardar_bot(b)
        detalle = "".join(traceback.format_exception(e))[-700:]
        tg.mensaje(dueno, f"🛠 fallo{(' en ' + html.escape(contexto)) if contexto else ''} (te lo digo una vez al día; "
                          f"pégamelo si se repite):\n<code>{html.escape(detalle)}</code>")
    except Exception:
        traceback.print_exc()


def manejar(tg, chat_id, e: BaseException, que: str = "esto", contexto: str = "") -> None:
    """Explica el fallo a quien lo pidió y avisa al dueño (si no es fallo de la web, que ya tiene su aviso)."""
    from datosdep.scraper.origen_a import AccesoRestringido

    try:
        tg.mensaje(chat_id, explicar(e, que))
    except Exception:
        traceback.print_exc()
    if not isinstance(e, AccesoRestringido) and not es_pasajero(e):
        avisar(tg, e, contexto or que)
