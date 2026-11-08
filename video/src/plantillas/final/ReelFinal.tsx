import React from "react";
import { TransitionSeries, springTiming } from "@remotion/transitions";
import { slide } from "@remotion/transitions/slide";
import { wipe } from "@remotion/transitions/wipe";
import { useVideoConfig } from "remotion";
import { Cierre } from "../../base/Cierre";
import { Marco } from "../../base/comun";
import { Anotadores, DUR_ANOTADORES } from "./escenas/Anotadores";
import { DUR_ENSAYOS, Ensayos } from "./escenas/Ensayos";
import { DUR_EVOLUCION, Evolucion } from "./escenas/Evolucion";
import { Gancho } from "./escenas/Gancho";
import type { PropsFinal } from "./tipos";

// Guion (30 fps, ~17 s): marcador con el relato -> así fue (diferencia minuto a minuto)
// -> los ensayos en su minuto -> anotadores -> cierre en bucle.
// Si el acta no cuadra con el resultado solo queda el marcador (más largo) y el cierre.
const TRANSICION = 10;
const CIERRE = 76;

type Escena = { nombre: string; dur: number; el: React.ReactNode; entrada: "abajo" | "derecha" | "barrido" };

const escenas = (p: PropsFinal): Escena[] => {
  const out: Escena[] = [{ nombre: "Gancho", dur: p.completa ? 96 : 126, el: <Gancho />, entrada: "abajo" }];
  if (p.completa && p.evolucion.length) out.push({ nombre: "Así fue", dur: DUR_EVOLUCION, el: <Evolucion />, entrada: "abajo" });
  if (p.completa && p.ensayos.length) out.push({ nombre: "Ensayos", dur: DUR_ENSAYOS, el: <Ensayos />, entrada: "derecha" });
  if (p.completa && p.anotadores.length) out.push({ nombre: "Anotadores", dur: DUR_ANOTADORES, el: <Anotadores />, entrada: "barrido" });
  out.push({ nombre: "Cierre", dur: CIERRE, el: <Cierre />, entrada: "abajo" });
  return out;
};

export const duracionFinal = (p: PropsFinal) => {
  const e = escenas(p);
  return e.reduce((s, x) => s + x.dur, 0) - (e.length - 1) * TRANSICION;
};

const empuje = () => springTiming({ config: { damping: 200 }, durationInFrames: TRANSICION });
const transicion = (e: Escena["entrada"], key: string) =>
  e === "barrido" ? (
    <TransitionSeries.Transition key={key} presentation={wipe({ direction: "from-left" })} timing={empuje()} />
  ) : (
    <TransitionSeries.Transition
      key={key}
      presentation={slide({ direction: e === "derecha" ? "from-right" : "from-bottom" })}
      timing={empuje()}
    />
  );

export const ReelFinal: React.FC<PropsFinal> = (props) => {
  const { fps } = useVideoConfig();
  return (
    <Marco props={props}>
      <TransitionSeries name="Reel">
        {escenas(props).flatMap((e, i) => [
          ...(i ? [transicion(e.entrada, `t${i}`)] : []),
          <TransitionSeries.Sequence key={e.nombre} name={e.nombre} durationInFrames={e.dur} premountFor={fps}>
            {e.el}
          </TransitionSeries.Sequence>,
        ])}
      </TransitionSeries>
    </Marco>
  );
};
