import type { PropsBase } from "../../base/tipos";

export type PropsDato = PropsBase & {
  dato: {
    /** texto completo del número ("73'", "13"...) */
    numero: string;
    /** partes para el contador: antes + valor + despues; valor null si no hay que contar */
    antes: string;
    valor: number | null;
    despues: string;
    unidad: string;
    titular: string;
    contexto: string;
    equipo: string;
    escudo: string;
  };
  /** cuántos datos tenía la jornada */
  total: number;
};
