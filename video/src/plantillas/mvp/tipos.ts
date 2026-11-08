import type { PropsBase } from "../../base/tipos";

/** Jugador destacado (lo genera datosdep/videos/mvp.py: ficha()). */
export type FichaJugador = {
  nombre: string;
  apellidos: string;
  corto: string;
  completo: string;
  equipo: string;
  abr: string;
  escudo: string;
  posicion: string;
  dorsal: number | null;
  puesto: number | null;
  puntos: number;
  nota: number;
  stats: { clave: string; valor: number; texto: string }[];
  partido: {
    rival: string;
    escudoRival: string;
    propios: number | null;
    contra: number | null;
    letra: string;
    texto: string;
  } | null;
  /** data URI 720×900 (solo si la foto tiene calidad) o "" */
  foto: string;
  motivo: string;
};

export type PropsMvp = PropsBase & { jugador: FichaJugador | null };

export const JUGADOR_VACIO: FichaJugador = {
  nombre: "Nombre",
  apellidos: "Apellido",
  corto: "Apellido",
  completo: "Nombre Apellido",
  equipo: "Equipo",
  abr: "EQU",
  escudo: "",
  posicion: "Apertura",
  dorsal: 10,
  puesto: 10,
  puntos: 0,
  nota: 0,
  stats: [],
  partido: null,
  foto: "",
  motivo: "",
};
