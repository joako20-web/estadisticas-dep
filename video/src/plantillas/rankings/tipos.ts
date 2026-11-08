import type { PropsBase } from "../../base/tipos";

export type FilaRanking = {
  pos: number;
  nombre: string;
  apellidos: string;
  /** apellidos recortados (si no caben enteros) */
  corto: string;
  equipo: string;
  escudo: string;
  valor: number;
  detalle: string;
};

export type Bloque = {
  clave: "anotadores" | "ensayadores" | "pateadores" | string;
  titulo: string;
  unidad: string;
  filas: FilaRanking[];
};

export type PropsRankings = PropsBase & {
  bloques: Bloque[];
  trasJornada: number;
};
