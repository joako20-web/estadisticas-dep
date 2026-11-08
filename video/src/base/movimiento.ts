// Curvas y tiempos de animación comunes (30 fps).
// Reglas: nunca lineal; entradas ease-out de 15-25 f, salidas ease-in de 8-12 f,
// escalonado de 3-5 f entre elementos hermanos.
import { Easing, interpolate, spring } from "remotion";

export const EASE_OUT = Easing.bezier(0.16, 1, 0.3, 1);
export const EASE_IN = Easing.bezier(0.7, 0, 0.84, 0);
export const EASE_IN_OUT = Easing.bezier(0.65, 0, 0.35, 1);
export const STAGGER = 4;

const clamp = { extrapolateLeft: "clamp", extrapolateRight: "clamp" } as const;

/** 0 -> 1 con ease-out empezando en `desde`. */
export const entra = (frame: number, desde: number, dur = 18) =>
  interpolate(frame, [desde, desde + dur], [0, 1], { ...clamp, easing: EASE_OUT });

/** 0 -> 1 con ease-in (para salidas). */
export const sale = (frame: number, desde: number, dur = 10) =>
  interpolate(frame, [desde, desde + dur], [0, 1], { ...clamp, easing: EASE_IN });

/** Muelle con algo de rebote (damping bajo = más rebote). */
export const muelle = (frame: number, fps: number, desde: number, damping = 12, stiffness = 170) =>
  spring({ frame: frame - desde, fps, config: { damping, stiffness, mass: 0.9 } });

/** Golpe de entrada con anticipación: se encoge 3 f y salta con rebote (~8 %). */
export const golpe = (frame: number, fps: number, desde: number) => {
  if (frame < desde) return 0;
  if (frame < desde + 3) return interpolate(frame, [desde, desde + 3], [1.12, 0.96], { ...clamp, easing: EASE_IN });
  return 0.96 + 0.04 * muelle(frame, fps, desde + 3, 9, 220);
};

/** Contador que sube hasta `valor` (efecto marcador). */
export const cuenta = (frame: number, desde: number, valor: number, dur = 18) =>
  Math.round(interpolate(frame, [desde, desde + dur], [0, valor], { ...clamp, easing: Easing.bezier(0.25, 1, 0.5, 1) }));

/** Desenfoque proporcional a la velocidad de una entrada (motion blur barato). */
export const blurEntrada = (frame: number, desde: number, dur = 10, max = 14) =>
  interpolate(frame, [desde, desde + dur * 0.35, desde + dur], [max, max * 0.5, 0], clamp);
