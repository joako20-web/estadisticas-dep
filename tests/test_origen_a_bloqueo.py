"""el origen A devuelve 403/429: el cliente degrada sin reintentar ni esquivar."""
import requests

from datosdep.scraper import origen_a


class _Resp:
    def __init__(self, status, headers=None):
        self.status_code = status
        self.headers = headers or {}
        self.content = b""
        self.text = ""

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(str(self.status_code))


class _Sesion:
    headers: dict = {}

    def __init__(self, status):
        self.status = status
        self.llamadas = 0

    def get(self, *a, **k):
        self.llamadas += 1
        return _Resp(self.status)


def _cliente(tmp_path, status):
    c = origen_a.OrigenA()
    c.cache_dir = tmp_path
    c.sesion = _Sesion(status)
    return c


def test_acta_403_devuelve_vacia_y_no_reintenta(tmp_path, monkeypatch):
    monkeypatch.setenv("ORIGEN_A_ACTA_URL", "https://ejemplo.invalid/acta")
    monkeypatch.setattr(origen_a, "RAIZ_DATOS", tmp_path / "datos")
    c = _cliente(tmp_path, 403)
    a = c.acta(123)
    assert a.id_partido == 123
    assert c.actas_bloqueadas
    assert c.sesion.llamadas == 1
    c.acta(124)  # circuito abierto: ni una petición más
    assert c.sesion.llamadas == 1
    assert not list(tmp_path.iterdir())  # los fallos no se cachean ni se guardan


def test_429_bloquea_todo_el_sitio(tmp_path):
    c = _cliente(tmp_path, 429)
    try:
        c._get("competicion.php", {"x": 1}, cachear=False)
    except origen_a.AccesoRestringido:
        pass
    assert c.sesion.llamadas == 1
    assert c.acta(1).id_partido == 1
    assert c.sesion.llamadas == 1


def test_bloqueado_sirve_el_ultimo_dato_guardado(tmp_path):
    import gzip
    import hashlib

    c = _cliente(tmp_path, 429)
    params = {"x": 1}
    clave = hashlib.sha1(f"{origen_a.BASE}/competicion.php?{sorted(params.items())}".encode()).hexdigest()
    (tmp_path / f"{clave}.html.gz").write_bytes(gzip.compress(b"<html>viejo</html>"))
    assert c._get("competicion.php", params, cachear=False) == b"<html>viejo</html>"


def test_precalentar_no_pide_si_esta_bloqueado(tmp_path, monkeypatch):
    from datosdep import precalentar

    c = _cliente(tmp_path, 429)
    monkeypatch.setattr(precalentar, "compartido", lambda: c)
    monkeypatch.setattr(precalentar, "_cola", [("acta", 1), ("acta", 2)])
    c.acta(1)  # 429 -> circuito abierto
    n = c.sesion.llamadas
    assert precalentar.paso() is None
    assert c.sesion.llamadas == n


def test_error_de_red_sirve_dato_guardado(tmp_path, monkeypatch):
    import gzip
    import hashlib

    class Caida(_Sesion):
        def get(self, *a, **k):
            raise requests.ConnectionError("sin red")

    monkeypatch.setattr(origen_a.time, "sleep", lambda s: None)
    c = _cliente(tmp_path, 200)
    c.sesion = Caida(200)
    clave = hashlib.sha1(f"{origen_a.BASE}/clasificacion.php?{sorted({'a': 1}.items())}".encode()).hexdigest()
    (tmp_path / f"{clave}.html.gz").write_bytes(gzip.compress(b"guardado"))
    assert c._get("clasificacion.php", {"a": 1}, cachear=False) == b"guardado"


def test_importar_acta_manual_json_y_html(tmp_path, monkeypatch):
    from pathlib import Path

    from datosdep import importar_acta

    monkeypatch.setattr(origen_a, "RAIZ_DATOS", tmp_path / "data")
    fx = Path(__file__).parent / "fixtures"
    c = _cliente(tmp_path / "cache", 429)
    assert importar_acta.importar(17643, fx / "acta_17643.json", cliente=c)
    assert importar_acta.importar(17644, fx / "acta_17644.html", cliente=c)
    assert c.sesion.llamadas == 0 and c.acta_en_cache(17643)
    assert not importar_acta.importar(1, fx / "acta_17643.json", esperado=(0, 0), cliente=c)
    assert not c.acta_en_cache(1)
