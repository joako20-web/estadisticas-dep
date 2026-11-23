"""Cliente mínimo de la API de bots de Telegram (sondeo con getUpdates)."""
from __future__ import annotations

import html
import json
import re
import time
from contextlib import ExitStack
from pathlib import Path

import requests


LIMITE_MENSAJE = 4000  # Telegram admite 4096 caracteres por mensaje
LIMITE_PIE = 1000  # y 1024 en el pie de una foto o vídeo


def _recortar(texto: str, limite: int) -> str:
    if len(texto or "") <= limite:
        return texto
    corte = texto[:limite - 1]
    corte = corte[:corte.rfind("\n")] if "\n" in corte[limite // 2:] else corte
    return re.sub(r"<[^>]*$", "", corte) + "…"  # sin dejar una etiqueta HTML a medias


def _trocear(texto: str, limite: int) -> list[str]:
    """Parte un texto largo por saltos de línea (o donde se pueda) sin pasar del límite."""
    trozos, actual = [], ""
    for linea in (texto or "").split("\n"):
        while len(linea) > limite:  # una sola línea más larga que el límite
            if actual:
                trozos.append(actual)
                actual = ""
            trozos.append(linea[:limite])
            linea = linea[limite:]
        if actual and len(actual) + 1 + len(linea) > limite:
            trozos.append(actual)
            actual = linea
        else:
            actual = f"{actual}\n{linea}" if actual else linea
    trozos.append(actual)
    return [t for t in trozos if t] or [""]


class Telegram:
    def __init__(self, token: str):
        self.base = f"https://api.telegram.org/bot{token}"
        self.base_ficheros = f"https://api.telegram.org/file/bot{token}"

    def _post(self, metodo: str, files=None, **datos):
        """Llamada a Telegram, a prueba de cortes: reintenta si la red falla, si Telegram está caído (5xx) o si
        pide esperar (429, respetando su `retry_after`). Si el texto no se puede leer como HTML, lo manda sin formato."""
        datos = {k: json.dumps(v) if isinstance(v, (dict, list)) else v for k, v in datos.items() if v is not None}
        ultimo: Exception | None = None
        for intento in range(4):
            for f in (files or {}).values():
                f.seek(0)  # al reintentar, el fichero se vuelve a mandar desde el principio
            try:
                r = requests.post(f"{self.base}/{metodo}", data=datos, files=files, timeout=120)
            except requests.ConnectionError as e:  # no llegó a Telegram: es seguro repetir
                ultimo = e
                time.sleep(3 * (intento + 1))
                continue
            try:
                cuerpo = r.json()
            except ValueError:
                cuerpo = {"ok": False, "error_code": r.status_code, "description": f"respuesta no válida ({r.status_code})"}
            if cuerpo.get("ok"):
                return cuerpo["result"]
            codigo, desc = cuerpo.get("error_code") or r.status_code, str(cuerpo.get("description") or "")
            if codigo == 429:
                espera = int((cuerpo.get("parameters") or {}).get("retry_after") or 5)
                ultimo = RuntimeError(f"Telegram {metodo}: {desc}")
                time.sleep(min(espera, 60) + 1)
                continue
            if codigo >= 500:
                ultimo = RuntimeError(f"Telegram {metodo}: {desc}")
                time.sleep(3 * (intento + 1))
                continue
            if "can't parse entities" in desc and datos.get("parse_mode"):
                # un carácter que rompe el formato: el mismo texto, sin etiquetas
                datos.pop("parse_mode")
                for campo in ("text", "caption"):
                    if campo in datos:
                        datos[campo] = html.unescape(re.sub(r"<[^>]+>", "", str(datos[campo])))
                continue
            raise RuntimeError(f"Telegram {metodo}: {desc}")
        raise RuntimeError(f"Telegram {metodo}: sin respuesta tras varios intentos ({ultimo})")

    def actualizaciones(self, offset: int, espera: int = 0) -> list[dict]:
        """getUpdates con sondeo largo: espera hasta `espera` segundos a que llegue algo."""
        datos = {"offset": offset, "timeout": espera,
                 "allowed_updates": json.dumps(["message", "callback_query"])}
        try:
            r = requests.post(f"{self.base}/getUpdates", data=datos, timeout=espera + 30)
            return r.json().get("result", [])
        except requests.RequestException:
            return []

    @staticmethod
    def _teclado(botones):
        if not botones:
            return None
        return {"inline_keyboard": [[{"text": t, "callback_data": d} for t, d in fila] for fila in botones]}

    def mensaje(self, chat_id, texto: str, botones: list[list[tuple[str, str]]] | None = None,
                teclado_fijo: list[list[str]] | None = None) -> dict:
        teclado = self._teclado(botones)
        if teclado_fijo:
            teclado = {"keyboard": [[{"text": t} for t in fila] for fila in teclado_fijo],
                       "resize_keyboard": True, "is_persistent": True}
        trozos = _trocear(texto, LIMITE_MENSAJE)
        for t in trozos[:-1]:  # un texto largo va en varios mensajes; los botones, en el último
            self._post("sendMessage", chat_id=chat_id, text=t, parse_mode="HTML", disable_web_page_preview=True)
        return self._post(
            "sendMessage", chat_id=chat_id, text=trozos[-1], parse_mode="HTML",
            reply_markup=teclado, disable_web_page_preview=True,
        )

    def editar(self, chat_id, message_id: int, texto: str, botones=None) -> None:
        try:
            self._post("editMessageText", chat_id=chat_id, message_id=message_id, text=texto,
                       parse_mode="HTML", reply_markup=self._teclado(botones) or {"inline_keyboard": []})
        except RuntimeError:
            pass  # p. ej. "message is not modified"

    def comandos(self, lista: list[tuple[str, str]]) -> None:
        self._post("setMyCommands", commands=[{"command": c, "description": d} for c, d in lista])

    def album(self, chat_id, imagenes: list[Path], como_archivo: bool = False) -> None:
        """Envía hasta 10 imágenes por álbum. `como_archivo` las manda sin comprimir."""
        tipo = "document" if como_archivo else "photo"
        if len(imagenes) == 1:
            with open(imagenes[0], "rb") as f:
                metodo = "sendDocument" if como_archivo else "sendPhoto"
                self._post(metodo, files={tipo: f}, chat_id=chat_id)
            return
        for i in range(0, len(imagenes), 10):
            lote = imagenes[i : i + 10]
            with ExitStack() as pila:
                files = {f"f{j}": pila.enter_context(open(p, "rb")) for j, p in enumerate(lote)}
                media = [{"type": tipo, "media": f"attach://f{j}"} for j in range(len(lote))]
                self._post("sendMediaGroup", files=files, chat_id=chat_id, media=media)

    def foto(self, chat_id, imagen: Path, texto: str = "") -> None:
        with open(imagen, "rb") as f:
            self._post("sendPhoto", files={"photo": f}, chat_id=chat_id, caption=_recortar(texto, LIMITE_PIE))

    def video(self, chat_id, ruta: Path, texto: str = "", botones=None) -> None:
        with open(ruta, "rb") as f:
            self._post("sendVideo", files={"video": f}, chat_id=chat_id, caption=_recortar(texto, LIMITE_PIE), parse_mode="HTML",
                       width=1080, height=1920, supports_streaming=True,
                       reply_markup=self._teclado(botones) if botones else None)

    def responder_boton(self, callback_id: str, texto: str = "") -> None:
        try:
            self._post("answerCallbackQuery", callback_query_id=callback_id, text=texto)
        except RuntimeError:
            pass  # el botón caducó (más de unos minutos): no importa

    def descargar(self, file_id: str) -> bytes:
        info = self._post("getFile", file_id=file_id)
        r = requests.get(f"{self.base_ficheros}/{info['file_path']}", timeout=60)
        r.raise_for_status()
        return r.content
