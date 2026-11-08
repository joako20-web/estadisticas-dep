import type { PropsBase } from "../../base/tipos";
import type { FichaJugador } from "../mvp/tipos";

export type JugadorXV = {
  puesto: number;
  nombre: string;
  apellido: string;
  equipo: string;
  abr: string;
  escudo: string;
  posicion: string;
  mejor: boolean;
};

/** Las 6 filas del campo, en orden de aparición (datosdep/videos/xv.py: LINEAS). */
export type LineaXV = { titulo: string; jugadores: JugadorXV[] };

export type PropsXV = PropsBase & { lineas: LineaXV[]; mejor: FichaJugador | null };
