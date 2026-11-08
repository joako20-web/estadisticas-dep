"""Efectos de sonido sintetizados (sin bancos de sonido ni licencias) para los reels.

Todo se genera con numpy a 48 kHz. El volumen es discreto (picos entre -14 y -10 dB)
para que en la red quede sitio a la música que se ponga encima.
"""
from __future__ import annotations

import wave
from pathlib import Path

import numpy as np

SR = 48_000
_rng = np.random.default_rng(7)  # semilla fija: mismo sonido en cada render


def _t(seg: float) -> np.ndarray:
    return np.arange(int(SR * seg)) / SR


def _svf(x: np.ndarray, fc: np.ndarray, q: float = 0.7) -> np.ndarray:
    """Filtro paso banda de estado variable con frecuencia de corte que cambia en el tiempo."""
    f = 2 * np.sin(np.pi * np.clip(fc, 20, SR / 6) / SR)
    low = band = 0.0
    out = np.empty_like(x)
    for i, v in enumerate(x):
        high = v - low - q * band
        band += f[i] * high
        low += f[i] * band
        out[i] = band
    return out


def _env(n: int, ataque: float, caida: float) -> np.ndarray:
    t = np.arange(n) / SR
    sube = np.clip(t / max(ataque, 1e-4), 0, 1) ** 2
    return sube * np.exp(-np.maximum(t - ataque, 0) / caida)


def _norm(x: np.ndarray, db: float) -> np.ndarray:
    pico = np.max(np.abs(x)) or 1.0
    return x / pico * 10 ** (db / 20)


def whoosh(seg: float = 0.42, db: float = -13) -> np.ndarray:
    n = int(SR * seg)
    t = _t(seg)
    centro = 300 + 3200 * np.sin(np.pi * t / seg) ** 2  # sube y baja: paso de un objeto
    x = _svf(_rng.standard_normal(n), centro, q=0.9)
    env = np.sin(np.pi * np.clip(t / seg, 0, 1)) ** 1.6
    return _norm(x * env, db)


def impacto(db: float = -10) -> np.ndarray:
    t = _t(0.9)
    tono = np.sin(2 * np.pi * (48 * t + 70 * (1 - np.exp(-t * 18)) / 18))  # caída de tono 118->48 Hz
    golpe = _svf(_rng.standard_normal(t.size), np.full(t.size, 1800.0), q=1.2) * np.exp(-t * 60)
    x = tono * np.exp(-t * 5.5) + 0.35 * golpe
    return _norm(np.tanh(x * 1.6), db)


def tic(db: float = -16) -> np.ndarray:
    t = _t(0.05)
    x = np.sin(2 * np.pi * 2300 * t) * np.exp(-t * 140) + 0.3 * _rng.standard_normal(t.size) * np.exp(-t * 400)
    return _norm(x, db)


def riser(seg: float = 1.0, db: float = -15) -> np.ndarray:
    t = _t(seg)
    centro = 400 * (12 ** (t / seg))  # 400 Hz -> 4,8 kHz
    ruido = _svf(_rng.standard_normal(t.size), centro, q=0.6)
    fase = 2 * np.cumsum(np.pi * (180 * (4 ** (t / seg)))) / SR
    x = (ruido / (np.max(np.abs(ruido)) or 1) + 0.25 * np.sin(fase)) * (t / seg) ** 2.2
    x[-int(SR * 0.02):] *= np.linspace(1, 0, int(SR * 0.02))
    return _norm(x, db)


def pop(db: float = -15) -> np.ndarray:
    t = _t(0.12)
    x = np.sin(2 * np.pi * (900 * t - 2600 * t * t)) * _env(t.size, 0.002, 0.03)
    return _norm(x, db)


def acorde(db: float = -14) -> np.ndarray:
    t = _t(2.0)
    x = np.zeros_like(t)
    for f in (220.0, 277.18, 329.63, 440.0):  # La mayor, suave
        x += np.sin(2 * np.pi * f * t) + 0.3 * np.sin(4 * np.pi * f * t)
    return _norm(x * _env(t.size, 0.03, 0.7), db)


EFECTOS = {"whoosh": whoosh, "impacto": impacto, "tic": tic, "riser": riser, "pop": pop, "acorde": acorde}


def guardar(x: np.ndarray, ruta: Path) -> Path:
    datos = (np.clip(x, -1, 1) * 32767).astype("<i2")
    estereo = np.repeat(datos[:, None], 2, axis=1)
    with wave.open(str(ruta), "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(estereo.tobytes())
    return ruta


def generar(destino: Path) -> list[Path]:
    destino.mkdir(parents=True, exist_ok=True)
    return [guardar(f(), destino / f"{nombre}.wav") for nombre, f in EFECTOS.items()]
