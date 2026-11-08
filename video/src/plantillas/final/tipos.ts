import type { Equipo, PropsBase } from "../../base/tipos";

export type Lado = "L" | "V";

export type EquipoFinal = Equipo & { ensayos: number };

/** Marcador tras cada anotación (en orden). */
export type Anotacion = { minuto: number; lado: Lado; tipo: string; local: number; visitante: number };

export type PropsFinal = PropsBase & {
  idPartido: number;
  ronda: string;
  cuando: string;
  local: EquipoFinal;
  visitante: EquipoFinal;
  etiqueta: string; // "Remontada", "En el último minuto"... ("" si no hay)
  frase: string;
  completa: boolean; // el acta cuadra con el resultado: hay evolución, ensayos y anotadores
  evolucion: Anotacion[];
  ensayos: { minuto: number; lado: Lado; jugador: string; castigo: boolean }[];
  anotadores: { nombre: string; apellidos: string; lado: Lado; puntos: number; detalle: string }[];
};

const EQ: EquipoFinal = { nombre: "Local", abr: "LOC", escudo: "", puntos: 0, gana: false, ensayos: 0 };

export const PROPS_FINAL_VACIAS = {
  idPartido: 0,
  ronda: "",
  cuando: "",
  local: EQ,
  visitante: { ...EQ, nombre: "Visitante", abr: "VIS" },
  etiqueta: "",
  frase: "",
  completa: false,
  evolucion: [],
  ensayos: [],
  anotadores: [],
};
