import importlib

from datosdep import estado


def test_estado_por_defecto_en_raiz(monkeypatch):
    monkeypatch.delenv("ESTADO_DIR", raising=False)
    e = importlib.reload(estado)
    assert e.ESTADO == e.RAIZ / "estado"


def test_estado_separado_para_laboratorio(monkeypatch, tmp_path):
    monkeypatch.setenv("ESTADO_DIR", "estado_lab")
    e = importlib.reload(estado)
    assert e.ESTADO == e.RAIZ / "estado_lab"
    monkeypatch.delenv("ESTADO_DIR")
    importlib.reload(estado)
