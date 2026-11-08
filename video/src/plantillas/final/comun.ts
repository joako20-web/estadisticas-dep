import { useColores, useReel } from "../../base/comun";
import type { EquipoFinal, Lado, PropsFinal } from "./tipos";

/** Equipo y color de cada lado: el ganador en el acento, el otro en blanco (empate: los dos blancos). */
export const useLados = () => {
  const c = useColores();
  const { local, visitante } = useReel<PropsFinal>();
  const color = (eq: EquipoFinal) => (eq.gana ? c.acento : c.texto);
  return {
    L: { eq: local, color: color(local) },
    V: { eq: visitante, color: color(visitante) },
  } as Record<Lado, { eq: EquipoFinal; color: string }>;
};

/** Último minuto del eje (80' o la prórroga si la hubo). */
export const minutoFinal = (p: PropsFinal) => Math.max(80, ...p.evolucion.map((a) => a.minuto));
