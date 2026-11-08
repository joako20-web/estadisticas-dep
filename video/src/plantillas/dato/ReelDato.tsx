import React from "react";
import { TransitionSeries, springTiming } from "@remotion/transitions";
import { slide } from "@remotion/transitions/slide";
import { useVideoConfig } from "remotion";
import { Cierre } from "../../base/Cierre";
import { Marco } from "../../base/comun";
import { DURACION_DATO, Dato } from "./escenas/Dato";
import type { PropsDato } from "./tipos";

// Guion (30 fps, ~9,5 s): el dato (número gigante en el primer segundo) -> cierre en bucle.
export const DURACIONES = { dato: DURACION_DATO, cierre: 76, transicion: 10 };
export const DURACION_REEL_DATO = DURACIONES.dato + DURACIONES.cierre - DURACIONES.transicion;

const empuje = () => springTiming({ config: { damping: 200 }, durationInFrames: DURACIONES.transicion });

export const ReelDato: React.FC<PropsDato> = (props) => {
  const { fps } = useVideoConfig();
  return (
    <Marco props={props}>
      <TransitionSeries name="Reel">
        <TransitionSeries.Sequence name="Dato" durationInFrames={DURACIONES.dato} premountFor={fps}>
          <Dato />
        </TransitionSeries.Sequence>
        <TransitionSeries.Transition presentation={slide({ direction: "from-bottom" })} timing={empuje()} />
        <TransitionSeries.Sequence name="Cierre" durationInFrames={DURACIONES.cierre} premountFor={fps}>
          <Cierre />
        </TransitionSeries.Sequence>
      </TransitionSeries>
    </Marco>
  );
};
