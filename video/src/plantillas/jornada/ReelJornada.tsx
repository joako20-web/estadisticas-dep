import React from "react";
import { TransitionSeries, springTiming } from "@remotion/transitions";
import { slide } from "@remotion/transitions/slide";
import { wipe } from "@remotion/transitions/wipe";
import { useVideoConfig } from "remotion";
import { Cierre } from "../../base/Cierre";
import { Marco } from "../../base/comun";
import { Clasificacion } from "./escenas/Clasificacion";
import { Gancho } from "./escenas/Gancho";
import { Mvp } from "./escenas/Mvp";
import { POR_PARTIDO, Resultados } from "./escenas/Resultados";
import type { PropsJornada } from "./tipos";

// Guion (30 fps, ~20 s): gancho -> 5 resultados -> jugador de la jornada -> top 4 -> cierre en bucle.
export const DURACIONES = { gancho: 66, mvp: 96, top: 102, cierre: 76, transicion: 10 };

export const duracionReel = (partidos: number) =>
  DURACIONES.gancho + partidos * POR_PARTIDO + DURACIONES.mvp + DURACIONES.top + DURACIONES.cierre - 4 * DURACIONES.transicion;

const empuje = () => springTiming({ config: { damping: 200 }, durationInFrames: DURACIONES.transicion });

export const ReelJornada: React.FC<PropsJornada> = (props) => {
  const { fps } = useVideoConfig();
  return (
    <Marco props={props}>
        <TransitionSeries name="Reel">
          <TransitionSeries.Sequence name="Gancho" durationInFrames={DURACIONES.gancho} premountFor={fps}>
            <Gancho />
          </TransitionSeries.Sequence>
          <TransitionSeries.Transition presentation={slide({ direction: "from-bottom" })} timing={empuje()} />
          <TransitionSeries.Sequence name="Resultados" durationInFrames={props.partidos.length * POR_PARTIDO} premountFor={fps}>
            <Resultados />
          </TransitionSeries.Sequence>
          <TransitionSeries.Transition presentation={slide({ direction: "from-right" })} timing={empuje()} />
          <TransitionSeries.Sequence name="Jugador de la jornada" durationInFrames={DURACIONES.mvp} premountFor={fps}>
            <Mvp />
          </TransitionSeries.Sequence>
          <TransitionSeries.Transition presentation={wipe({ direction: "from-left" })} timing={empuje()} />
          <TransitionSeries.Sequence name="Clasificación" durationInFrames={DURACIONES.top} premountFor={fps}>
            <Clasificacion />
          </TransitionSeries.Sequence>
          <TransitionSeries.Transition presentation={slide({ direction: "from-bottom" })} timing={empuje()} />
          <TransitionSeries.Sequence name="Cierre" durationInFrames={DURACIONES.cierre} premountFor={fps}>
            <Cierre />
          </TransitionSeries.Sequence>
        </TransitionSeries>
    </Marco>
  );
};
