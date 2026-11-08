import type { PropsBase } from "../../base/tipos";

export type FilaTabla = {
  pos: number;
  nombre: string;
  abr: string;
  escudo: string;
  pj: number;
  pg: number;
  pe: number;
  pp: number;
  pt: number;
  dif: number;
  /** color de la franja de zona ("" si no tiene) */
  zona: string;
  /** puestos ganados (+) o perdidos (-) respecto a la jornada anterior; null sin datos */
  mov: number | null;
};

export type PropsClasificacion = PropsBase & {
  filas: FilaTabla[];
  leyenda: { color: string; texto: string }[];
  trasJornada: number;
  /** puntos de ventaja del líder sobre el segundo */
  ventaja: number;
};
