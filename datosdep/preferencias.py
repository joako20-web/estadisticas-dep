"""Preferencias de cada usuario del bot: qué avisos automáticos recibe, de qué
ligas, y sus ligas favoritas en el menú. Se guardan en estado/bot.json."""
from __future__ import annotations

from datosdep.pipeline import cargar_config

TIPOS = {
    "semana": "📊 Carruseles del lunes",
    "directo": "🏁 Resultados al momento (finde)",
    "agenda": "📅 Agenda del jueves",
    "arbitros": "🧑‍⚖️ Quién pita (jueves)",
}
FAVORITAS_DEFECTO = ["dh_masc", "dh_fem", "dh_elite"]


def ligas_defecto() -> list[str]:
    """Las que llegan si el usuario no ha elegido: las que entran en el envío semanal."""
    return [c for c, v in cargar_config()["competiciones"].items() if v.get("semanal", True) is not False]


def de(b: dict, chat_id) -> dict:
    p = b.get("prefs", {}).get(str(chat_id), {})
    comps = cargar_config()["competiciones"]
    return {
        "avisos": {t: p.get("avisos", {}).get(t, True) for t in TIPOS},
        "ligas": [c for c in (p.get("ligas") if p.get("ligas") is not None else ligas_defecto()) if c in comps],
        "favoritas": [c for c in p.get("favoritas", FAVORITAS_DEFECTO) if c in comps],
    }


def guardar(b: dict, chat_id, p: dict) -> None:
    b.setdefault("prefs", {})[str(chat_id)] = p


def alternar_aviso(b: dict, chat_id, tipo: str) -> None:
    p = de(b, chat_id)
    p["avisos"][tipo] = not p["avisos"][tipo]
    guardar(b, chat_id, p)


def alternar(b: dict, chat_id, lista: str, comp: str) -> None:
    p = de(b, chat_id)
    if comp in p[lista]:
        p[lista].remove(comp)
    else:
        p[lista].append(comp)
    guardar(b, chat_id, p)


def usuarios(b: dict) -> list[int]:
    return ([b["chat_id"]] if b.get("chat_id") else []) + [int(i) for i in b.get("invitados", {})]


def quiere(b: dict, chat_id, tipo: str | None, comp: str | None = None) -> bool:
    if tipo is None:
        return True
    p = de(b, chat_id)
    return p["avisos"].get(tipo, True) and (comp is None or comp in p["ligas"])


def ligas_de_todos(b: dict, tipo: str) -> set[str]:
    """Ligas que algún usuario quiere recibir con ese aviso (para no generar de más)."""
    return {c for u in usuarios(b) if de(b, u)["avisos"].get(tipo, True) for c in de(b, u)["ligas"]}
