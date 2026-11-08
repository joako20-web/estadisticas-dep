import React from "react";
import { TransitionSeries, springTiming } from "@remotion/transitions";
import { slide } from "@remotion/transitions/slide";
import { wipe } from "@remotion/transitions/wipe";
import { useVideoConfig } from "remotion";
import { Cierre } from "../../base/Cierre";
import { Marco } from "../../base/comun";
import { Agenda } from "./escenas/Agenda";
import { CaraACara } from "./escenas/CaraACara";
import { Partidos, porPartido } from "./escenas/Partidos";
import type { PropsPrevia } from "./tipos";

// Guion (30 fps, 12-22 s): cara a cara del partido destacado -> cada partido con
// día, hora y campo -> la jornada completa -> cierre en bucle.
export const DURACIONES = { gancho: 96, agenda: 105, cierre: 76, transicion: 10 };

export const duracionReel = (partidos: number) =>
  DURACIONES.gancho + partidos * porPartido(partidos) + DURACIONES.agenda + DURACIONES.cierre - 3 * DURACIONES.transicion;

const empuje = () => springTiming({ config: { damping: 200 }, durationInFrames: DURACIONES.transicion });

export const ReelPrevia: React.FC<PropsPrevia> = (props) => {
  const { fps } = useVideoConfig();
  const n = props.partidos.length;
  return (
    <Marco props={props}>
      <TransitionSeries name="Reel">
        <TransitionSeries.Sequence name="Cara a cara" durationInFrames={DURACIONES.gancho} premountFor={fps}>
          <CaraACara />
        </TransitionSeries.Sequence>
        <TransitionSeries.Transition presentation={slide({ direction: "from-bottom" })} timing={empuje()} />
        <TransitionSeries.Sequence name="Partidos" durationInFrames={Math.max(1, n * porPartido(n))} premountFor={fps}>
          <Partidos />
        </TransitionSeries.Sequence>
        <TransitionSeries.Transition presentation={wipe({ direction: "from-left" })} timing={empuje()} />
        <TransitionSeries.Sequence name="Agenda" durationInFrames={DURACIONES.agenda} premountFor={fps}>
          <Agenda />
        </TransitionSeries.Sequence>
        <TransitionSeries.Transition presentation={slide({ direction: "from-bottom" })} timing={empuje()} />
        <TransitionSeries.Sequence name="Cierre" durationInFrames={DURACIONES.cierre} premountFor={fps}>
          <Cierre />
        </TransitionSeries.Sequence>
      </TransitionSeries>
    </Marco>
  );
};
