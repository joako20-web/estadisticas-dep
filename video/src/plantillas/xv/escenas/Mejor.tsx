import React from "react";
import { useCurrentFrame } from "remotion";
import { useColores, useReel } from "../../../base/comun";
import { STAGGER, cuenta, entra } from "../../../base/movimiento";
import { Presentacion } from "../../mvp/escenas/Presentacion";
import type { PropsXV } from "../tipos";

const DATOS = 40;

/** Puntos y desglose bajo el dorsal (columna derecha). */
const Datos: React.FC = () => {
  const frame = useCurrentFrame();
  const c = useColores();
  const { mejor: j, fuenteTitulo, fuenteTexto } = useReel<PropsXV>();
  if (!j) return null;
  const anota = j.puntos > 0;
  const lineas = j.stats.filter((s) => s.valor > 0);
  const p = entra(frame, DATOS, 16);
  return (
    <div style={{ opacity: p, translate: `${(1 - p) * 120}px 0px` }}>
      <div style={{ fontFamily: fuenteTitulo, fontWeight: 700, fontSize: 150, lineHeight: 0.9, color: c.acento }}>
        {anota ? cuenta(frame, DATOS, j.puntos, 16) : j.nota.toFixed(1)}
        <span style={{ fontSize: 56, marginLeft: 10 }}>{anota ? "PTS" : "NOTA"}</span>
      </div>
      {lineas.map((s, i) => {
        const q = entra(frame, DATOS + 8 + i * STAGGER, 14);
        return (
          <div
            key={s.clave}
            style={{ fontFamily: fuenteTexto, fontWeight: 700, fontSize: 44, color: c.texto, textTransform: "uppercase", opacity: q, translate: `${(1 - q) * 60}px 0px` }}
          >
            {s.valor} {s.texto}
          </div>
        );
      })}
    </div>
  );
};

// El mejor del XV: misma presentación que el reel del jugador de la jornada, sin foto y con sus puntos.
export const Mejor: React.FC = () => {
  const { mejor } = useReel<PropsXV>();
  if (!mejor) return null;
  return <Presentacion j={{ ...mejor, foto: "" }} chip="★ El mejor del XV" apellido={mejor.corto} extra={<Datos />} />;
};
