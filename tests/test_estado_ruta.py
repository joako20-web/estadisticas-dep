import importlib

from datosdep import estado


def test_estado_por_defecto_en_raiz(monkeypatch):
    monkeypatch.delenv("RUGBYIG_ESTADO", raising=False)
    e = importlib.reload(estado)
    assert e.ESTADO == e.RAIZ / "estado"


def test_estado_separado_para_laboratorio(monkeypatch, tmp_path):
    monkeypatch.setenv("RUGBYIG_ESTADO", "estado_lab")
    e = importlib.reload(estado)
    assert e.ESTADO == e.RAIZ / "estado_lab"
    monkeypatch.delenv("RUGBYIG_ESTADO")
    importlib.reload(estado)
