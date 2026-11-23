"""Que nada pare el bot: red caída, Telegram saturado, ficheros rotos, una imagen que no se puede pintar..."""
import pytest
import requests

from datosdep import archivos, estado, fallos, telegram
from datosdep.scraper import origen_a


# --- Telegram -----------------------------------------------------------------------------------------------------

class _R:
    def __init__(self, cuerpo, status=200):
        self.cuerpo, self.status_code = cuerpo, status

    def json(self):
        if self.cuerpo is None:
            raise ValueError("no es JSON")
        return self.cuerpo


def _tg(monkeypatch, respuestas):
    llamadas = []

    def post(url, data=None, files=None, timeout=None):
        llamadas.append({"metodo": url.rsplit("/", 1)[-1], **(data or {})})
        r = respuestas.pop(0)
        if isinstance(r, Exception):
            raise r
        return r
    monkeypatch.setattr(telegram.requests, "post", post)
    return telegram.Telegram("x"), llamadas


OK = _R({"ok": True, "result": {"message_id": 1}})


def test_telegram_reintenta_cortes_saturacion_y_caidas(monkeypatch):
    tg, llamadas = _tg(monkeypatch, [requests.ConnectionError("corte"),
                                     _R({"ok": False, "error_code": 429, "parameters": {"retry_after": 3}}, 429),
                                     _R(None, 502), OK])
    assert tg.mensaje(1, "hola") == {"message_id": 1}
    assert len(llamadas) == 4


def test_telegram_formato_roto_se_manda_sin_formato(monkeypatch):
    tg, llamadas = _tg(monkeypatch, [_R({"ok": False, "error_code": 400, "description": "Bad Request: can't parse entities"}), OK])
    tg.mensaje(1, "<b>Rialta &amp; Co</b> <3")
    assert "parse_mode" not in llamadas[1] and llamadas[1]["text"] == "Rialta & Co <3"


def test_telegram_error_definitivo_no_se_repite(monkeypatch):
    tg, llamadas = _tg(monkeypatch, [_R({"ok": False, "error_code": 403, "description": "bot was blocked by the user"})])
    with pytest.raises(RuntimeError, match="blocked"):
        tg.mensaje(1, "hola")
    assert len(llamadas) == 1


def test_telegram_texto_largo_en_varios_mensajes_con_botones_al_final(monkeypatch):
    tg, llamadas = _tg(monkeypatch, [OK, OK, OK])
    tg.mensaje(1, ("una línea de texto\n" * 600), botones=[[("Vale", "ok")]])
    assert len(llamadas) == 3 and all(len(c["text"]) <= 4096 for c in llamadas)
    assert "reply_markup" in llamadas[-1] and "reply_markup" not in llamadas[0]


def test_telegram_reintento_con_fichero_lo_manda_entero(monkeypatch, tmp_path):
    leidos = []

    def post(url, data=None, files=None, timeout=None):
        leidos.append(files["photo"].read())
        if len(leidos) == 1:
            raise requests.ConnectionError("corte")
        return OK
    monkeypatch.setattr(telegram.requests, "post", post)
    foto = tmp_path / "f.jpg"
    foto.write_bytes(b"datos de la foto")
    telegram.Telegram("x").foto(1, foto, "pie " * 400)
    assert leidos == [b"datos de la foto", b"datos de la foto"]


# --- API de la federación ------------------------------------------------------------------------------------------

def test_api_reintenta_cortes_pero_no_bloqueos(monkeypatch):
    c = origen_a.OrigenA()
    intentos = []

    def una(tipo, params, lenta):
        intentos.append(1)
        if len(intentos) < 3:
            raise requests.ConnectionError("Connection reset by peer")
        return b'{"ok": 1}'
    monkeypatch.setattr(c, "_pedir_api_una", una)
    assert c._pedir_api("torneo", {}, False) == b'{"ok": 1}' and len(intentos) == 3

    intentos.clear()

    def bloqueo(tipo, params, lenta):
        intentos.append(1)
        raise origen_a.AccesoRestringido("429")
    monkeypatch.setattr(c, "_pedir_api_una", bloqueo)
    with pytest.raises(origen_a.AccesoRestringido):
        c._pedir_api("torneo", {}, False)
    assert len(intentos) == 1


# --- ficheros y estado ---------------------------------------------------------------------------------------------

def test_estado_roto_usa_la_copia_anterior(tmp_path, monkeypatch):
    monkeypatch.setattr(estado, "ESTADO", tmp_path)
    estado.guardar_bot({"chat_id": 1, "offset": 5})
    estado.guardar_bot({"chat_id": 1, "offset": 6})
    (tmp_path / "bot.json").write_text("{roto", encoding="utf-8")  # p. ej. conflicto de git o corte a medias
    assert estado.bot()["offset"] == 5
    (tmp_path / "bot.json.bak").write_text("tampoco", encoding="utf-8")
    assert estado.bot() == {"offset": 0, "chat_id": None, "esperando": None}


def test_escritura_atomica_no_deja_temporales(tmp_path):
    ruta = tmp_path / "a" / "x.json"
    archivos.escribir(ruta, "1")
    archivos.escribir(ruta, b"2", copia=True)
    assert ruta.read_text() == "2" and (tmp_path / "a" / "x.json.bak").read_text() == "1"
    assert not list((tmp_path / "a").glob("*.tmp"))


# --- avisos al dueño -----------------------------------------------------------------------------------------------

class _TgFalso:
    def __init__(self):
        self.enviados = []

    def mensaje(self, chat_id, texto, **k):
        self.enviados.append((chat_id, texto))


def _fallo():
    try:
        {}["x"]
    except KeyError as e:
        return e


def test_usuario_no_ve_codigo_y_dueno_recibe_el_detalle_una_vez(tmp_path, monkeypatch):
    monkeypatch.setattr(estado, "ESTADO", tmp_path)
    estado.guardar_bot({"chat_id": 99})
    tg = _TgFalso()
    for _ in range(3):
        fallos.manejar(tg, 7, _fallo(), que="la clasificación")
    al_usuario = [t for c, t in tg.enviados if c == 7]
    al_dueno = [t for c, t in tg.enviados if c == 99]
    assert len(al_usuario) == 3 and all("File" not in t and "Traceback" not in t for t in al_usuario)
    assert len(al_dueno) == 1 and "KeyError" in al_dueno[0]


def test_fallos_de_la_web_se_explican_sin_molestar_al_dueno(tmp_path, monkeypatch):
    monkeypatch.setattr(estado, "ESTADO", tmp_path)
    estado.guardar_bot({"chat_id": 99})
    tg = _TgFalso()
    fallos.manejar(tg, 7, requests.ConnectionError("reset"), que="la clasificación")
    fallos.manejar(tg, 7, origen_a.AccesoRestringido("429"), que="la clasificación")
    assert [c for c, _ in tg.enviados] == [7, 7]
    assert "no responde" in tg.enviados[0][1] and "limitando" in tg.enviados[1][1]


# --- imágenes ------------------------------------------------------------------------------------------------------

def test_un_slide_roto_no_tumba_el_carrusel(monkeypatch, tmp_path):
    from datosdep.render import render

    descartados = []

    def html(datos, slides, formato="post", tema=None):
        if any(s["clave"] == "roto" for s in slides):
            raise KeyError("dato que falta")
        return "<html></html>"
    monkeypatch.setattr(render, "html_post", html)
    monkeypatch.setattr(render, "AL_DESCARTAR", lambda e, clave: descartados.append(clave))
    monkeypatch.setattr(render, "_pintar", lambda datos, slides, destino, f, t: [s["clave"] for s in slides])
    salida = render.renderizar_slides({}, [{"clave": "a"}, {"clave": "roto"}, {"clave": "b"}], tmp_path)
    assert salida == ["a", "b"] and descartados == ["roto"]


def test_navegador_caido_se_relanza_y_se_repite(monkeypatch, tmp_path):
    from datosdep.render import render

    intentos, cerrados = [], []

    def pintar(datos, slides, destino, f, t):
        intentos.append(1)
        if len(intentos) == 1:
            raise render.ErrorNavegador("Target page, context or browser has been closed")
        return ["ok"]
    monkeypatch.setattr(render, "_slides_que_se_pueden_pintar", lambda d, s, f, t: s)
    monkeypatch.setattr(render, "_pintar", pintar)
    monkeypatch.setattr(render._NAV, "cerrar", lambda: cerrados.append(1))
    assert render.renderizar_slides({}, [{"clave": "a"}], tmp_path) == ["ok"]
    assert len(intentos) == 2 and cerrados == [1]
