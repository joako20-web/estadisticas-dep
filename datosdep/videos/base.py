"""Piezas comunes de los vídeos: props de marca/tema/fuentes, escudos y render con Remotion.

Python prepara las props y los efectos de sonido; la animación vive en video/
(una composición por plantilla) y se renderiza con `npx remotion render`.
"""
from __future__ import annotations

import hashlib
import json
import re
import shutil
import subprocess
import tempfile
import threading
import time
from pathlib import Path


from datosdep import sonido
from datosdep.pipeline import cargar_config, preparar_jornada, ruta_jornada
from datosdep.render import nombres
from datosdep.render import render as R
from datosdep.rutas import CONFIG, RAIZ, leer_yaml

VIDEO = RAIZ / "video"
PUBLICO = VIDEO / "public"
TEMAS_CSS = Path(R.__file__).parent / "templates" / "temas.css"
# Familias de cada tema para el vídeo (titulares/números y texto)
FUENTES = {"tele": ("Oswald", "Roboto Condensed")}
_UNO_A_LA_VEZ = threading.Lock()  # el bot puede pedir varios a la vez: se renderizan en fila
# Cachés (no cambian la calidad: se reutiliza trabajo idéntico)
CACHE_BUNDLES = VIDEO / ".bundles"  # proyecto ya empaquetado, por huella del código
CACHE_VIDEOS = RAIZ / ".cache" / "videos"  # MP4 ya hechos, por huella de props + código
MAX_VIDEOS_CACHE = 12
LISTO = VIDEO / "node_modules" / ".listo"  # lo crea la instalación en segundo plano (bot.yml)
INSTALANDO = VIDEO / ".instalando"


def colores_tema(tema: str) -> dict:
    """Variables CSS (--fondo, --acento...) del bloque `.tema-<tema> {` de temas.css."""
    css = TEMAS_CSS.read_text(encoding="utf-8")
    bloque = re.search(r"\.tema-" + tema + r"\s*\{(.*?)\}", css, re.S)
    if not bloque:
        return {}
    return {k: v.strip() for k, v in re.findall(r"--([\w-]+):\s*([^;]+);", bloque.group(1))
            if v.strip().startswith("#")}


def equipo(equipo: str, escudos: dict, puntos: int | None = None, gana: bool = False) -> dict:
    return {"nombre": nombres.equipo_corto(equipo), "abr": nombres.equipo_abr(equipo),
            "escudo": R.escudo_equipo(equipo, escudos), "puntos": puntos, "gana": gana}


def props_base(comp: str, jornada: int, temporada: str, tema: str = "tele") -> dict:
    """Marca, competición, colores del tema y tipografías: lo que llevan todas las plantillas."""
    cfg = cargar_config()["competiciones"][comp]
    marca = leer_yaml(CONFIG / "marca.yaml")
    tit, txt = FUENTES.get(tema, FUENTES["tele"])
    return {
        "competicion": cfg["nombre"], "corto": cfg.get("corto", cfg["nombre"]), "jornada": jornada,
        "temporada": temporada, "handle": marca["handle"],
        "logo": R._logo_uri(RAIZ / marca["logo"]),
        "tema": colores_tema(tema), "fuenteTitulo": tit, "fuenteTexto": txt,
    }


def datos_jornada(comp: str, grupo: str = "unico", jornada: int | None = None) -> dict:
    """JSON de la jornada. Si ya está guardada se usa tal cual (su clasificación es la de
    aquel momento); si no, se descarga."""
    ruta = ruta_jornada(comp, grupo, jornada) if jornada else None
    if not (ruta and ruta.exists()):
        ruta = preparar_jornada(comp, grupo, jornada)
    return json.loads(ruta.read_text(encoding="utf-8"))


def copiar_fuentes(familias: tuple[str, ...]) -> list[dict]:
    """Copia las woff2 del tema a video/public/fuentes y devuelve su lista para loadFont."""
    origen = RAIZ / "assets" / "fuentes"
    destino = PUBLICO / "fuentes"
    destino.mkdir(parents=True, exist_ok=True)
    lista = []
    for f in json.loads((origen / "fuentes.json").read_text(encoding="utf-8")):
        if f["familia"] in familias:
            shutil.copy2(origen / f["archivo"], destino / f["archivo"])
            lista.append({"familia": f["familia"], "peso": f["peso"], "archivo": f"fuentes/{f['archivo']}",
                          "rango": f["rango"]})
    return lista


def _huella(*partes: bytes) -> str:
    h = hashlib.sha256()
    for p in partes:
        h.update(p)
    return h.hexdigest()[:20]


def _huella_proyecto() -> str:
    """Huella del código de video/ y de lo que se sirve en public/: si no cambia, el
    empaquetado (y los vídeos ya hechos) siguen valiendo."""
    ficheros = sorted(
        [p for p in (VIDEO / "src").rglob("*") if p.is_file()]
        + [p for p in PUBLICO.rglob("*") if p.is_file()]
        + [VIDEO / "package-lock.json", VIDEO / "remotion.config.ts"]
    )
    return _huella(*(str(p.relative_to(VIDEO)).encode() + p.read_bytes() for p in ficheros))


def _bundle(huella: str) -> Path:
    """Empaqueta video/ una vez por versión del código (ahorra el webpack de cada render)."""
    destino = CACHE_BUNDLES / huella
    if not (destino / "index.html").exists():
        shutil.rmtree(CACHE_BUNDLES, ignore_errors=True)  # solo se guarda la versión actual
        subprocess.run(["npx", "remotion", "bundle", f"--out-dir={destino}", "--log=error"], cwd=VIDEO, check=True)
    return destino


def _guardar_en_cache(mp4: Path, clave: str) -> None:
    CACHE_VIDEOS.mkdir(parents=True, exist_ok=True)
    shutil.copy2(mp4, CACHE_VIDEOS / f"{clave}.mp4")
    viejos = sorted(CACHE_VIDEOS.glob("*.mp4"), key=lambda p: p.stat().st_mtime)[:-MAX_VIDEOS_CACHE]
    for p in viejos:
        p.unlink(missing_ok=True)


def renderizar(composicion: str, props: dict, salida: Path) -> Path:
    """Renderiza una composición de video/ con esas props (añade las fuentes y los sonidos).

    Si ya se hizo un vídeo con exactamente las mismas props y el mismo código, se copia
    el MP4 guardado en vez de volver a renderizarlo.
    """
    salida.parent.mkdir(parents=True, exist_ok=True)
    with _UNO_A_LA_VEZ:
        preparar_node()
        props = {**props, "fuentes": copiar_fuentes((props["fuenteTitulo"], props["fuenteTexto"]))}
        if not all((PUBLICO / "sfx" / f"{n}.wav").exists() for n in sonido.EFECTOS):
            sonido.generar(PUBLICO / "sfx")  # deterministas (semilla fija): basta con generarlos una vez
        huella = _huella_proyecto()
        texto = json.dumps(props, ensure_ascii=False, sort_keys=True)
        clave = _huella(composicion.encode(), texto.encode(), huella.encode())
        hecho = CACHE_VIDEOS / f"{clave}.mp4"
        if hecho.exists():
            shutil.copy2(hecho, salida)
            hecho.touch()  # recién usado: el último en salir de la caché
            return salida
        bundle = _bundle(huella)
        with tempfile.NamedTemporaryFile("w", suffix=".json", encoding="utf-8", delete=False) as f:
            f.write(texto)
        try:
            subprocess.run(["npx", "remotion", "render", str(bundle), composicion, str(salida), f"--props={f.name}",
                            "--codec=h264", "--crf=16", "--audio-bitrate=320k", "--log=warn"],
                           cwd=VIDEO, check=True, stdout=subprocess.DEVNULL)  # sin la barra de progreso en el log
        finally:
            Path(f.name).unlink(missing_ok=True)
        _guardar_en_cache(salida, clave)
    return salida


def preparar_node(espera_max: float = 300) -> None:
    """Deja listas las dependencias de video/ (Node y el navegador de Remotion).

    En GitHub Actions se instalan en segundo plano nada más arrancar (bot.yml), así que
    normalmente ya están; si la instalación sigue en marcha, se espera a que acabe.
    """
    if LISTO.exists() or ((VIDEO / "node_modules" / ".bin" / "remotion").exists() and not INSTALANDO.exists()):
        return
    limite = time.monotonic() + espera_max
    while INSTALANDO.exists() and not LISTO.exists() and time.monotonic() < limite:
        time.sleep(2)
    if LISTO.exists():
        return
    subprocess.run(["npm", "ci", "--no-audit", "--no-fund"], cwd=VIDEO, check=True)
    subprocess.run(["npx", "remotion", "browser", "ensure"], cwd=VIDEO, check=True)
    LISTO.touch()


def foto_jugador(url: str, ancho: int = 720, alto: int = 900) -> str:
    """Foto de el origen A recortada a 4:5 (cara arriba) como data URI, o "" si no hay o es
    pequeña (las de carnet de ~150-500 px se ven pixeladas a ese tamaño)."""
    if not url:
        return ""
    import io

    from PIL import Image

    from datosdep.pipeline import FOTO_MIN_PX
    from datosdep.scraper.origen_a import compartido

    try:
        img = Image.open(io.BytesIO(compartido().imagen(url))).convert("RGB")
    except Exception:
        return ""
    w, h = img.size
    if min(w, h) < FOTO_MIN_PX:
        return ""
    proporcion = ancho / alto
    if w / h > proporcion:  # más ancha: se recorta por los lados, centrada
        nuevo = round(h * proporcion)
        img = img.crop(((w - nuevo) // 2, 0, (w - nuevo) // 2 + nuevo, h))
    else:  # más alta: se recorta abajo (la cara suele estar en el tercio superior)
        nuevo = round(w / proporcion)
        arriba = round((h - nuevo) * 0.2)
        img = img.crop((0, arriba, w, arriba + nuevo))
    img = img.resize((ancho, alto), Image.LANCZOS)
    buf = io.BytesIO()
    img.save(buf, "JPEG", quality=90)
    return R._data_uri(buf.getvalue(), "image/jpeg")
