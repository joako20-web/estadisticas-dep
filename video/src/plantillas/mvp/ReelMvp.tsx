import React from "react";
import { TransitionSeries, springTiming } from "@remotion/transitions";
import { slide } from "@remotion/transitions/slide";
import { wipe } from "@remotion/transitions/wipe";
import { useVideoConfig } from "remotion";
import { Cierre } from "../../base/Cierre";
import { Marco } from "../../base/comun";
import { Estadisticas } from "./escenas/Estadisticas";
import { GanchoMvp } from "./escenas/GanchoMvp";
import { Presentacion } from "./escenas/Presentacion";
import type { PropsMvp } from "./tipos";

// Guion (30 fps, ~13 s): gancho "MVP" -> quién es (foto o escudo) -> sus números -> cierre en bucle.
export const DURACIONES = { gancho: 62, presentacion: 112, numeros: 168, cierre: 76, transicion: 10 };

export const duracionMvp = () =>
  DURACIONES.gancho + DURACIONES.presentacion + DURACIONES.numeros + DURACIONES.cierre - 3 * DURACIONES.transicion;

const empuje = () => springTiming({ config: { damping: 200 }, durationInFrames: DURACIONES.transicion });

export const ReelMvp: React.FC<PropsMvp> = (props) => {
  const { fps } = useVideoConfig();
  const j = props.jugador;
  return (
    <Marco props={props}>
      <TransitionSeries name="Reel">
        <TransitionSeries.Sequence name="Gancho" durationInFrames={DURACIONES.gancho} premountFor={fps}>
          <GanchoMvp />
        </TransitionSeries.Sequence>
        <TransitionSeries.Transition presentation={slide({ direction: "from-bottom" })} timing={empuje()} />
        <TransitionSeries.Sequence name="Presentación" durationInFrames={DURACIONES.presentacion} premountFor={fps}>
          {j ? <Presentacion j={j} chip="★ Jugador de la jornada" /> : null}
        </TransitionSeries.Sequence>
        <TransitionSeries.Transition presentation={wipe({ direction: "from-left" })} timing={empuje()} />
        <TransitionSeries.Sequence name="Números" durationInFrames={DURACIONES.numeros} premountFor={fps}>
          <Estadisticas />
        </TransitionSeries.Sequence>
        <TransitionSeries.Transition presentation={slide({ direction: "from-bottom" })} timing={empuje()} />
        <TransitionSeries.Sequence name="Cierre" durationInFrames={DURACIONES.cierre} premountFor={fps}>
          <Cierre />
        </TransitionSeries.Sequence>
      </TransitionSeries>
    </Marco>
  );
};
