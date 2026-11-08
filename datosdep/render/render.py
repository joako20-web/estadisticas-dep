"""JSON de jornada -> carrusel JPEG 1080x1350 (Jinja2 + Playwright).

Claves de slide:
- CLAVES (carrusel por defecto): portada, resultados, anotadores, xv, clasificacion, previa, temporada.
- EXTRA: datos (tarjetas de "el dato de la jornada").
- RANKINGS (solo bajo pedido, no entran en el carrusel):
  · ensayadores    "Máximos ensayadores" de la jornada (ensayos, puntos, rival).
  · pateadores     "Puntos al pie" de la jornada (transformaciones, golpes y drops).
  · ensayadores_t  "Ensayadores de la liga": ensayos en la temporada.
  · pateadores_t   "Pateadores de la liga": puntos al pie en la temporada, con desglose.
  · disciplina     "Tarjetas": jugadores con más amarillas/rojas en la temporada.
  · banquillo      "Desde el banquillo": puntos de suplentes (dorsal 16-23) en la temporada.
  · equipos        "La liga en números": mejor ataque, mejor defensa, más ensayos y más tarjetas.
"""
from __future__ import annotations

import atexit
import base64
import hashlib
import io
import os
import json
import re
from functools import lru_cache
from datetime import datetime
from pathlib import Path

from jinja2 import Environment, FileSystemLoader
from playwright.sync_api import sync_playwright

from datosdep.core.estadisticas import POSICIONES
from datosdep.pipeline import CONFIG, RAIZ, cargar_config, separar_descansos
from datosdep.rutas import leer_yaml
from datosdep.render import nombres
from datosdep.scraper.origen_a import compartido

TEMPLATES = Path(__file__).parent / "templates"
OUT = RAIZ / "out"

DIAS = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo"]
MESES = ["ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sep", "oct", "nov", "dic"]

# Filas del XV en el campo, delanteros arriba.
FILAS_XV = [(1, 2, 3), (6, 4, 5, 7), (8, 9, 10), (11, 12, 13, 14), (15,)]


def _env() -> Environment:
    env = Environment(loader=FileSystemLoader(TEMPLATES), autoescape=True)
    env.filters.update(
        corto=nombres.equipo_corto,
        abr=nombres.equipo_abr,
        jugador=nombres.jugador,
        titulo=nombres.titulo,
        posicion=lambda d: POSICIONES.get(int(d), ""),
        sep=_sin_puntos,
        unidad=_unidad,
    )
    return env


def _sin_puntos(texto) -> str:
    """El punto medio como separador universal es un tic de diseño generado:
    en las imágenes se usa coma."""
    return str(texto or "").replace(" · ", ", ")


UNIDADES = {"PTS": ("pt", "pts"), "ENS": ("ensayo", "ensayos"), "TARJ": ("tarjeta", "tarjetas")}


def _unidad(unidad: str, valor=None) -> str:
    """Unidad en palabras y en minúscula (nada de "ENS" o "TARJ")."""
    singular, plural = UNIDADES.get(str(unidad).upper(), (str(unidad).lower(), str(unidad).lower()))
    try:
        return singular if int(valor) == 1 else plural
    except (TypeError, ValueError):
        return plural


def _rango_fechas(partidos: list[dict]) -> str:
    fechas = sorted(datetime.fromisoformat(p["fecha"]) for p in partidos if p["fecha"])
    if not fechas:
        return ""
    a, b = fechas[0], fechas[-1]
    if a.date() == b.date():
        return f"{a.day} {MESES[a.month - 1]} {a.year}"
    if a.month == b.month:
        return f"{a.day}–{b.day} {MESES[b.month - 1]} {b.year}"
    return f"{a.day} {MESES[a.month - 1]} – {b.day} {MESES[b.month - 1]} {b.year}"


def _n(n: int, singular: str, plural: str) -> str:
    return f"{n} {singular if n == 1 else plural}"


def fila_anotador(x: dict, temporada: bool = False) -> dict:
    partes = []
    if x.get("ensayos"):
        partes.append(_n(x["ensayos"], "ensayo", "ensayos"))
    if not temporada:
        if x.get("conversiones"):
            partes.append(_n(x["conversiones"], "transf.", "transf."))
        if x.get("golpes"):
            partes.append(_n(x["golpes"], "golpe", "golpes"))
        if x.get("drops"):
            partes.append(_n(x["drops"], "drop", "drops"))
    elif x.get("id") is not None:  # tabla oficial: partidos jugados reales
        partes.append(_n(x["pj"], "partido", "partidos"))
    return {
        "nombre": x["nombre"],
        "equipo": x["equipo"],
        "valor": x["puntos"],
        "detalle": ", ".join(partes),
        "extra": f"vs {nombres.equipo_corto(x['rival'])}" if x.get("rival") else "",
    }


# Claves de slide, en orden de carrusel. Sirven para pedir slides sueltos.
CLAVES = ["portada", "resultados", "anotadores", "xv", "clasificacion", "previa", "temporada"]
# Slides que van aparte del carrusel (tarjetas de "el dato de la jornada").
EXTRA = ["datos"]
# Rankings bajo pedido (ver docstring del módulo)
RANKINGS = ["ensayadores", "pateadores", "ensayadores_t", "pateadores_t", "disciplina", "banquillo", "equipos"]
TAMANOS = {"post": (1080, 1350), "historia": (1080, 1920)}
ESCALA = 2  # imágenes finales de 2160x2700 (post) y 2160x3840 (historia)


def zonas_de(comp: str, grupo: str) -> list[dict]:
    cfg = cargar_config()["competiciones"][comp]
    return cfg.get("zonas_grupo", {}).get(grupo) or cfg.get("zonas", [])


def con_zonas(clasificacion: list[dict], comp: str, grupo: str) -> tuple[list[dict], list[dict]]:
    """Añade a cada fila su zona (franja de color) y devuelve la leyenda."""
    n = len(clasificacion)
    zonas = []
    for z in zonas_de(comp, grupo):
        desde = z["desde"] if z["desde"] > 0 else n + 1 + z["desde"]
        hasta = z["hasta"] if z["hasta"] > 0 else n + 1 + z["hasta"]
        zonas.append({**z, "desde": desde, "hasta": hasta})
    filas, usadas = [], []
    for f in clasificacion:
        z = next((z for z in zonas if z["desde"] <= f["posicion"] <= z["hasta"]), None)
        filas.append({**f, "zona": z["color"] if z else ""})
        if z and z not in usadas:
            usadas.append(z)
    return filas, [{"color": z["color"], "texto": z["texto"]} for z in usadas]


def slides_de_jornada(datos: dict) -> list[dict]:
    """El carrusel semanal de una liga: portada, resultados, anotadores, XV,
    clasificación, previa y anotadores de la temporada."""
    j = datos["jornada"]
    slides: list[dict] = []

    foto = datos.get("foto_portada")
    partes = ["resultados"]
    if datos["anotadores"]:
        partes.append("anotadores")
    if datos.get("xv_ideal"):
        partes.append("XV ideal")
    partes.append("clasificación")
    bajada = ", ".join(partes[:-1]) + f" y {partes[-1]}" if len(partes) > 1 else partes[0]
    destacado = None
    if datos.get("xv_ideal"):
        mvp = max(datos["xv_ideal"].values(), key=lambda x: x["nota"])
        destacado = {"motivo": "Mejor jugador de la jornada", "jugador": mvp["nombre"], "equipo": mvp["equipo"],
                     "dorsal": mvp["dorsal"], "linea": fila_anotador(mvp)["detalle"], "puntos": mvp["puntos"]}
    elif datos["anotadores"]:
        top = datos["anotadores"][0]
        destacado = {"motivo": "Máximo anotador de la jornada", "jugador": top["nombre"], "equipo": top["equipo"],
                     "dorsal": top["dorsal"], "linea": fila_anotador(top)["detalle"], "puntos": top["puntos"]}
    slides.append(
        {
            "tipo": "portada",
            "clave": "portada",
            "foto": _foto(foto) if foto else None,
            "bajada": f"{bajada[:1].upper()}{bajada[1:]}",
            "credito": destacado,
        }
    )
    # Los datos guardados antes de separar los descansos aún traen el «partido» contra DESCANSO
    jugados, descansan = separar_descansos(datos["partidos"])
    slides.append(
        {"tipo": "resultados", "clave": "resultados", "partidos": jugados, "fechas": _rango_fechas(jugados),
         "descansa": datos.get("descansa") or descansan}
    )
    if datos["anotadores"]:
        slides.append(
            {
                "tipo": "ranking",
                "clave": "anotadores",
                "sup": f"Jornada {j}",
                "titulo": "Máximos anotadores",
                "unidad": "PTS",
                "filas": [fila_anotador(x) for x in datos["anotadores"][:7]],
            }
        )
    if datos.get("xv_ideal"):
        xv = datos["xv_ideal"]
        mvp = max(xv, key=lambda d: xv[d]["nota"])
        slides.append(
            {"tipo": "xv", "clave": "xv", "xv": xv, "mvp": int(mvp), "filas": [{"dorsales": d} for d in FILAS_XV]}
        )
    filas, leyenda = con_zonas(datos["clasificacion"], datos["competicion"], datos["grupo"])
    slides.append({"tipo": "clasificacion", "clave": "clasificacion", "filas": filas, "leyenda": leyenda})
    prox = datos.get("proxima_jornada")
    reales, descansan_sig = separar_descansos(prox["partidos"]) if prox else ([], [])
    if reales:
        partidos = []
        for p in reales:
            f = datetime.fromisoformat(p["fecha"]) if p["fecha"] else None
            partidos.append(
                {
                    **p,
                    "dia": f"{DIAS[f.weekday()][:3]} {f.day} {MESES[f.month - 1]}" if f else "Por fijar",
                    # 00:00 en el origen A/OrigenB = hora sin fijar
                    "hora": "" if not f or (f.hour, f.minute) == (0, 0) else f.strftime("%H:%M"),
                }
            )
        slides.append({"tipo": "previa", "clave": "previa", "numero": prox["numero"], "partidos": partidos,
                       "descansa": prox.get("descansa") or descansan_sig})
    if datos["temporada_anotadores"]:
        slides.append(
            {
                "tipo": "ranking",
                "clave": "temporada",
                "sup": f"Temporada {datos['temporada']}",
                "titulo": "Anotadores de la liga",
                "unidad": "PTS",
                "filas": [fila_anotador(x, True) for x in datos["temporada_anotadores"][:7]],
            }
        )
    slides += [dict(t) for t in datos.get("datos_jornada", [])]
    slides += slides_rankings(datos)
    return slides


def slides_rankings(datos: dict) -> list[dict]:
    """Slides de RANKINGS; se omiten los que no tienen datos."""
    r = datos.get("rankings") or {}
    j, temp = datos["jornada"], f"Temporada {datos['temporada']}"
    defs = [
        ("ensayadores", "Máximos ensayadores", f"Jornada {j}", "ENS"),
        ("pateadores", "Puntos al pie", f"Jornada {j}", "PTS"),
        ("ensayadores_t", "Ensayadores de la liga", temp, "ENS"),
        ("pateadores_t", "Pateadores de la liga", temp, "PTS"),
        ("disciplina", "Tarjetas", temp, "TARJ"),
        ("banquillo", "Desde el banquillo", f"Puntos de suplentes, {temp}", "PTS"),
    ]
    slides = []
    for clave, titulo, sup, unidad in defs:
        filas = r.get(clave) or []
        if not filas:
            continue
        filas = [{**f, "extra": f"vs {nombres.equipo_corto(f['rival'])}" if f.get("rival") else ""} for f in filas]
        slides.append({"tipo": "ranking", "clave": clave, "titulo": titulo, "sup": sup, "unidad": unidad,
                       "filas": filas})
    if r.get("equipos"):
        slides.append({"tipo": "bloques", "clave": "equipos", "titulo": "La liga en números",
                       "sup": f"Tras la jornada {j}", "bloques": r["equipos"]})
    return slides


def _data_uri(raw: bytes, mime: str) -> str:
    return f"data:{mime};base64,{base64.b64encode(raw).decode()}"


def _foto(foto: dict) -> str:
    """Foto de portada: un archivo local puesto a mano o una URL de el origen A."""
    if foto.get("archivo"):
        ruta = RAIZ / foto["archivo"]
        mime = "image/png" if ruta.suffix.lower() == ".png" else "image/jpeg"
        return _data_uri(ruta.read_bytes(), mime)
    return _data_uri(compartido().imagen(foto["url"]), "image/jpeg")


@lru_cache(maxsize=512)
def _imagen_escudo(url: str):
    """Escudo como imagen RGB sobre fondo blanco (los PNG transparentes salían negros)."""
    from PIL import Image

    img = Image.open(io.BytesIO(compartido().imagen(url)))
    if img.mode in ("RGBA", "LA") or (img.mode == "P" and "transparency" in img.info):
        img = img.convert("RGBA")
        fondo = Image.new("RGB", img.size, (255, 255, 255))
        fondo.paste(img, mask=img.split()[-1])
        return fondo
    return img.convert("RGB")


def _jpeg_uri(img) -> str:
    buf = io.BytesIO()
    img.save(buf, "JPEG", quality=94)
    return _data_uri(buf.getvalue(), "image/jpeg")


def _seguro_en_circulo(img, margen: float = 1.08):
    """Recorta el blanco sobrante y centra el escudo en un lienzo cuadrado cuyo
    círculo inscrito lo contiene entero (diagonal del escudo <= diámetro).

    Las plantillas pintan los escudos en círculos (border-radius: 50%): así ningún
    escudo se corta por las esquinas, sea alargado, ancho o cuadrado.
    """
    import math

    from PIL import Image

    tinta = img.convert("L").point(lambda v: 255 if v < 238 else 0)
    caja = tinta.getbbox()
    if caja:
        img = img.crop(caja)
    w, h = img.size
    lado = max(1, math.ceil(math.hypot(w, h) * margen))
    try:
        # Radio real del dibujo (píxel de tinta más lejano del centro): un escudo redondo
        # llena el círculo en vez de quedarse pequeño por la diagonal de su caja.
        import numpy as np

        ys, xs = np.nonzero(np.asarray(tinta.crop(caja or (0, 0, w, h))))
        if len(xs):
            radio = float(np.hypot(xs + 0.5 - w / 2, ys + 0.5 - h / 2).max())
            lado = max(1, min(lado, math.ceil(2 * radio * margen), 1 << 14))
    except ImportError:
        pass
    lienzo = Image.new("RGB", (lado, lado), (255, 255, 255))
    lienzo.paste(img, ((lado - w) // 2, (lado - h) // 2))
    return lienzo


@lru_cache(maxsize=512)
def _escudo_uri(url: str) -> str:
    """Escudo listo para un círculo (se pinta a doble resolución: hasta ~460 px reales)."""
    try:
        img = _seguro_en_circulo(_imagen_escudo(url))
    except Exception:
        return ""
    img.thumbnail((480, 480))
    return _jpeg_uri(img)


@lru_cache(maxsize=64)
def _escudo_conjunto(urls: tuple[str, ...]) -> str:
    """Varios escudos en un mismo círculo (equipos que son conjunto de 2-3 clubes)."""
    from PIL import Image

    lienzo = Image.new("RGB", (480, 480), (255, 255, 255))
    # Huecos dentro del círculo inscrito (radio 240) para 2 o 3 escudos
    # (x, y, lado) de cada hueco: su círculo inscrito queda dentro del círculo grande
    # (radio 240, con margen) y los huecos no se tocan entre sí
    huecos = {2: [(10, 128, 224), (246, 128, 224)],
              3: [(134, 9, 212), (24, 197, 212), (244, 197, 212)]}[min(len(urls), 3)]
    for url, (x, y, lado) in zip(urls, huecos):
        try:
            img = _seguro_en_circulo(_imagen_escudo(url), margen=1.02)
        except Exception:
            continue
        img.thumbnail((lado, lado))
        lienzo.paste(img, (x + (lado - img.width) // 2, y + (lado - img.height) // 2))
    return _jpeg_uri(lienzo)


def escudos_de_clubes(clubes: list[str]) -> tuple[str, ...]:
    """Busca el escudo de cada club (por nombre) entre todos los equipos que leemos."""
    from datosdep.fichas import indice_equipos, norm

    indice = [c for c in indice_equipos() if c.get("escudo")]
    urls = []
    for club in clubes:
        n = norm(club)
        candidatos = [c for c in indice if n in norm(c["equipo"]) and " - " not in c["equipo"]]
        if candidatos:  # el nombre más corto suele ser el club "puro" (sin filial ni patrocinador)
            urls.append(min(candidatos, key=lambda c: len(c["equipo"]))["escudo"])
    return tuple(urls)


def escudo_equipo(equipo: str, escudos: dict) -> str:
    conjunto = nombres.clubes_conjunto(equipo)
    if conjunto:
        urls = escudos_de_clubes(conjunto)
        if len(urls) >= 2:
            return _escudo_conjunto(urls)
    return _escudo_uri(escudos[equipo]) if equipo in escudos else ""


TEMAS = {"noche": "Noche", "brutal": "Brutal", "prensa": "Prensa", "tele": "Tele", "retro": "Retro"}
# Tipografías de cada tema (titulares y datos/texto); ver templates/temas.css
FUENTES_TEMA = {
    "noche": {"Teko", "Barlow Condensed"},
    "brutal": {"Anton", "Archivo Narrow"},
    "prensa": {"Playfair Display", "IBM Plex Sans Condensed"},
    "tele": {"Oswald", "Roboto Condensed"},
    "retro": {"Alfa Slab One", "Barlow Condensed"},
}
FUENTES = RAIZ / "assets" / "fuentes"


@lru_cache(maxsize=8)
def css_fuentes(tema: str) -> str:
    """@font-face con las fuentes del tema incrustadas (sin pedir nada a Google)."""
    familias = FUENTES_TEMA.get(tema, FUENTES_TEMA["noche"])
    reglas = []
    for f in json.loads((FUENTES / "fuentes.json").read_text()):
        if f["familia"] not in familias:
            continue
        datos = base64.b64encode((FUENTES / f["archivo"]).read_bytes()).decode()
        reglas.append(
            f"@font-face {{ font-family: '{f['familia']}'; font-weight: {f['peso']}; font-style: normal;"
            f" font-display: block; src: url(data:font/woff2;base64,{datos}) format('woff2');"
            f" unicode-range: {f['rango']}; }}"
        )
    return "\n".join(reglas)


@lru_cache(maxsize=4)
def _logo_uri_cache(ruta: Path, mtime: float) -> str:
    return _data_uri(ruta.read_bytes(), "image/png")


def _logo_uri(ruta: Path) -> str:
    """Logo en base64, calculado una vez (cada imagen lo incrusta)."""
    return _logo_uri_cache(ruta, ruta.stat().st_mtime)


def tema_actual() -> str:
    """Tema elegido en Telegram (/estilo) o el de config/marca.yaml."""
    from datosdep import estado

    marca = leer_yaml(CONFIG / "marca.yaml")
    tema = estado.bot().get("tema") or marca.get("tema", "noche")
    return tema if tema in TEMAS else "noche"


def html_post(datos: dict, slides: list[dict], formato: str = "post", tema: str | None = None) -> str:
    cfg = cargar_config()["competiciones"][datos["competicion"]]
    marca = leer_yaml(CONFIG / "marca.yaml")
    logo = _logo_uri(RAIZ / marca["logo"])
    escudos = datos.get("escudos", {})
    env = _env()
    env.filters["escudo"] = lambda equipo: escudo_equipo(equipo, escudos)
    return (
        env
        .get_template("post.html.j2")
        .render(
            slides=slides,
            formato=formato,
            tema=(tema := tema or tema_actual()),
            fuentes=css_fuentes(tema),
            marca=marca,
            logo=logo,
            jornada=datos["jornada"],
            temporada=datos["temporada"],
            comp={
                "nombre": cfg["nombre"],
                "corto": cfg["corto"],
                "grupo": None if datos["grupo"] == "unico" else f"Grupo {datos['grupo']}",
                # Cabecera propia para imágenes que no son de una liga (agenda...)
                **(datos.get("cabecera") or {}),
            },
        )
    )


class _Navegador:
    """Un único Chromium para todo el proceso (arrancarlo cuesta ~1 s)."""

    def __init__(self):
        self.pw = self.nav = None

    def pagina(self, ancho: int, alto: int):
        if self.nav is None or not self.nav.is_connected():
            self.pw = sync_playwright().start()
            canal = os.environ.get("PLAYWRIGHT_CHANNEL")  # "chrome" en GitHub: ya viene instalado
            self.nav = self.pw.chromium.launch(channel=canal) if canal else self.pw.chromium.launch()
        # Doble resolución: texto y escudos nítidos aunque Telegram vuelva a comprimir
        pagina = self.nav.new_page(viewport={"width": ancho, "height": alto}, device_scale_factor=ESCALA)
        return pagina

    def cerrar(self):
        if self.nav:
            self.nav.close()
            self.pw.stop()
            self.nav = self.pw = None


_NAV = _Navegador()
atexit.register(_NAV.cerrar)

# Recursos incrustados (escudos, logo, fuentes) servidos desde una dirección interna:
# el HTML iba con cada data URI repetido en cada slide (~7 MB por carrusel) y solo
# cargarlo costaba ~2 s. Los bytes son los mismos, así que la imagen no cambia.
_ORIGEN = "http://datosdep.local/r/"
_DATA_URI = re.compile(r"data:([\w/+.-]+);base64,([A-Za-z0-9+/=]+)")
_RECURSOS: dict[str, tuple[str, bytes]] = {}


def _externalizar(html: str) -> str:
    def sustituir(m: re.Match) -> str:
        clave = hashlib.sha1(m.group(2).encode()).hexdigest()
        if clave not in _RECURSOS:
            _RECURSOS[clave] = (m.group(1), base64.b64decode(m.group(2)))
        return _ORIGEN + clave
    return _DATA_URI.sub(sustituir, html)


def _servir_recurso(route) -> None:
    mime, cuerpo = _RECURSOS.get(route.request.url.removeprefix(_ORIGEN), ("text/plain", b""))
    route.fulfill(status=200, body=cuerpo, content_type=mime,
                  headers={"Access-Control-Allow-Origin": "*", "Cache-Control": "max-age=86400"})


# Ajuste automático: los textos de una línea que no caben (nombres de equipos y
# jugadores largos) reducen su tamaño poco a poco en vez de cortarse con "…".
# Mínimo: el 62 % del tamaño original y nunca menos de 22 px. Solo si aun así no
# caben, se queda la elipsis como último recurso.
_JS_AJUSTA = """() => {
  let n = 0;
  for (const e of document.querySelectorAll('section.slide *')) {
    if (!(e.textContent || '').trim()) continue;
    const s = getComputedStyle(e);
    if (s.overflowX === 'visible' && s.textOverflow !== 'ellipsis') continue;
    if (e.scrollWidth <= e.clientWidth + 1) continue;
    let fs = parseFloat(s.fontSize);
    const min = Math.max(22, fs * 0.62);
    while (e.scrollWidth > e.clientWidth + 1 && fs > min) {
      fs = Math.max(min, fs - 1);
      e.style.fontSize = fs + 'px';
    }
    n++;
  }
  // Nombres de equipo que admiten 2 líneas: si ocupan 3 o más, se reducen hasta caber en 2
  for (const e of document.querySelectorAll('section.slide .equipo .nom, section.slide .final-eq .nom, section.slide .pj-nom, section.slide .md-nom')) {
    const s = getComputedStyle(e);
    let fs = parseFloat(s.fontSize);
    const min = Math.max(22, fs * 0.6);
    const lineas = () => Math.round(e.getBoundingClientRect().height / (parseFloat(getComputedStyle(e).lineHeight) || fs));
    while (lineas() > 2 && fs > min) {
      fs = Math.max(min, fs - 1);
      e.style.fontSize = fs + 'px';
    }
  }
  return n;
}"""

# Detecta textos recortados (elipsis) o que se salen del slide. Con la variable de
# entorno RUGBYIG_AUDITA=<fichero.jsonl> se registran (para revisar plantillas).
_JS_AUDITA = """(clave) => {
  const out = [];
  for (const sec of document.querySelectorAll('section.slide')) {
    const caja = sec.getBoundingClientRect();
    for (const e of sec.querySelectorAll('*')) {
      if (!e.childElementCount && !(e.textContent || '').trim()) continue;
      const s = getComputedStyle(e);
      const corta = e.scrollWidth > e.clientWidth + 1 && s.overflowX !== 'visible';
      const r = e.getBoundingClientRect();
      const fuera = r.width > 0 && (r.right > caja.right + 1 || r.left < caja.left - 1 || r.bottom > caja.bottom + 1);
      if ((corta || fuera) && (e.textContent || '').trim() && !e.querySelector('*:not(br)'))
        out.push({tipo: corta ? 'corta' : 'fuera', clase: e.className, texto: e.textContent.trim().slice(0, 60),
                  fs: s.fontSize});
    }
  }
  return out;
}"""


def renderizar_slides(
    datos: dict, slides: list[dict], destino: Path, formato: str = "post", tema: str | None = None
) -> list[Path]:
    """Pinta los slides dados como JPEG (1080x1350 o 1080x1920)."""
    destino.mkdir(parents=True, exist_ok=True)
    for viejo in destino.glob("*.jpg"):
        viejo.unlink()
    if not slides:
        return []
    ancho, alto = TAMANOS[formato]
    generados: list[Path] = []
    pagina = _NAV.pagina(ancho, alto)
    try:
        pagina.route(_ORIGEN + "*", _servir_recurso)
        pagina.set_content(_externalizar(html_post(datos, slides, formato, tema)), wait_until="load")
        pagina.evaluate("document.fonts.ready")
        pagina.evaluate(_JS_AJUSTA)
        if os.environ.get("RUGBYIG_AUDITA"):
            problemas = pagina.evaluate(_JS_AUDITA, "")
            with open(os.environ["RUGBYIG_AUDITA"], "a", encoding="utf-8") as f:
                f.write(json.dumps({"tema": tema or tema_actual(), "formato": formato,
                                    "comp": datos.get("competicion"), "claves": [s["clave"] for s in slides],
                                    "destino": str(destino), "problemas": problemas}, ensure_ascii=False) + "\n")
        for sec, s in zip(pagina.query_selector_all("section.slide"), slides):
            jpg = destino / f"{len(generados) + 1:02d}_{s['clave']}.jpg"
            # PNG -> JPEG sin submuestreo de color: los bordes de alto contraste (círculos de
            # los escudos sobre fondo oscuro) no se rompen en bloques como con el 4:2:0 de Chromium.
            from PIL import Image

            Image.open(io.BytesIO(sec.screenshot(type="png"))).convert("RGB").save(
                jpg, "JPEG", quality=97, subsampling=0, optimize=True)
            generados.append(jpg)
    finally:
        pagina.close()
    return generados


def renderizar_jornada(
    ruta_json: Path, destino: Path | None = None, claves: list[str] | None = None,
    formato: str = "post",
) -> list[Path]:
    """Genera el carrusel (o solo los slides de `claves`) como JPEG.

    Sin `claves` se genera el carrusel; las tarjetas de datos solo si se piden.
    """
    datos = json.loads(Path(ruta_json).read_text(encoding="utf-8"))
    destino = destino or OUT / datos["competicion"] / datos["grupo"] / f"j{datos['jornada']:02d}"
    slides = slides_de_jornada(datos)
    slides = [s for s in slides if s["clave"] in claves] if claves else [s for s in slides if s["clave"] in CLAVES]
    return renderizar_slides(datos, slides, destino, formato)


def hoja_muestras(datos: dict, tema: str, destino: Path) -> Path:
    """Una imagen con 4 slides de ejemplo en ese tema, para elegir estilo."""
    from PIL import Image

    slides = {s["clave"]: s for s in slides_de_jornada(datos)}
    elegidos = [slides[c] for c in ("portada", "resultados", "clasificacion", "xv") if c in slides]
    imgs = renderizar_slides(datos, elegidos, destino / tema, "post", tema)
    hoja = Image.new("RGB", (2 * 540 + 20, 2 * 675 + 20), (40, 40, 40))
    for i, img in enumerate(imgs[:4]):
        hoja.paste(Image.open(img).resize((540, 675)), ((i % 2) * 560, (i // 2) * 695))
    salida = destino / f"{tema}.jpg"
    hoja.save(salida, quality=88)
    return salida
