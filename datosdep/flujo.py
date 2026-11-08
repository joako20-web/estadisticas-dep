"""Orquestación del bot de Telegram.

- `semana`: el lunes manda el carrusel de la última jornada de cada liga (el
  martes reintenta los que tenían actas incompletas).
- `procesar`: atiende botones, cambios del XV, fotos de portada y pedidos
  ("xv de dhb", "clasificación élite"...).
- `bucle`: escucha Telegram durante N minutos (lo lanza GitHub Actions).
"""
from __future__ import annotations

import html
import json
import re
import tempfile
import threading
import time
import traceback
from pathlib import Path

from datosdep import agenda, arbitros, caption, preferencias, precalentar, destacado, directo, especiales, estado, evolucion, fichas, historico, torneo
from datosdep.core.editar import cambiar_xv
from datosdep.pedidos import interpretar
from datosdep.pipeline import RAIZ, cargar_config, es_descanso, jornadas_jugadas, preparar_jornada
from datosdep.render import nombres
from datosdep.render.render import CLAVES, TEMAS, hoja_muestras, renderizar_jornada, tema_actual
from datosdep.scraper.origen_a import AccesoRestringido
from datosdep.telegram import Telegram

# Claves de slide abreviadas para caber en los 64 bytes de un botón.
ABREV = {"portada": "p", "resultados": "r", "anotadores": "a", "xv": "x",
         "clasificacion": "c", "previa": "v", "temporada": "t", "datos": "d",
         "grupos": "g", "cuadro": "k",
         "ensayadores": "y", "ensayadores_t": "Y", "pateadores": "f", "pateadores_t": "F",
         "disciplina": "j", "banquillo": "b", "equipos": "q",
         "encuesta_mvp": "u", "encuesta_partido": "w", "evolucion": "e",
         "xv_temporada": "X", "mvp_temporada": "M",
         "partido_jornada": "z", "palmares": "P", "hace_un_ano": "H",
         "mvp_jornada": "m", "matchday": "n"}
# Imágenes de nivel competición (no dependen de un grupo ni de una jornada).
DE_COMPETICION = {"grupos", "cuadro"}
DESABREV = {v: k for k, v in ABREV.items()}

AYUDA = (
    "<b>Cada lunes</b> te mando el carrusel de cada liga listo para subir, el texto del post "
    "para copiar y las tarjetas de <b>💡 el dato de la jornada</b>.\n"
    "<b>El fin de semana</b>, en cuanto acaba un partido de DH, Élite o Iberdrola, te llega "
    "su <b>🏁 resultado final</b> en formato historia.\n\n"
    "Debajo de cada envío:\n"
    "📱 <b>Historias</b>: lo mismo en vertical 9:16.\n"
    "📦 <b>Original</b>: como archivo, sin la compresión de Telegram.\n"
    "✏️ <b>Cambiar XV</b>: después escribe el dorsal y el nombre, p. ej. <code>9 Araña</code>.\n"
    "📷 <b>Foto portada</b>: después mándame la foto.\n\n"
    "📋 <b>Pedir</b> (botón de abajo o /pedir): eliges liga, qué quieres y jornada.\n"
    "🎬 <b>Vídeos para vídeos</b> (dentro de cada liga): resultados, clasificación, XV... animados.\n"
    "/semana manda ya los carruseles de la semana.\n"
    "/estilo cambia el estilo visual (5 opciones, con muestras)."
)


NOVEDADES = (
    "🆕 <b>Novedades</b>\n"
    "· ⚙️ <b>Avisos</b>: elige qué te llega (carruseles, resultados al momento, agenda, árbitros) y de qué ligas.\n"
    "· ⭐ <b>Favoritas</b>: tus ligas a un toque, arriba del menú.\n"
    "· Menús más ordenados, con 🏠 Inicio en cada pantalla."
)


def _rel(p: Path) -> str:
    return str(p.relative_to(RAIZ))


def _titulo(post: dict) -> str:
    cfg = cargar_config()["competiciones"][post["competicion"]]
    grupo = "" if post["grupo"] == "unico" else f" · Grupo {post['grupo']}"
    return f"{cfg['nombre']}{grupo} · Jornada {post['jornada']}"


def _cod(claves: list[str] | None) -> str:
    return "*" if not claves else "".join(ABREV[c] for c in claves)


def _decod(cod: str) -> list[str] | None:
    return None if cod in ("", "*") else [DESABREV[c] for c in cod if c in DESABREV]


def preparar(comp: str, grupo: str, jornada: int | None = None) -> tuple[str, dict]:
    """Descarga datos frescos de la jornada y la registra en el estado."""
    ruta = preparar_jornada(comp, grupo, jornada)
    datos = json.loads(ruta.read_text(encoding="utf-8"))
    pid = estado.id_post(datos["temporada"], comp, grupo, datos["jornada"])
    posts = estado.posts()
    post = posts.get(pid, {})
    post.update(competicion=comp, grupo=grupo, jornada=datos["jornada"], json=_rel(ruta),
                actas_pendientes=datos["actas_pendientes"],
                jugados=sum(p["puntos_local"] is not None for p in datos["partidos"]))
    posts[pid] = post
    estado.guardar_posts(posts)
    return pid, post


def enviar(tg: Telegram, chat_id, pid: str, post: dict, claves: list[str] | None = None,
           nota: str = "", formato: str = "post", original: bool = False) -> None:
    """Genera las imágenes (el carrusel o solo `claves`) y las manda con sus botones.

    formato: "post" (4:5) o "historia" (9:16). original: como archivo, sin compresión.
    """
    datos = json.loads((RAIZ / post["json"]).read_text(encoding="utf-8"))
    with tempfile.TemporaryDirectory() as tmp:
        imagenes = renderizar_jornada(RAIZ / post["json"], Path(tmp), claves, formato)
        if not imagenes:
            from datosdep.scraper import origen_a
            detalle = origen_a.compartido().detalle_bloqueo
            motivo = (f"\n⚠️ Faltan {len(datos['actas_pendientes'])} acta(s) de el origen (el origen A las está "
                      f"bloqueando, código {detalle}): sin ellas no hay "
                      "anotadores, XV ideal ni MVP de esta jornada."
                      if datos.get("actas_pendientes") else "")
            tg.mensaje(chat_id, f"No hay nada que enseñar de <b>{_titulo(post)}</b> todavía.{motivo}")
            return
        tg.album(chat_id, imagenes, como_archivo=original)
    if original:
        return  # los originales van sin botones ni textos: ya se mandó la versión normal

    cod, fmt = _cod(claves), formato[0]
    lineas = [f"<b>{_titulo(post)}</b>" + (" · 📱 historias" if formato == "historia" else "")]
    if nota:
        lineas.append(nota)
    if datos["actas_pendientes"] and formato == "post":
        lineas.append(
            f"⚠️ {len(datos['actas_pendientes'])} acta(s) sin completar en la web de el origen: "
            "sus estadísticas aún no cuentan."
        )
    completo = claves is None
    filas = []
    if formato == "post":
        edicion = []
        if datos.get("xv_ideal") and (completo or "xv" in claves):
            edicion.append(("✏️ Cambiar XV", f"xv|{pid}|{cod}"))
        if completo or "portada" in claves:
            edicion.append(("📷 Foto portada", f"foto|{pid}|{cod}"))
        if edicion:
            filas.append(edicion)
        filas.append([("📱 Historias", f"h|{pid}|{cod}"), ("📦 Original", f"o|{pid}|{cod}|p")])
    else:
        filas.append([("📦 Original", f"o|{pid}|{cod}|h")])
    tg.mensaje(chat_id, "\n".join(lineas), filas)
    if completo and formato == "post":
        tg.mensaje(chat_id, "📋 Texto para el post (mantén pulsado para copiar):")
        tg.mensaje(chat_id, html.escape(caption.texto_post(datos)))


def _novedad_competicion(comp: str) -> str | None:
    """Clave que cambia cuando hay algo nuevo a nivel competición (jornada de
    grupos o eliminatoria jugada). None si no hay nada jugado."""
    dc = torneo.datos_competicion(comp)
    j = torneo.ultima_jornada(dc)
    elim = sum(p["puntos_local"] is not None for p in dc["eliminatorias"])
    if not j and not elim:
        return None
    return f"{cargar_config()['temporada'].replace('/', '-')}_{comp}_comp_j{j or 0}_e{elim}"


def _semana_competicion(tg: Telegram, chat_id, comp: str, claves: list[str], nota: str) -> str | None:
    try:
        clave = _novedad_competicion(comp)
    except Exception:
        tg.mensaje(chat_id, f"❗ Error preparando {comp}:\n<code>{html.escape(traceback.format_exc()[-700:])}</code>")
        return None
    posts = estado.posts()
    if not clave or clave in posts:
        return None
    if enviar_competicion(tg, chat_id, comp, claves, nota=nota):
        posts[clave] = {"competicion": comp, "enviado": estado.ahora().isoformat()}
        estado.guardar_posts(posts)
        return clave
    return None


def semana(tg: Telegram, chat_id, reintento: bool = False, ligas: set[str] | list[str] | None = None) -> list[str]:
    """Carruseles de la última jornada. `ligas`: cuáles (por defecto las de envío semanal)."""
    hechos = []
    ligas = set(ligas) if ligas is not None else set(preferencias.ligas_defecto())
    general = tg
    for comp, cfg in cargar_config()["competiciones"].items():
        if comp not in ligas:
            continue
        tg = general.para("semana", comp) if hasattr(general, "para") else general
        if cfg.get("torneo"):
            if not reintento and (h := _semana_competicion(
                    tg, chat_id, comp, ["resultados", "grupos", "cuadro"], "Resumen de la semana")):
                hechos.append(h)
            continue
        enviados_antes = len(hechos)
        for grupo in cfg["grupos"]:
            try:
                pid, post = preparar(comp, grupo)
            except RuntimeError:
                continue  # liga sin jornadas jugadas todavía
            except Exception:
                tg.mensaje(chat_id, f"❗ Error preparando {comp}/{grupo}:\n<code>{html.escape(traceback.format_exc()[-700:])}</code>")
                continue
            if post.get("enviado"):
                # Ya mandada: solo se reenvía en el reintento si se completaron actas.
                if not (reintento and post.get("pendientes_al_enviar") and not post["actas_pendientes"]):
                    continue
                nota = "🔄 Versión actualizada: ya están todas las actas."
            else:
                nota = ""
            enviar(tg, chat_id, pid, post, None, nota)
            if json.loads((RAIZ / post["json"]).read_text(encoding="utf-8")).get("datos_jornada"):
                enviar(tg, chat_id, pid, post, ["datos"], "💡 El dato de la jornada: para post suelto o historias.")
            posts = estado.posts()
            posts[pid]["enviado"] = estado.ahora().isoformat()
            posts[pid]["pendientes_al_enviar"] = bool(post["actas_pendientes"])
            estado.guardar_posts(posts)
            hechos.append(pid)
        if reintento or len(hechos) == enviados_antes:
            continue
        extra = (["grupos"] if len(cfg["grupos"]) > 1 else []) + (["cuadro"] if cfg.get("playoff") else [])
        if extra:
            # El cuadro "si acabara hoy" solo va en los pedidos; aquí solo el real
            dc = torneo.datos_competicion(comp)
            if "cuadro" in extra and not dc["eliminatorias"]:
                extra.remove("cuadro")
            if extra:
                enviar_competicion(tg, chat_id, comp, extra, nota="Visión de toda la competición")
    return hechos


# ---------- Menús con botones: liga -> qué -> jornada ----------

TECLADO_FIJO = [["📋 Pedir", "⭐ Favoritas"], ["🎨 Estilo", "⚙️ Avisos", "❓ Ayuda"]]
VERSION_TECLADO = 4  # súbelo al cambiar el teclado fijo para que se reenvíe
COMANDOS = [("pedir", "Pedir resultados, XV, clasificación…"),
            ("avisos", "Qué te llega automáticamente y de qué ligas"),
            ("favoritas", "Tus ligas favoritas"),
            ("agenda", "Agenda del finde (nacionales)"),
            ("equipo", "Ficha de un equipo: /equipo vrac"),
            ("jugador", "Ficha de un jugador: /jugador mansilla"),
            ("cara", "Cara a cara: /cara vrac vs salvador"),
            ("arbitros", "Un equipo con cada árbitro: /arbitros vrac"),
            ("usuarios", "Quién tiene acceso al bot (solo administrador)"),
            ("estilo", "Cambiar el estilo visual"),
            ("semana", "Mandar ya los carruseles de esta semana"),
            ("ayuda", "Cómo funciona")]
QUE = [("🧾 Carrusel completo", "*"), ("📊 Resultados", "r"), ("📅 Próxima jornada", "v"),
       ("🔢 Clasificación", "c"), ("🗂 Todos los grupos", "g"), ("🏆 Cuadro / play-off", "k"),
       ("⭐ XV ideal", "x"), ("🎯 Anotadores", "a"), ("📈 Anotadores temporada", "t"),
       ("💡 El dato de la jornada", "d"), ("🖼 Portada", "p"),
       ("🏉 Ensayadores (jornada)", "y"), ("🏉 Ensayadores (temporada)", "Y"),
       ("🦶 Puntos al pie (jornada)", "f"), ("🦶 Pateadores (temporada)", "F"),
       ("🟨 Tarjetas", "j"), ("🔄 Desde el banquillo", "b"), ("📊 La liga en números", "q"),
       ("🗳 Vota el MVP", "u"), ("❓ ¿Quién gana?", "w"), ("📉 Así va la liga", "e"),
       ("⭐ XV de la temporada", "X"), ("🏅 MVP de la temporada", "M"),
       ("⚔️ Partido de la jornada", "z"), ("🏆 Palmarés", "P"), ("⏪ Hace un año", "H"),
       ("🏅 Tarjeta MVP", "m"), ("🎟 Carteles de partido", "n")]
# Submenú "Más estadísticas"
FILAS_STATS = [["X", "M"], ["e", "q"], ["t", "d"], ["y", "Y"], ["f", "F"], ["j", "b"], ["P", "H"], ["p"]]
# Imágenes de temporada: no se elige jornada
DE_TEMPORADA = {"t", "Y", "F", "j", "b", "q", "v", "g", "k", "w", "e", "X", "M", "z", "P", "H", "n"}
# Imágenes especiales (módulo especiales/evolucion): clave -> (función, admite formato post/historia)
ESPECIALES = {"encuesta_mvp", "encuesta_partido", "evolucion", "xv_temporada", "mvp_temporada",
              "partido_jornada", "palmares", "hace_un_ano", "mvp_jornada", "matchday"}
# Estadísticas de árbitros (designación y actas de el origen A desde 2023/24)
ARBITROS = {"dh_masc", "dh_fem"}
# Histórico: solo competiciones de el origen A con temporadas anteriores
HISTORICO = {"dh_masc", "dh_fem", "dh_elite", "copa"}
# Filas del menú "¿qué quieres?" (agrupadas por tema)
FILAS_QUE = [["*"], ["r", "c"], ["v", "z"], ["x", "a"], ["m", "n"], ["u", "w"], ["g", "k"], ["+"]]
CATEGORIAS = {"nacional": "🇪🇸 Nacionales", "copa": "🏆 Copa del Rey", "regional": "🗺 Regionales"}


def _filas(botones: list[tuple[str, str]], ancho: int) -> list[list[tuple[str, str]]]:
    return [botones[i : i + ancho] for i in range(0, len(botones), ancho)]


def _comps(categoria: str | None = None, region: str | None = None) -> dict[str, dict]:
    return {k: v for k, v in cargar_config()["competiciones"].items()
            if (categoria is None or v.get("categoria", "nacional") == categoria)
            and (region is None or v.get("region") == region)}


def _regiones() -> list[str]:
    return sorted({v["region"] for v in _comps("regional").values() if v.get("region")})


def _nombre_liga(liga: str) -> str:
    comp, grupo = liga.split("/")
    cfg = cargar_config()["competiciones"][comp]
    if grupo == "*":
        return f"{cfg['nombre']} (todos los grupos)"
    return cfg["nombre"] + ("" if grupo == "unico" else f" · Grupo {grupo}")


def _boton_liga(comp: str, cfg: dict) -> tuple[str, str]:
    if len(cfg["grupos"]) > 1 and not cfg.get("torneo"):
        return (f"{cfg['nombre']} ▸", f"mg|{comp}")
    return (cfg["nombre"], f"m2|{comp}/{'*' if cfg.get('torneo') else next(iter(cfg['grupos']))}")


def _atras_de(comp: str) -> str:
    cfg = cargar_config()["competiciones"][comp]
    if cfg.get("categoria") == "regional" and len(_regiones()) > 1:
        return f"mr|{_regiones().index(cfg['region'])}"
    return f"mc|{cfg.get('categoria', 'nacional')}"


def _favoritas(chat_id) -> list[tuple[str, str]]:
    comps = cargar_config()["competiciones"]
    favs = preferencias.de(estado.bot(), chat_id)["favoritas"] if chat_id else preferencias.FAVORITAS_DEFECTO
    return [(f"⭐ {comps[c]['corto']}", _boton_liga(c, comps[c])[1]) for c in favs if c in comps]


def _menu_inicio(chat_id=None) -> tuple[str, list]:
    filas = _filas(_favoritas(chat_id), 3)
    botones = []
    for cat, etiqueta in CATEGORIAS.items():
        comps = _comps(cat)
        if not comps:
            continue
        if cat == "copa" and len(comps) == 1:  # una sola copa: directo a ella
            botones.append((etiqueta, _boton_liga(*next(iter(comps.items())))[1]))
        else:
            botones.append((etiqueta, f"mc|{cat}"))
    filas += _filas(botones, 3)
    filas.append([("📅 Agenda del finde", "ma"), ("🔎 Buscar", "mb")])
    return "📋 <b>¿Qué quieres?</b>", filas


def _menu_agenda() -> tuple[str, list]:
    filas = [[("🇪🇸 Nacionales", "ag|n|h|0"), ("🏆 Copa", "ag|c|h|0")],
             [("🗺 Todas las regionales", "ag|r|h|0"), ("Todo", "ag|*|h|0")]]
    filas += _filas([(r, f"ag|R{i}|h|0") for i, r in enumerate(_regiones())], 3)
    return "📅 <b>Agenda del finde</b>\n¿De qué?", filas + [[("⬅️ Volver", "m1")]]


def _menu_categoria(cat: str) -> tuple[str, list]:
    if cat == "regional" and len(_regiones()) > 1:
        botones = [(r, f"mr|{i}") for i, r in enumerate(_regiones())]
        return "🗺 <b>Regionales</b>\n¿Qué región?", _filas(botones, 2) + [[("⬅️ Volver", "m1")]]
    botones = [_boton_liga(k, v) for k, v in _comps(cat).items()]
    titulo = CATEGORIAS[cat] + (f" · {_regiones()[0]}" if cat == "regional" and _regiones() else "")
    return f"<b>{titulo}</b>\n¿Qué liga?", _filas(botones, 1) + [[("⬅️ Volver", "m1")]]


def _menu_region(i: int) -> tuple[str, list]:
    region = _regiones()[i]
    botones = [_boton_liga(k, v) for k, v in _comps("regional", region).items()]
    return f"🗺 <b>{region}</b>\n¿Qué liga?", _filas(botones, 1) + [[("⬅️ Volver", "mc|regional")]]


def _menu_grupos(comp: str) -> tuple[str, list]:
    cfg = cargar_config()["competiciones"][comp]
    botones = [(f"Grupo {g}", f"m2|{comp}/{g}") for g in cfg["grupos"]]
    filas = _filas(botones, 4) + [[("Todos los grupos", f"m2|{comp}/*")], [("⬅️ Volver", _atras_de(comp)), ("🏠 Inicio", "m1")]]
    return f"<b>{cfg['nombre']}</b>\n¿Qué grupo?", filas


def _menu_que(liga: str) -> tuple[str, list]:
    comp, grupo = liga.split("/")
    cfg = cargar_config()["competiciones"][comp]
    ocultar = set()
    if len(cfg["grupos"]) < 2:
        ocultar.add("g")
    if not torneo.tiene_cuadro(comp):
        ocultar.add("k")
    if not cfg.get("xv_ideal"):
        ocultar.add("x")
    etiqueta = {c: t for t, c in QUE}
    filas = []
    for fila in FILAS_QUE:
        if fila == ["+"]:
            filas.append([("📈 Más estadísticas ▸", f"ms|{liga}")])
            continue
        botones = [(etiqueta[c], f"m3|{liga}|{c}") for c in fila if c not in ocultar]
        if botones:
            filas.append(botones)
    if grupo != "*" and not cfg.get("torneo"):
        filas.append([("🎬 Vídeos para vídeos ▸", f"vd|{liga}")])
    if cfg.get("torneo"):  # Copa: acceso a cada grupo
        filas.append([(f"Grupo {g}", f"m2|{comp}/{g}") for g in cfg["grupos"]][:6])
    atras = f"mg|{comp}" if len(cfg["grupos"]) > 1 and not cfg.get("torneo") else _atras_de(comp)
    if cfg.get("torneo") and grupo != "*":
        atras = f"m2|{comp}/*"
    filas.append([("⬅️ Volver", atras), ("🏠 Inicio", "m1")])
    return f"<b>{_nombre_liga(liga)}</b>\n¿Qué quieres?", filas


def _menu_stats(liga: str) -> tuple[str, list]:
    etiqueta = {c: t for t, c in QUE}
    ocultar = set() if liga.split("/")[0] in HISTORICO else {"P", "H"}
    filas = [[(etiqueta[c], f"m3|{liga}|{c}") for c in fila if c not in ocultar] for fila in FILAS_STATS]
    filas = [f for f in filas if f]
    if liga.split("/")[0] in ARBITROS:
        filas.insert(0, [("🟥 Árbitros ▸", f"mar|{liga.split('/')[0]}")])
    return f"<b>{_nombre_liga(liga)}</b> › 📈 Más estadísticas", filas + [[("⬅️ Volver", f"m2|{liga}"), ("🏠 Inicio", "m1")]]


def _menu_arbitros(comp: str) -> tuple[str, list]:
    nombre = cargar_config()["competiciones"][comp]["nombre"]
    filas = [[("🟨 Los más tarjeteros", f"ar|{comp}|t|p|0")],
             [("🤔 Datos curiosos", f"ar|{comp}|c|p|0")],
             [("🧑‍⚖️ Quién pita la jornada", f"ar|{comp}|d|p|0")],
             [("⬅️ Volver", f"ms|{comp}/unico")]]
    return (f"🟥 <b>Árbitros · {nombre}</b>\nDatos desde 2023/24. Para un equipo concreto escribe "
            f"<code>/arbitros vrac</code>."), filas


def enviar_arbitros(tg: Telegram, chat_id, comp: str, tipo: str, formato: str = "post",
                    original: bool = False, equipo: str = "") -> bool:
    funciones = {"t": arbitros.renderizar_tarjeteros, "c": arbitros.renderizar_curiosidades,
                 "d": arbitros.renderizar_designaciones}
    if not original:
        tg.mensaje(chat_id, "⏳ Preparando… (la primera vez puede tardar un par de minutos: repasa tres temporadas)")
    with tempfile.TemporaryDirectory() as tmp:
        if tipo == "e":
            imgs = arbitros.renderizar_equipo(comp, equipo, Path(tmp), formato)
        else:
            imgs = funciones[tipo](comp, Path(tmp), formato)
        if not imgs:
            tg.mensaje(chat_id, "No hay muestra suficiente (o aún no hay designaciones publicadas).")
            return False
        base = f"ar|{comp}|{tipo}" if tipo != "e" else f"ae|{comp}|{equipo[:24]}"
        _mandar(tg, chat_id, imgs, base, formato, original, "🟥 <b>Árbitros</b>")
    return True


def _menu_jornada(liga: str, cod: str) -> tuple[str, list] | None:
    comp, grupo = liga.split("/")
    grupo_ref = next(iter(cargar_config()["competiciones"][comp]["grupos"])) if grupo == "*" else grupo
    if cod in DE_TEMPORADA:
        return None  # siempre lo último
    jugadas = jornadas_jugadas(comp, grupo_ref)
    if len(jugadas) <= 1:
        return None  # nada que elegir: la última
    ultimas = jugadas[-8:]
    botones = [(f"Última (J{ultimas[-1]})", f"m4|{liga}|{cod}|0")]
    botones += [(f"J{j}", f"m4|{liga}|{cod}|{j}") for j in reversed(ultimas[:-1])]
    return f"<b>{_nombre_liga(liga)}</b>\n¿Qué jornada?", _filas(botones, 4) + [[("⬅️ Volver", f"m2|{liga}"), ("🏠 Inicio", "m1")]]


def _menu(tg: Telegram, chat_id, cq: dict, partes: list[str]) -> None:
    paso, mid = partes[0], cq["message"]["message_id"]
    if paso == "m1":
        tg.editar(chat_id, mid, *_menu_inicio(chat_id))
    elif paso == "ma":
        tg.editar(chat_id, mid, *_menu_agenda())
    elif paso == "mb":
        tg.editar(chat_id, mid, "🔎 <b>Buscar</b>\nEscribe:\n· <code>/equipo vrac</code>\n· <code>/jugador mansilla</code>\n"
                  "· <code>/cara vrac vs salvador</code> (cara a cara histórico)", [[("⬅️ Volver", "m1")]])
    elif paso == "mc":
        tg.editar(chat_id, mid, *_menu_categoria(partes[1]))
    elif paso == "mr":
        tg.editar(chat_id, mid, *_menu_region(int(partes[1])))
    elif paso == "mg":
        tg.editar(chat_id, mid, *_menu_grupos(partes[1]))
    elif paso == "m2":
        tg.editar(chat_id, mid, *_menu_que(partes[1]))
    elif paso == "ms":
        tg.editar(chat_id, mid, *_menu_stats(partes[1]))
    elif paso == "mar":
        tg.editar(chat_id, mid, *_menu_arbitros(partes[1]))
    elif paso in ("m3", "m4"):
        liga, cod = partes[1], partes[2]
        if paso == "m3" and (menu := _menu_jornada(liga, cod)):
            tg.editar(chat_id, mid, *menu)
            return
        jornada = int(partes[3]) if paso == "m4" and partes[3] != "0" else None
        que = dict((c, t) for t, c in QUE)[cod]
        tg.editar(chat_id, mid, f"⏳ {que} · {_nombre_liga(liga)}" + (f" · J{jornada}" if jornada else ""))
        comp, grupo = liga.split("/")
        grupos = list(cargar_config()["competiciones"][comp]["grupos"]) if grupo == "*" else [grupo]
        _servir(tg, chat_id, [(comp, g) for g in grupos], _decod(cod), jornada)
        tg.mensaje(chat_id, "¿Algo más?", [[("🔁 Otra cosa de esta liga", f"m0|{liga}"), ("📋 Otra competición", "m0")]])


def enviar_competicion(tg: Telegram, chat_id, comp: str, claves: list[str],
                       formato: str = "post", original: bool = False, nota: str = "") -> bool:
    """Imágenes de toda la competición (todos los grupos, cuadro, resultados de todos los grupos)."""
    with tempfile.TemporaryDirectory() as tmp:
        imagenes = torneo.renderizar(comp, claves, Path(tmp), formato)
        if not imagenes:
            return False
        tg.album(chat_id, imagenes, como_archivo=original)
    if original:
        return True
    cod = _cod(claves)
    nombre = cargar_config()["competiciones"][comp]["nombre"]
    botones = [[("📦 Original", f"to|{comp}|{cod}|{formato[0]}")]]
    if formato == "post":
        botones[0].insert(0, ("📱 Historias", f"th|{comp}|{cod}"))
    tg.mensaje(chat_id, f"<b>{nombre}</b>" + (f"\n{nota}" if nota else ""), botones)
    return True


# Imágenes de un solo partido que el bot elige solo; debajo sale «🔄 Cambiar partido».
CON_PARTIDO = {"partido_jornada", "encuesta_partido"}


def _render_especial(clave: str, comp: str, grupo: str, destino: Path, formato: str, jornada: int | None,
                     id_partido: int | None = None, elegido: dict | None = None) -> list[Path]:
    """`id_partido` fuerza el partido en las imágenes de CON_PARTIDO; en `elegido["id"]`
    se devuelve el partido que ha salido (el elegido por el bot o el forzado)."""
    elegido = elegido if elegido is not None else {}
    if clave == "encuesta_mvp":
        return especiales.renderizar_vota_mvp(comp, grupo, destino, jornada=jornada)
    if clave == "encuesta_partido":
        if id_partido is None:
            from datosdep.carteles import _datos

            p = especiales.partido_destacado(_datos(comp, grupo, None))
            id_partido = p["id"] if p else None
        elegido["id"] = id_partido
        return especiales.renderizar_quien_gana(comp, grupo, destino, id_partido=id_partido)
    if clave == "evolucion":
        return evolucion.renderizar_evolucion(comp, grupo, destino, formato=formato)
    if clave == "xv_temporada":
        return especiales.renderizar_xv_temporada(comp, grupo, destino, formato=formato)
    if clave == "mvp_temporada":
        return especiales.renderizar_mvp_temporada(comp, grupo, destino, formato=formato)
    if clave == "partido_jornada":
        datos, rutas = destacado.partido_jornada(comp, grupo, id_partido=id_partido, formato=formato, destino=destino)
        elegido["id"] = datos["partido"]["id"]
        return rutas
    if clave == "palmares":
        return historico.palmares(comp, formato, destino)
    if clave == "mvp_jornada":
        from datosdep.carteles_mvp import renderizar_mvp
        from datosdep.videos.base import datos_jornada

        jornada = jornada or datos_jornada(comp, grupo, None)["jornada"]
        elegido["jornada"] = jornada
        return renderizar_mvp(comp, grupo, destino, jornada=jornada, formato=formato)
    if clave == "matchday":  # un cartel por partido de la próxima jornada
        from datosdep.carteles import _datos, renderizar_matchday

        siguiente = _datos(comp, grupo, None).get("proxima_jornada") or {}
        ids = [p["id"] for p in siguiente.get("partidos", []) if p.get("puntos_local") is None and not es_descanso(p)]
        return [renderizar_matchday(comp, grupo, i, destino / str(i), formato=formato) for i in ids]
    if clave == "hace_un_ano":
        jugadas = jornadas_jugadas(comp, grupo)
        return historico.hace_un_ano(comp, jugadas[-1], formato, destino) if jugadas else []
    return []


def enviar_especial(tg: Telegram, chat_id, clave: str, comp: str, grupo: str, jornada: int | None = None,
                    formato: str = "post", original: bool = False, id_partido: int | None = None) -> bool:
    elegido: dict = {}
    with tempfile.TemporaryDirectory() as tmp:
        imagenes = _render_especial(clave, comp, grupo, Path(tmp), formato, jornada, id_partido, elegido)
        if not imagenes:
            return False
        tg.album(chat_id, imagenes, como_archivo=original)
    if original:
        return True
    cod, liga = ABREV[clave], f"{comp}/{grupo}"
    es_historia = clave.startswith("encuesta") or formato == "historia"
    pid = elegido.get("id")
    extra = f"|{pid}" if pid and clave in CON_PARTIDO else ""  # Historias/Original del mismo partido
    botones = [("📦 Original", f"eo|{liga}|{cod}|{'h' if formato == 'historia' else 'p'}{extra}")]
    if not es_historia:
        botones.insert(0, ("📱 Historias", f"eh|{liga}|{cod}|h{extra}"))
    filas = [botones]
    if clave in CON_PARTIDO:
        filas.append([("🔄 Cambiar partido", f"pc|{liga}|{cod}|{pid or ''}")])
    if clave == "mvp_jornada" and elegido.get("jornada"):
        filas.append([("🗳 Ganador de la votación", f"ym|{liga}|{elegido['jornada']}")])
    nota = "\nPega encima la encuesta de la red en el hueco." if clave.startswith("encuesta") else ""
    tg.mensaje(chat_id, f"<b>{_nombre_liga(liga)}</b>{nota}", filas)
    return True


def _servir(tg: Telegram, chat_id, ligas: list[tuple[str, str]], claves: list[str] | None, jornada: int | None) -> None:
    esp = [c for c in (claves or []) if c in ESPECIALES]
    if esp:
        for comp, grupo in ligas:
            for clave in esp:
                try:
                    hecho = enviar_especial(tg, chat_id, clave, comp, grupo, jornada)
                except RuntimeError:
                    hecho = False
                if not hecho:
                    tg.mensaje(chat_id, f"<b>{_nombre_liga(f'{comp}/{grupo}')}</b>: todavía no hay datos suficientes para esto.")
        claves = [c for c in claves if c not in ESPECIALES]
        if not claves:
            return
    de_comp = [c for c in (claves or []) if c in DE_COMPETICION]
    if de_comp:
        for comp in dict.fromkeys(c for c, _ in ligas):
            if not enviar_competicion(tg, chat_id, comp, de_comp):
                tg.mensaje(chat_id, "No hay nada que enseñar todavía (sin grupos o sin play-off).")
        claves = [c for c in claves if c not in DE_COMPETICION]
        if not claves:
            return
    # Torneo (Copa) pedido completo para todos los grupos: un único resumen
    comps = {c for c, _ in ligas}
    if claves is None and len(ligas) > 1 and len(comps) == 1 and \
            cargar_config()["competiciones"][next(iter(comps))].get("torneo"):
        enviar_competicion(tg, chat_id, next(iter(comps)), ["resultados", "grupos", "cuadro"])
        return
    for comp, grupo in ligas:
        try:
            pid, post = preparar(comp, grupo, jornada)
        except RuntimeError:
            nombre = cargar_config()["competiciones"][comp]["nombre"]
            tg.mensaje(chat_id, f"La {nombre} todavía no ha jugado ninguna jornada.")
            continue
        if jornada and not post["jugados"] and claves != ["previa"]:
            tg.mensaje(chat_id, f"<b>{_titulo(post)}</b>: esa jornada aún no se ha jugado.")
            continue
        enviar(tg, chat_id, pid, post, claves)


# ---------- Avisos y favoritas (preferencias de cada usuario) ----------

def _menu_videos(liga: str) -> tuple[str, list]:
    from datosdep.videos import PLANTILLAS

    cfg = cargar_config()["competiciones"][liga.split("/")[0]]
    botones = [(p.nombre, f"vv|{liga}|{p.clave}") for p in PLANTILLAS.values() if p.disponible(cfg)]
    if not cfg.get("torneo"):
        botones.append((PLANTILLAS["final"].nombre + " ▸", f"vp|{liga}"))
    filas = _filas(botones, 2) + [[("⬅️ Volver", f"m2|{liga}"), ("🏠 Inicio", "m1")]]
    return (f"🎬 <b>{_nombre_liga(liga)}</b>\n¿Qué vídeo? Tardan unos 3 minutos y te llegan solos; "
            "mientras puedes seguir pidiendo cosas."), filas


def _datos_votacion(liga: str, jornada: int) -> tuple[Path, dict]:
    from datosdep.pipeline import ruta_jornada

    comp, grupo = liga.split("/")
    ruta = ruta_jornada(comp, grupo, jornada)
    return ruta, json.loads(ruta.read_text(encoding="utf-8"))


def _boton_votacion(tg: Telegram, b: dict, partes: list[str]) -> None:
    """ym: elegir ganador · yw: guardar ganador · yq: pedir porcentajes · yk: rehacer la tarjeta."""
    from datosdep.carteles_mvp import guardar_votacion

    chat_id, accion, liga, jornada = b["chat_id"], partes[0], partes[1], int(partes[2])
    comp, grupo = liga.split("/")
    ruta, datos = _datos_votacion(liga, jornada)
    cands = especiales.candidatos_mvp(datos)
    if accion == "ym":
        actual = (datos.get("mvp_votacion") or {}).get("ganador")
        filas = [[(("✅ " if c["nombre"] == actual else "") + f"{'ABCD'[i]} · {nombres.jugador(c['nombre'])['completo']}"
                   f" ({nombres.equipo_abr(c['equipo'])})", f"yw|{liga}|{jornada}|{i}")] for i, c in enumerate(cands)]
        filas.append([("↩️ El de mejor nota (sin votación)", f"yw|{liga}|{jornada}|x")])
        tg.mensaje(chat_id, f"🗳 <b>{_nombre_liga(liga)}</b> · jornada {jornada}\n"
                   "¿Quién ganó la votación? (mismas letras que en la encuesta «Vota el MVP»)", filas)
    elif accion == "yw":
        if partes[3] == "x":
            guardar_votacion(datos, None)
            ruta.write_text(json.dumps(datos, ensure_ascii=False, indent=2), encoding="utf-8")
            enviar_especial(tg, chat_id, "mvp_jornada", comp, grupo, jornada)
            return
        ganador = cands[int(partes[3])]["nombre"]
        guardar_votacion(datos, ganador)
        ruta.write_text(json.dumps(datos, ensure_ascii=False, indent=2), encoding="utf-8")
        tg.mensaje(chat_id, f"✔️ MVP de la afición: <b>{nombres.jugador(ganador)['completo']}</b>.\n"
                   "¿Pongo también los porcentajes de la votación?",
                   [[("📊 Añadir porcentajes", f"yq|{liga}|{jornada}"), ("✅ Así está bien", f"yk|{liga}|{jornada}")]])
    elif accion == "yq":
        b["esperando"] = {"accion": "mvp_pct", "liga": liga, "jornada": jornada}
        lista = "\n".join(f"{'ABCD'[i]}. {nombres.jugador(c['nombre'])['completo']}" for i, c in enumerate(cands))
        ej = " ".join(str(x) for x in [48, 24, 19, 9][:len(cands)])
        tg.mensaje(chat_id, f"📊 Escribe los porcentajes en este orden:\n\n{html.escape(lista)}\n\n"
                   f"Por ejemplo: <code>{ej}</code>")
    else:  # yk
        enviar_especial(tg, chat_id, "mvp_jornada", comp, grupo, jornada)


def _porcentajes_mvp(tg: Telegram, b: dict, texto: str) -> None:
    from datosdep.carteles_mvp import leer_porcentajes

    esperando = b["esperando"]
    liga, jornada = esperando["liga"], esperando["jornada"]
    ruta, datos = _datos_votacion(liga, jornada)
    cands = especiales.candidatos_mvp(datos)
    try:
        pcts = leer_porcentajes(texto, len(cands))
    except ValueError as e:
        if interpretar(texto):  # parece un pedido: salir del modo votación
            b["esperando"] = None
            _atender_pedido(tg, b["chat_id"], texto)
        else:
            tg.mensaje(b["chat_id"], f"🤔 {html.escape(str(e))}")
        return
    votacion = datos.get("mvp_votacion") or {}
    votacion["votos"] = {c["nombre"]: pct for c, pct in zip(cands, pcts)}
    datos["mvp_votacion"] = votacion
    ruta.write_text(json.dumps(datos, ensure_ascii=False, indent=2), encoding="utf-8")
    b["esperando"] = None
    comp, grupo = liga.split("/")
    enviar_especial(tg, b["chat_id"], "mvp_jornada", comp, grupo, jornada)


def _menu_cambiar_partido(liga: str, cod: str, actual: str) -> tuple[str, list]:
    """Partidos pendientes de la próxima jornada; ⭐ el que sale ahora."""
    from datosdep.carteles import _datos

    comp, grupo = liga.split("/")
    prox = _datos(comp, grupo, None).get("proxima_jornada") or {}
    pendientes = [p for p in prox.get("partidos", []) if p.get("puntos_local") is None and not es_descanso(p)]
    if not pendientes:
        return f"<b>{_nombre_liga(liga)}</b>: no quedan partidos pendientes en la próxima jornada.", [[("🏠 Inicio", "m1")]]
    filas = [[(("⭐ " if str(p["id"]) == actual else "") +
               f"{nombres.equipo_corto(p['local'])} – {nombres.equipo_corto(p['visitante'])}",
               f"pe|{liga}|{cod}|{p['id']}")] for p in pendientes]
    return (f"🔄 <b>{_nombre_liga(liga)}</b> · jornada {prox.get('numero')}\n"
            "¿Qué partido quieres? (⭐ = el que he elegido yo)"), filas + [[("🏠 Inicio", "m1")]]


def _menu_partidos_video(liga: str) -> tuple[str, list]:
    from datosdep.videos.final import id_partidos_jornada

    comp, grupo = liga.split("/")
    partidos = id_partidos_jornada(comp, grupo)
    botones = [[(texto, f"vf|{liga}|{id_}")] for id_, texto in partidos]
    return (f"🏉 <b>{_nombre_liga(liga)}</b>\n¿De qué partido hago el «así fue»?",
            botones + [[("⬅️ Volver", f"vd|{liga}"), ("🏠 Inicio", "m1")]])


def pedir_video(tg: Telegram, chat_id, liga: str, tipo: str = "jornada", **extra) -> None:
    """Vídeo para vídeos. Tarda unos minutos: se hace en segundo plano para que el bot
    siga respondiendo (el hilo no es daemon, así que el proceso espera a que acabe)."""
    from datosdep.videos import PLANTILLAS

    plantilla = PLANTILLAS[tipo]
    tg.mensaje(chat_id, f"⏳ {plantilla.nombre} · {_nombre_liga(liga)}\nEn unos 3 minutos te llega el vídeo.")

    def trabajo():
        from datosdep.videos import reel

        comp, grupo = liga.split("/")
        try:
            with tempfile.TemporaryDirectory() as tmp:
                props: dict = {}
                ruta = reel(comp, grupo, tipo=tipo, salida=Path(tmp) / f"reel_{tipo}_{comp}_{grupo}.mp4",
                            props_usadas=props, **extra)
                filas = [[("🎬 Otro vídeo", f"vd|{liga}"), ("🔁 Otra cosa", f"m0|{liga}")]]
                if props.get("idDestacado"):  # el cara a cara de la previa lo elige el bot: se puede cambiar
                    filas.insert(0, [("🔄 Cambiar partido destacado", f"pc|{liga}|VP|{props['idDestacado']}")])
                tg.video(chat_id, ruta, f"🎬 <b>{plantilla.nombre}</b> · {_nombre_liga(liga)}\n"
                         "Listo para vídeos. Ponle música desde la red: los efectos van flojitos para que se oiga.",
                         filas)
        except Exception as e:
            traceback.print_exc()
            tg.mensaje(chat_id, f"⚠️ No he podido hacer el vídeo: {html.escape(str(e))[:300]}")

    threading.Thread(target=trabajo, name=f"video {tipo} {liga}").start()


def _marca(si: bool) -> str:
    return "✅" if si else "⬜"


def _menu_avisos(chat_id) -> tuple[str, list]:
    p = preferencias.de(estado.bot(), chat_id)
    filas = [[(f"{_marca(p['avisos'][k])} {v}", f"pf|t|{k}")] for k, v in preferencias.TIPOS.items()]
    filas.append([(f"🏆 Ligas que te llegan ({len(p['ligas'])}) ▸", "pf|L|N")])
    filas.append([(f"⭐ Favoritas del menú ({len(p['favoritas'])}) ▸", "pf|F|N")])
    filas.append([("✔️ Hecho", "pf|x")])
    return ("⚙️ <b>Tus avisos automáticos</b>\nToca para activar o desactivar. "
            "Los resultados al momento y los carruseles solo llegan de las ligas que marques."), filas


def _menu_pref_ligas(chat_id, lista: str, vista: str) -> tuple[str, list]:
    """lista: "L" ligas que llegan o "F" favoritas. vista: "N" nacionales, "R" regiones o "r<i>" una región."""
    p = preferencias.de(estado.bot(), chat_id)
    elegidas = p["ligas"] if lista == "L" else p["favoritas"]
    comps = cargar_config()["competiciones"]
    titulo = "🏆 <b>Ligas que te llegan</b>" if lista == "L" else "⭐ <b>Tus favoritas</b>"
    if vista == "R":
        filas = _filas([(r, f"pf|{lista}|r{i}") for i, r in enumerate(_regiones())], 2)
        return f"{titulo} › Regionales", filas + [[("⬅️ Volver", f"pf|{lista}|N")]]
    if vista.startswith("r"):
        region = _regiones()[int(vista[1:])]
        sel = {k: v for k, v in comps.items() if v.get("region") == region}
        atras = f"pf|{lista}|R"
    else:
        sel = {k: v for k, v in comps.items() if v.get("categoria", "nacional") in ("nacional", "copa")}
        atras = "pf|0"
    botones = [(f"{_marca(c in elegidas)} {v['corto']}", f"pf|{lista.lower()}|{c}|{vista}") for c, v in sel.items()]
    filas = _filas(botones, 2)
    if vista == "N":
        filas.append([("🗺 Regionales ▸", f"pf|{lista}|R")])
    filas.append([("⬅️ Volver", atras)])
    return titulo + (f" › {region}" if vista.startswith("r") else ""), filas


def _boton_pref(tg: Telegram, chat_id, cq: dict, partes: list[str]) -> None:
    mid = cq["message"]["message_id"]
    b = estado.bot()
    accion = partes[1]
    if accion == "t":
        preferencias.alternar_aviso(b, chat_id, partes[2])
        estado.guardar_bot(b)
        tg.editar(chat_id, mid, *_menu_avisos(chat_id))
    elif accion in ("L", "F"):
        tg.editar(chat_id, mid, *_menu_pref_ligas(chat_id, accion, partes[2]))
    elif accion in ("l", "f"):
        preferencias.alternar(b, chat_id, "ligas" if accion == "l" else "favoritas", partes[2])
        estado.guardar_bot(b)
        tg.editar(chat_id, mid, *_menu_pref_ligas(chat_id, accion.upper(), partes[3]))
    elif accion == "0":
        tg.editar(chat_id, mid, *_menu_avisos(chat_id))
    elif accion == "x":
        tg.editar(chat_id, mid, "✅ Avisos guardados. Cámbialos cuando quieras con ⚙️ Avisos.")


# ---------- Agenda, fichas y cara a cara ----------

def _mandar(tg: Telegram, chat_id, imagenes: list[Path], base_cb: str, formato: str, original: bool,
            titulo: str = "") -> None:
    """Manda imágenes y, salvo que sean originales, los botones de otro formato / original."""
    tg.album(chat_id, imagenes, como_archivo=original)
    if original:
        return
    f = formato[0]
    botones = [("📦 Original", f"{base_cb}|{f}|1")]
    if formato == "post":
        botones.insert(0, ("📱 Historia", f"{base_cb}|h|0"))
    else:
        botones.insert(0, ("🖼 Post", f"{base_cb}|p|0"))
    tg.mensaje(chat_id, titulo or "👆", [botones])


def _formato(partes: list[str]) -> tuple[str, bool]:
    return ("historia" if partes[-2] == "h" else "post"), partes[-1] == "1"


def enviar_agenda(tg: Telegram, chat_id, filtro: str, formato: str = "historia", original: bool = False) -> None:
    cats, region = None, None
    if filtro == "n":
        cats = ["nacional"]
    elif filtro == "c":
        cats = ["copa"]
    elif filtro == "r":
        cats = ["regional"]
    elif filtro.startswith("R"):
        region = _regiones()[int(filtro[1:])]
    if not original:
        tg.mensaje(chat_id, "⏳ Preparando la agenda (tarda unos segundos)…")
    with tempfile.TemporaryDirectory() as tmp:
        imgs = agenda.agenda(categorias=cats, region=region, formato=formato, destino=Path(tmp))
        if not imgs:
            tg.mensaje(chat_id, "No hay partidos pendientes con fecha para esa selección.")
            return
        _mandar(tg, chat_id, imgs, f"ag|{filtro}", formato, original, "📅 <b>Agenda del finde</b>")
    if not original and formato == "historia":
        datos = agenda.datos_agenda(categorias=cats, region=region)
        tg.mensaje(chat_id, html.escape(agenda.texto_agenda(datos)))


def _ficha(tg: Telegram, chat_id, tipo: str, id_: str, formato: str = "post", original: bool = False) -> None:
    funcion = fichas.ficha_equipo if tipo == "fe" else fichas.ficha_jugador
    with tempfile.TemporaryDirectory() as tmp:
        imgs = funcion(id_, formato, Path(tmp))
        if not imgs:
            tg.mensaje(chat_id, "No hay datos suficientes para esa ficha.")
            return
        _mandar(tg, chat_id, imgs, f"{tipo}|{id_}", formato, original)


def _buscar(tg: Telegram, chat_id, tipo: str, texto: str) -> None:
    if not texto:
        tg.mensaje(chat_id, f"Escribe también el nombre, p. ej. <code>/{'equipo vrac' if tipo == 'fe' else 'jugador mansilla'}</code>")
        return
    tg.mensaje(chat_id, "🔎 Buscando…")
    cands = (fichas.buscar_equipo if tipo == "fe" else fichas.buscar_jugador)(texto)
    if not cands:
        tg.mensaje(chat_id, f"No encuentro a «{html.escape(texto)}».")
    elif len(cands) == 1:
        _ficha(tg, chat_id, tipo, cands[0]["id"])
    else:
        def etiqueta(c):
            if tipo == "fe":
                return f"{c.get('corto') or c['equipo']} · {c.get('liga', '')}"[:60]
            return f"{nombres.titulo(c.get('nombre', ''))} · {nombres.equipo_corto(c.get('equipo', ''))}"[:60]
        tg.mensaje(chat_id, "¿Cuál?", [[(etiqueta(c), f"{tipo}|{c['id']}|p|0")] for c in cands[:8]])


def _cara(tg: Telegram, chat_id, texto: str, formato: str = "post", original: bool = False) -> None:
    lados = re.split(r"\s+(?:vs|contra|-)\s+", texto, flags=re.I)
    if len(lados) != 2:
        tg.mensaje(chat_id, "Escríbelo así: <code>/cara vrac vs salvador</code>")
        return
    elegidos = []
    for lado in lados:
        cands = fichas.buscar_equipo(lado)
        if not cands:
            tg.mensaje(chat_id, f"No encuentro a «{html.escape(lado)}».")
            return
        elegidos.append(cands[0])
    _cara_ids(tg, chat_id, elegidos[0]["id"], elegidos[1]["id"], formato, original)


def _cara_ids(tg: Telegram, chat_id, id_a: str, id_b: str, formato: str = "post", original: bool = False) -> None:
    a, b = fichas.equipo_por_id(id_a), fichas.equipo_por_id(id_b)
    with tempfile.TemporaryDirectory() as tmp:
        imgs = historico.cara_a_cara(a, b, formato, Path(tmp)) if a and b else []
        if not imgs:
            tg.mensaje(chat_id, "No hay partidos entre esos dos equipos en las temporadas guardadas (desde 2023/24, solo nacionales).")
            return
        _mandar(tg, chat_id, imgs, f"cc|{id_a}|{id_b}", formato, original)


# ---------- Estilo visual ----------

def _menu_estilo(tg: Telegram, chat_id) -> None:
    actual = tema_actual()
    botones = [(("✅ " if k == actual else "") + v, f"es|{k}") for k, v in TEMAS.items()]
    tg.mensaje(chat_id, "🎨 <b>Estilo de las imágenes</b>\nElige uno o mira antes las muestras.",
               _filas(botones, 3) + [[("👀 Ver muestras de todos", "es|ver")]])


def _estilo(tg: Telegram, chat_id, b: dict, eleccion: str) -> None:
    if eleccion == "ver":
        tg.mensaje(chat_id, "⏳ Preparando muestras de los 5 estilos (tarda un minuto)…")
        posts = estado.posts()
        post = next((p for p in posts.values() if p.get("json") and p.get("competicion") == "dh_masc"), None)
        if not post:
            _, post = preparar("dh_masc", "unico")
        datos = json.loads((RAIZ / post["json"]).read_text(encoding="utf-8"))
        with tempfile.TemporaryDirectory() as tmp:
            for k, nombre in TEMAS.items():
                tg.foto(chat_id, hoja_muestras(datos, k, Path(tmp)), nombre)
        _menu_estilo(tg, chat_id)
        return
    if eleccion in TEMAS:
        real = estado.bot()  # b es el contexto del chat: el tema se guarda en el estado general
        real["tema"] = eleccion
        estado.guardar_bot(real)
        tg.mensaje(chat_id, f"🎨 Estilo cambiado a <b>{TEMAS[eleccion]}</b>. Todo lo que te mande a partir de ahora saldrá así.")


def _atender_pedido(tg: Telegram, chat_id, texto: str) -> bool:
    pedido = interpretar(texto)
    if pedido is None:
        return False
    etiquetas = {DESABREV[c]: t.split(" ", 1)[1].lower() for t, c in QUE if c != "*"}
    que = "el carrusel completo" if pedido.claves is None else ", ".join(etiquetas[c] for c in pedido.claves)
    tg.mensaje(chat_id, f"⏳ Preparando {que}…")
    _servir(tg, chat_id, pedido.ligas, pedido.claves, pedido.jornada)
    return True


class Difusion:
    """Envuelve el cliente de Telegram: lo que se manda al dueño se reparte entre
    los usuarios que quieren ese aviso (tipo) de esa liga (comp), según sus preferencias."""

    def __init__(self, tg: Telegram, b: dict, tipo: str | None = None, comp: str | None = None):
        self.tg, self.b, self.dueno, self.tipo, self.comp = tg, b, b.get("chat_id"), tipo, comp

    def para(self, tipo: str | None, comp: str | None = None) -> "Difusion":
        return Difusion(self.tg, self.b, tipo, comp)

    def _todos(self, chat_id):
        if chat_id != self.dueno:
            return [chat_id]
        return [u for u in preferencias.usuarios(self.b) if preferencias.quiere(self.b, u, self.tipo, self.comp)]

    def mensaje(self, chat_id, *a, **k):
        r = None
        for c in self._todos(chat_id):
            try:
                r = self.tg.mensaje(c, *a, **k)
            except Exception:
                traceback.print_exc()
        return r

    def album(self, chat_id, *a, **k):
        for c in self._todos(chat_id):
            try:
                self.tg.album(c, *a, **k)
            except Exception:
                traceback.print_exc()

    def foto(self, chat_id, *a, **k):
        for c in self._todos(chat_id):
            try:
                self.tg.foto(c, *a, **k)
            except Exception:
                traceback.print_exc()

    def __getattr__(self, nombre):
        return getattr(self.tg, nombre)


def _quien(u: dict) -> str:
    de = (u.get("message") or {}).get("from") or {}
    nombre = " ".join(x for x in (de.get("first_name"), de.get("last_name")) if x) or "Alguien"
    return nombre + (f" (@{de['username']})" if de.get("username") else "")


def _invitacion(tg: Telegram, b: dict, u: dict, chat_id) -> None:
    """Alguien que no es el dueño ni invitado escribe al bot: pedir permiso al dueño."""
    texto = (u.get("message") or {}).get("text", "")
    pendientes = b.setdefault("solicitudes", {})
    if not texto.startswith("/start") or str(chat_id) in pendientes:
        return
    pendientes[str(chat_id)] = _quien(u)
    tg.mensaje(chat_id, "👋 He avisado al administrador. Cuando te dé acceso te escribo.")
    tg.mensaje(b["chat_id"], f"🔑 <b>{html.escape(_quien(u))}</b> quiere usar el bot.",
               [[("✅ Aceptar", f"inv|ok|{chat_id}"), ("❌ Rechazar", f"inv|no|{chat_id}")]])


def _gestionar_invitacion(tg: Telegram, b: dict, partes: list[str]) -> None:
    accion, otro = partes[1], partes[2]
    nombre = b.get("solicitudes", {}).pop(otro, None) or b.get("invitados", {}).get(otro, otro)
    if accion == "ok":
        b.setdefault("invitados", {})[otro] = nombre
        tg.mensaje(b["chat_id"], f"✅ {html.escape(nombre)} ya puede usar el bot.")
        tg.mensaje(int(otro), "✅ ¡Tienes acceso! Te llegarán también los envíos automáticos.\n\n" + AYUDA,
                   teclado_fijo=TECLADO_FIJO)
    elif accion == "no":
        tg.mensaje(b["chat_id"], f"❌ Rechazada la solicitud de {html.escape(nombre)}.")
    elif accion == "del":
        b.get("invitados", {}).pop(otro, None)
        tg.mensaje(b["chat_id"], f"🗑 {html.escape(nombre)} ya no tiene acceso.")
        try:
            tg.mensaje(int(otro), "Tu acceso al bot se ha retirado.")
        except Exception:
            pass


def procesar(tg: Telegram, actualizaciones: list[dict]) -> None:
    posts = estado.posts()
    for u in actualizaciones:
        b = estado.bot()
        b["offset"] = u["update_id"] + 1
        estado.guardar_bot(b)
        msg = u.get("message") or (u.get("callback_query") or {}).get("message") or {}
        chat_id = msg.get("chat", {}).get("id")

        if b.get("chat_id") is None:
            if (u.get("message") or {}).get("text", "").startswith("/start"):
                b["chat_id"] = chat_id
                estado.guardar_bot(b)
                tg.comandos(COMANDOS)
                tg.mensaje(chat_id, "👋 Listo, este chat queda vinculado a la cuenta.\n\n" + AYUDA,
                           teclado_fijo=TECLADO_FIJO)
            continue
        es_dueno = chat_id == b["chat_id"]
        if not es_dueno and str(chat_id) not in b.get("invitados", {}):
            _invitacion(tg, b, u, chat_id)
            estado.guardar_bot(b)
            continue
        if es_dueno and "callback_query" in u and u["callback_query"].get("data", "").startswith("inv|"):
            tg.responder_boton(u["callback_query"]["id"])
            _gestionar_invitacion(tg, b, u["callback_query"]["data"].split("|"))
            estado.guardar_bot(b)
            continue

        # Contexto de este chat: cada usuario tiene su propia edición en curso
        esperas = b.setdefault("esperas", {})
        ctx = {**b, "chat_id": chat_id, "esperando": esperas.get(str(chat_id)), "es_dueno": es_dueno}
        try:
            if "callback_query" in u:
                _boton(tg, ctx, posts, u["callback_query"])
            else:
                _mensaje(tg, ctx, posts, u["message"])
        except AccesoRestringido:
            tg.mensaje(chat_id, "⏳ el origen A está limitando las peticiones y esto no está guardado todavía. "
                                "Lo estoy bajando poco a poco; prueba en unos minutos.")
        except Exception:
            tg.mensaje(chat_id, f"❗ Algo ha fallado:\n<code>{html.escape(traceback.format_exc()[-700:])}</code>")
        b = estado.bot()  # puede haber cambiado (estilo, semana...)
        b.setdefault("esperas", {})[str(chat_id)] = ctx.get("esperando")
        estado.guardar_bot(b)
        posts = estado.posts()


def _boton(tg: Telegram, b: dict, posts: dict, cq: dict) -> None:
    chat_id = b["chat_id"]
    partes = cq.get("data", "").split("|")
    tg.responder_boton(cq["id"])
    if partes[0] == "pf":
        _boton_pref(tg, chat_id, cq, partes)
        return
    if partes[0] == "m0":
        tg.mensaje(chat_id, *(_menu_que(partes[1]) if len(partes) > 1 else _menu_inicio(chat_id)))
        return
    if partes[0].startswith("m"):
        b["esperando"] = None
        _menu(tg, chat_id, cq, partes)
        return
    if partes[0] == "es":
        _estilo(tg, chat_id, b, partes[1])
        return
    if partes[0] == "vd":  # submenú de vídeos de una liga
        tg.editar(chat_id, cq["message"]["message_id"], *_menu_videos(partes[1]))
        return
    if partes[0] == "vv":
        pedir_video(tg, chat_id, partes[1], partes[2])
        return
    if partes[0] == "vp":  # lista de partidos para el «así fue»
        tg.editar(chat_id, cq["message"]["message_id"], *_menu_partidos_video(partes[1]))
        return
    if partes[0] == "vf":
        pedir_video(tg, chat_id, partes[1], "final", id_partido=int(partes[2]))
        return
    if partes[0] in ("th", "to"):  # historias / original de imágenes de competición
        cod = partes[2]
        formato = "historia" if partes[0] == "th" or (len(partes) > 3 and partes[3] == "h") else "post"
        enviar_competicion(tg, chat_id, partes[1], _decod(cod) or [], formato, original=partes[0] == "to")
        return
    if partes[0] == "fo":  # original de una historia de resultado final
        comp, grupo = partes[1].split("/")
        with tempfile.TemporaryDirectory() as tmp:
            img = directo.historia_final(comp, grupo, int(partes[2]), Path(tmp))
            tg.album(chat_id, [img], como_archivo=True)
        return
    if partes[0] in ("ar", "ae"):
        formato, original = _formato(partes)
        if partes[0] == "ar":
            enviar_arbitros(tg, chat_id, partes[1], partes[2], formato, original)
        else:
            enviar_arbitros(tg, chat_id, partes[1], "e", formato, original, equipo=partes[2])
        return
    if partes[0] == "ag":
        formato, original = _formato(partes)
        enviar_agenda(tg, chat_id, partes[1], formato, original)
        return
    if partes[0] in ("fe", "fj"):
        formato, original = _formato(partes) if len(partes) >= 4 else ("post", False)
        _ficha(tg, chat_id, partes[0], partes[1], formato, original)
        return
    if partes[0] == "cc":
        formato, original = _formato(partes)
        _cara_ids(tg, chat_id, partes[1], partes[2], formato, original)
        return
    if partes[0] in ("eh", "eo"):  # historias / original de imágenes especiales
        comp, grupo = partes[1].split("/")
        clave = DESABREV[partes[2]]
        formato = "historia" if partes[0] == "eh" or (len(partes) > 3 and partes[3] == "h") else "post"
        id_partido = int(partes[4]) if len(partes) > 4 and partes[4].isdigit() else None
        enviar_especial(tg, chat_id, clave, comp, grupo, formato=formato, original=partes[0] == "eo",
                        id_partido=id_partido)
        return
    if partes[0] in ("ym", "yw", "yq", "yk"):  # MVP elegido por la afición (votación de la red)
        _boton_votacion(tg, b, partes)
        return
    if partes[0] == "pc":  # elegir otro partido para el partido de la jornada / ¿quién gana?
        texto, filas = _menu_cambiar_partido(partes[1], partes[2], partes[3] if len(partes) > 3 else "")
        tg.mensaje(chat_id, texto, filas)
        return
    if partes[0] == "pe" and partes[2] == "VP":  # vídeo de previa con otro destacado
        pedir_video(tg, chat_id, partes[1], "previa", id_partido=int(partes[3]))
        return
    if partes[0] == "pe":
        comp, grupo = partes[1].split("/")
        tg.mensaje(chat_id, "⏳ Preparando el partido que has elegido…")
        try:
            hecho = enviar_especial(tg, chat_id, DESABREV[partes[2]], comp, grupo, id_partido=int(partes[3]))
        except RuntimeError as e:
            hecho = False
            tg.mensaje(chat_id, f"No he podido: {e}")
        if not hecho:
            tg.mensaje(chat_id, "Ese partido ya no está pendiente.")
        return
    accion, pid, cod = (partes + ["", ""])[:3]
    if accion in ("h", "o") and pid in posts:
        formato = "historia" if accion == "h" or (len(partes) > 3 and partes[3] == "h") else "post"
        enviar(tg, chat_id, pid, posts[pid], _decod(cod), formato=formato, original=accion == "o")
        return
    post = posts.get(pid)
    if not post:
        tg.mensaje(chat_id, "Ese contenido ya no existe.")
        return
    b["esperando"] = {"accion": accion, "post": pid, "claves": cod, "cambios": 0}
    if accion == "xv":
        datos = json.loads((RAIZ / post["json"]).read_text(encoding="utf-8"))
        xv = "\n".join(
            f"{d}. {nombres.jugador(j['nombre'])['completo']} ({nombres.equipo_abr(j['equipo'])})"
            for d, j in sorted(datos["xv_ideal"].items(), key=lambda x: int(x[0]))
        )
        tg.mensaje(
            chat_id,
            f"✏️ XV de <b>{_titulo(post)}</b>:\n\n{html.escape(xv)}\n\n"
            "Escribe el dorsal y el nombre del que quieres poner (p. ej. <code>9 Araña</code>). "
            "Puedes mandar varios cambios. Cuando acabes escribe <code>listo</code>.",
        )
    elif accion == "foto":
        tg.mensaje(chat_id, f"📷 Mándame la foto para la portada de <b>{_titulo(post)}</b>.")


def _mensaje(tg: Telegram, b: dict, posts: dict, m: dict) -> None:
    chat_id = b["chat_id"]
    texto = (m.get("text") or "").strip()
    esperando = b.get("esperando") or {}
    post = posts.get(esperando.get("post", ""))

    if texto.startswith(("/start", "/ayuda", "/help")) or texto == "❓ Ayuda":
        tg.mensaje(chat_id, AYUDA, teclado_fijo=TECLADO_FIJO)
    elif texto.startswith("/usuarios") and b.get("es_dueno"):
        invitados = estado.bot().get("invitados", {})
        if not invitados:
            tg.mensaje(chat_id, "Solo tú usas el bot. Para invitar a alguien: que busque el bot en Telegram y le dé a Iniciar.")
        else:
            tg.mensaje(chat_id, "👥 <b>Usuarios con acceso</b>",
                       [[(f"🗑 Quitar a {n[:40]}", f"inv|del|{i}")] for i, n in invitados.items()])
    elif texto.startswith("/equipo"):
        _buscar(tg, chat_id, "fe", texto[len("/equipo"):].strip())
    elif texto.startswith("/jugador"):
        _buscar(tg, chat_id, "fj", texto[len("/jugador"):].strip())
    elif texto.startswith("/cara"):
        _cara(tg, chat_id, texto[len("/cara"):].strip())
    elif texto.startswith("/arbitros") or texto.startswith("/árbitros"):
        equipo = texto.split(maxsplit=1)[1].strip() if " " in texto else ""
        if not equipo:
            tg.mensaje(chat_id, "Escribe el equipo, p. ej. <code>/arbitros vrac</code>")
        else:
            cands = [c for c in fichas.buscar_equipo(equipo) if c["comp"] in ARBITROS]
            comp = cands[0]["comp"] if cands else "dh_masc"
            enviar_arbitros(tg, chat_id, comp, "e", equipo=equipo)
    elif texto.startswith("/agenda"):
        enviar_agenda(tg, chat_id, "n")
    elif texto.startswith("/avisos") or texto == "⚙️ Avisos":
        tg.mensaje(chat_id, *_menu_avisos(chat_id))
    elif texto.startswith("/favoritas") or texto == "⭐ Favoritas":
        favs = _favoritas(chat_id)
        filas = _filas(favs, 2) + [[("✏️ Editar favoritas", "pf|F|N")]]
        tg.mensaje(chat_id, "⭐ <b>Tus favoritas</b>" if favs else "No tienes favoritas todavía.", filas)
    elif texto.startswith("/estilo") or texto == "🎨 Estilo":
        _menu_estilo(tg, chat_id)
    elif texto.startswith("/pedir") or texto == "📋 Pedir":
        b["esperando"] = None
        tg.mensaje(chat_id, *_menu_inicio(chat_id))
    elif texto.startswith("/semana"):
        tg.mensaje(chat_id, "⏳ Preparando los carruseles de esta semana…")
        if not semana(tg, chat_id, ligas=preferencias.de(estado.bot(), chat_id)["ligas"]):
            tg.mensaje(chat_id, "No hay jornadas nuevas desde el último envío. Pídeme la que quieras, p. ej. <code>todo dh</code>.")
    elif m.get("photo") and post and esperando.get("accion") == "foto":
        estado.FOTOS.mkdir(parents=True, exist_ok=True)
        destino = estado.FOTOS / f"{esperando['post']}.jpg"
        destino.write_bytes(tg.descargar(m["photo"][-1]["file_id"]))
        ruta_json = RAIZ / post["json"]
        datos = json.loads(ruta_json.read_text(encoding="utf-8"))
        datos["foto_portada"] = {"archivo": _rel(destino)}
        ruta_json.write_text(json.dumps(datos, ensure_ascii=False, indent=2), encoding="utf-8")
        b["esperando"] = None
        tg.mensaje(chat_id, "📷 Foto recibida, regenero…")
        enviar(tg, chat_id, esperando["post"], post, _decod(esperando["claves"]), "🔄 Con tu foto de portada.")
    elif m.get("photo"):
        tg.mensaje(chat_id, "Para poner una foto de portada pulsa antes 📷 en el carrusel que quieras.")
    elif texto and post and esperando.get("accion") == "xv":
        if texto.lower() in ("listo", "ok", "fin", "ya"):
            b["esperando"] = None
            if esperando.get("cambios"):
                enviar(tg, chat_id, esperando["post"], post, _decod(esperando["claves"]), "🔄 XV actualizado.")
            else:
                tg.mensaje(chat_id, "Sin cambios.")
            return
        ruta_json = RAIZ / post["json"]
        datos = json.loads(ruta_json.read_text(encoding="utf-8"))
        try:
            resultado = cambiar_xv(datos, texto)
        except ValueError as e:
            if interpretar(texto):  # parece un pedido: salir del modo edición
                b["esperando"] = None
                _atender_pedido(tg, chat_id, texto)
            else:
                tg.mensaje(chat_id, f"🤔 {html.escape(str(e))}")
            return
        ruta_json.write_text(json.dumps(datos, ensure_ascii=False, indent=2), encoding="utf-8")
        esperando["cambios"] = esperando.get("cambios", 0) + 1
        b["esperando"] = esperando
        tg.mensaje(chat_id, f"✔️ {html.escape(resultado)}\n(escribe <code>listo</code> para ver la imagen)")
    elif texto and esperando.get("accion") == "mvp_pct":
        _porcentajes_mvp(tg, b, texto)
    elif texto and _atender_pedido(tg, chat_id, texto):
        pass
    else:
        tg.mensaje(chat_id, "No te he entendido 🤔 Usa el menú:")
        tg.mensaje(chat_id, *_menu_inicio(chat_id))


def _toca(b: dict, clave: str, dia: int, hora: int) -> bool:
    """¿Toca la tarea semanal `clave` (día 0=lunes, desde la hora dada) y no se ha hecho?"""
    ahora = estado.ahora()
    semana_iso = f"{ahora.isocalendar().year}-W{ahora.isocalendar().week}"
    if ahora.weekday() == dia and ahora.hour >= hora and b.get(clave) != semana_iso:
        b[clave] = semana_iso
        estado.guardar_bot(b)
        return True
    return False


def _avisar_actas_bloqueadas(tg: Telegram, b: dict, chat_id) -> None:
    """Si el origen A rechaza las actas (403/429), avisa al dueño como mucho una vez al día."""
    from datosdep.scraper import origen_a

    if not origen_a.compartido().actas_bloqueadas:
        return
    hoy = estado.ahora().strftime("%Y-%m-%d")
    if b.get("aviso_actas") == hoy:
        return
    b["aviso_actas"] = hoy
    estado.guardar_bot(b)
    try:
        tg.mensaje(chat_id, f"⚠️ el origen A está rechazando la lectura de actas (código {origen_a.compartido().ultimo_codigo or '403/429'}; "
                            "429 = demasiadas peticiones, pasajero; 403 = acceso cerrado). Sigo con resultados y "
                            "clasificaciones; anotadores, XV y MVP quedan pendientes hasta que vuelva el acceso.")
    except Exception:
        traceback.print_exc()


def _cada_cuanto_directo() -> int:
    """Segundos entre comprobaciones de resultados: a menudo el finde, poco entre semana."""
    ahora = estado.ahora()
    if ahora.weekday() >= 5 and 11 <= ahora.hour < 23:
        return 4 * 60
    return 30 * 60


def bucle(tg: Telegram, minutos: float) -> None:
    fin = time.monotonic() + minutos * 60
    ultimo_directo = 0.0
    try:
        tg.comandos(COMANDOS)  # por si se han añadido comandos nuevos
    except Exception:
        pass
    while (restante := fin - time.monotonic()) > 5:
        b = estado.bot()
        chat_id = b.get("chat_id")
        tg_todos = Difusion(tg, b)  # lo automático llega al dueño y a los invitados
        if chat_id:
            if _toca(b, "semana_lunes", 0, 10):
                semana(tg_todos, chat_id, ligas=preferencias.ligas_de_todos(b, "semana"))
            elif _toca(b, "semana_martes", 1, 10):
                semana(tg_todos, chat_id, reintento=True, ligas=preferencias.ligas_de_todos(b, "semana"))
            elif _toca(b, "agenda_jueves", 3, 10):
                try:
                    enviar_agenda(tg_todos.para("agenda"), chat_id, "n")
                    for comp in ARBITROS:
                        enviar_arbitros(tg_todos.para("arbitros", comp), chat_id, comp, "d")
                except Exception:
                    traceback.print_exc()
            if time.monotonic() - ultimo_directo > _cada_cuanto_directo():
                ultimo_directo = time.monotonic()
                try:
                    directo.comprobar(tg_todos, b)
                except Exception:
                    traceback.print_exc()
                estado.guardar_bot(b)
            _avisar_actas_bloqueadas(tg, b, chat_id)
            try:
                precalentar.paso()  # un acta cada ~minuto como mucho, nunca en ráfaga
            except Exception:
                traceback.print_exc()
        espera = int(min(50, max(1, restante - 5)))
        procesar(tg, tg.actualizaciones(b.get("offset", 0), espera))
