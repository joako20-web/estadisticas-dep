import React from "react";
import { TransitionSeries, springTiming } from "@remotion/transitions";
import { slide } from "@remotion/transitions/slide";
import { wipe } from "@remotion/transitions/wipe";
import { useVideoConfig } from "remotion";
import { Cierre } from "../../base/Cierre";
import { Marco } from "../../base/comun";
import { Campo, duracionCampo } from "./escenas/Campo";
import { GanchoXV } from "./escenas/GanchoXV";
import { Mejor } from "./escenas/Mejor";
import type { PropsXV } from "./tipos";

// Guion (30 fps, ~17 s): gancho "XV" con los 15 escudos -> campo con las 6 filas -> el mejor -> cierre en bucle.
export const DURACIONES = { gancho: 72, mejor: 110, cierre: 76, transicion: 10 };

export const duracionXV = (filas: number) =>
  DURACIONES.gancho + duracionCampo(filas) + DURACIONES.mejor + DURACIONES.cierre - 3 * DURACIONES.transicion;

const empuje = () => springTiming({ config: { damping: 200 }, durationInFrames: DURACIONES.transicion });

export const ReelXV: React.FC<PropsXV> = (props) => {
  const { fps } = useVideoConfig();
  return (
    <Marco props={props}>
      <TransitionSeries name="Reel">
        <TransitionSeries.Sequence name="Gancho" durationInFrames={DURACIONES.gancho} premountFor={fps}>
          <GanchoXV />
        </TransitionSeries.Sequence>
        <TransitionSeries.Transition presentation={slide({ direction: "from-bottom" })} timing={empuje()} />
        <TransitionSeries.Sequence name="Campo" durationInFrames={duracionCampo(props.lineas.length || 6)} premountFor={fps}>
          <Campo />
        </TransitionSeries.Sequence>
        <TransitionSeries.Transition presentation={wipe({ direction: "from-left" })} timing={empuje()} />
        <TransitionSeries.Sequence name="El mejor" durationInFrames={DURACIONES.mejor} premountFor={fps}>
          <Mejor />
        </TransitionSeries.Sequence>
        <TransitionSeries.Transition presentation={slide({ direction: "from-bottom" })} timing={empuje()} />
        <TransitionSeries.Sequence name="Cierre" durationInFrames={DURACIONES.cierre} premountFor={fps}>
          <Cierre />
        </TransitionSeries.Sequence>
      </TransitionSeries>
    </Marco>
  );
};
