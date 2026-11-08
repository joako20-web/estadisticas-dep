import React from "react";
import { TransitionSeries, springTiming } from "@remotion/transitions";
import { slide } from "@remotion/transitions/slide";
import { useVideoConfig } from "remotion";
import { Cierre } from "../../base/Cierre";
import { Marco } from "../../base/comun";
import { Lider } from "./escenas/Lider";
import { Tabla, planTabla } from "./escenas/Tabla";
import type { PropsClasificacion } from "./tipos";

// Guion (30 fps, ~11-16 s): líder (gancho) -> tabla completa con zonas y flechas -> cierre en bucle.
export const DURACIONES = { lider: 72, cierre: 76, transicion: 10 };

export const duracionClasificacion = (filas: number, leyenda: number) =>
  DURACIONES.lider + planTabla(filas, leyenda).total + DURACIONES.cierre - 2 * DURACIONES.transicion;

const empuje = () => springTiming({ config: { damping: 200 }, durationInFrames: DURACIONES.transicion });

export const ReelClasificacion: React.FC<PropsClasificacion> = (props) => {
  const { fps } = useVideoConfig();
  return (
    <Marco props={props}>
      <TransitionSeries name="Reel">
        <TransitionSeries.Sequence name="Líder" durationInFrames={DURACIONES.lider} premountFor={fps}>
          <Lider />
        </TransitionSeries.Sequence>
        <TransitionSeries.Transition presentation={slide({ direction: "from-bottom" })} timing={empuje()} />
        <TransitionSeries.Sequence
          name="Tabla"
          durationInFrames={planTabla(props.filas.length, props.leyenda.length).total}
          premountFor={fps}
        >
          <Tabla />
        </TransitionSeries.Sequence>
        <TransitionSeries.Transition presentation={slide({ direction: "from-bottom" })} timing={empuje()} />
        <TransitionSeries.Sequence name="Cierre" durationInFrames={DURACIONES.cierre} premountFor={fps}>
          <Cierre />
        </TransitionSeries.Sequence>
      </TransitionSeries>
    </Marco>
  );
};
