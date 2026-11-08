import React from "react";
import { TransitionSeries, springTiming } from "@remotion/transitions";
import { slide } from "@remotion/transitions/slide";
import { wipe } from "@remotion/transitions/wipe";
import { useVideoConfig } from "remotion";
import { Cierre } from "../../base/Cierre";
import { Marco } from "../../base/comun";
import { Bloque, duracionBloque } from "./escenas/Bloque";
import { Gancho } from "./escenas/Gancho";
import type { PropsRankings } from "./tipos";

// Guion (30 fps, 10-15 s): cifra del líder (gancho) -> un bloque por ranking -> cierre en bucle.
export const DURACIONES = { gancho: 60, cierre: 76, transicion: 10 };

export const duracionRankings = (bloques: number) =>
  DURACIONES.gancho + bloques * duracionBloque(bloques) + DURACIONES.cierre - (bloques + 1) * DURACIONES.transicion;

const empuje = () => springTiming({ config: { damping: 200 }, durationInFrames: DURACIONES.transicion });

export const ReelRankings: React.FC<PropsRankings> = (props) => {
  const { fps } = useVideoConfig();
  return (
    <Marco props={props}>
      <TransitionSeries name="Reel">
        <TransitionSeries.Sequence name="Gancho" durationInFrames={DURACIONES.gancho} premountFor={fps}>
          <Gancho />
        </TransitionSeries.Sequence>
        {props.bloques.flatMap((b, i) => [
          i === 0 ? (
            <TransitionSeries.Transition key={`t${b.clave}`} presentation={slide({ direction: "from-bottom" })} timing={empuje()} />
          ) : (
            <TransitionSeries.Transition key={`t${b.clave}`} presentation={wipe({ direction: "from-left" })} timing={empuje()} />
          ),
          <TransitionSeries.Sequence key={b.clave} name={b.titulo} durationInFrames={duracionBloque(props.bloques.length)} premountFor={fps}>
            <Bloque bloque={b} />
          </TransitionSeries.Sequence>,
        ])}
        <TransitionSeries.Transition presentation={slide({ direction: "from-bottom" })} timing={empuje()} />
        <TransitionSeries.Sequence name="Cierre" durationInFrames={DURACIONES.cierre} premountFor={fps}>
          <Cierre />
        </TransitionSeries.Sequence>
      </TransitionSeries>
    </Marco>
  );
};
