import type { Equipo, PropsBase } from "../../base/tipos";

/** Día de la semana, hora y fecha cortos ("SÁB", "16:00", "10 OCT"); vacíos si no hay. */
export type Cuando = { dia: string; hora: string; fecha: string };

export type Lado = Equipo & { pos: number | null; pt: number | null };

export type PartidoPrevia = Cuando & {
  local: Equipo;
  visitante: Equipo;
  campo: string;
  destacado: boolean;
};

export type PropsPrevia = PropsBase & {
  destacado: (Cuando & { local: Lado; visitante: Lado; campo: string }) | null;
  partidos: PartidoPrevia[];
  total: number;
  equiposTabla: number;
};

/** "SÁB 10 OCT" / "Fecha por confirmar". */
export const textoDia = (c: Cuando) => (c.dia ? `${c.dia} ${c.fecha}` : "Fecha por confirmar");
