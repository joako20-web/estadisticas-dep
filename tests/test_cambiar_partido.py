import json

from datosdep import carteles, flujo
from datosdep.pipeline import ruta_jornada


def test_menu_cambiar_partido(monkeypatch):
    datos = json.loads(ruta_jornada("dh_masc", "unico", 2).read_text(encoding="utf-8"))
    monkeypatch.setattr(carteles, "_datos", lambda comp, grupo, jornada: datos)
    pend = [p for p in datos["proxima_jornada"]["partidos"] if p["puntos_local"] is None]
    actual = pend[1]["id"]
    texto, filas = flujo._menu_cambiar_partido("dh_masc/unico", "z", str(actual))
    partidos = filas[:-1]
    assert f"jornada {datos['proxima_jornada']['numero']}" in texto
    assert len(partidos) == len(pend)
    assert [f[0][1] for f in partidos] == [f"pe|dh_masc/unico|z|{p['id']}" for p in pend]
    marcados = [f[0][0] for f in partidos if f[0][0].startswith("⭐")]
    assert len(marcados) == 1 and partidos[1][0][0] == marcados[0]
    assert all(len(f[0][1].encode()) <= 64 for f in partidos)  # límite de Telegram


def test_menu_cambiar_partido_sin_pendientes(monkeypatch):
    monkeypatch.setattr(carteles, "_datos", lambda comp, grupo, jornada: {"proxima_jornada": None})
    texto, filas = flujo._menu_cambiar_partido("dh_masc/unico", "w", "")
    assert "no quedan partidos" in texto and filas == [[("🏠 Inicio", "m1")]]
