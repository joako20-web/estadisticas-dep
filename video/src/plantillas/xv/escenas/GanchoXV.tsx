import React from "react";
import { AbsoluteFill, interpolate, useCurrentFrame, useVideoConfig } from "remotion";
import { Chip, Escudo, Mascara, SEGURA, Sfx, useColores, useReel } from "../../../base/comun";
import { EASE_OUT, STAGGER, blurEntrada, entra, golpe } from "../../../base/movimiento";
import type { PropsXV } from "../tipos";

const POR_ESCUDO = 3;

// Gancho: "XV" gigante de golpe y los 15 escudos del equipo ideal saltando en rejilla.
export const GanchoXV: React.FC = () => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const c = useColores();
  const { lineas, corto, jornada, fuenteTitulo, fuenteTexto } = useReel<PropsXV>();
  const jugadores = lineas.flatMap((l) => l.jugadores).sort((a, b) => a.puesto - b.puesto);
  const linea = entra(frame, 12, 16);

  return (
    <AbsoluteFill>
      <Sfx nombre="impacto" en={2} />
      <Sfx nombre="whoosh" en={12} volumen={0.8} />
      <Sfx nombre="tic" en={20} volumen={0.5} />
      <Sfx nombre="tic" en={32} volumen={0.5} />
      <Sfx nombre="tic" en={44} volumen={0.5} />

      <AbsoluteFill
        style={{
          background: c.acento,
          opacity: interpolate(frame, [0, 6], [1, 0], { extrapolateRight: "clamp", easing: EASE_OUT }),
        }}
      />

      <div style={{ position: "absolute", left: SEGURA.x, top: SEGURA.arriba + 30 }}>
        <div
          style={{
            translate: `${interpolate(entra(frame, 0, 14), [0, 1], [-900, 0])}px 0px`,
            filter: `blur(${blurEntrada(frame, 0, 14)}px)`,
          }}
        >
          <Chip tam={50}>
            XV ideal · {corto} · J{jornada}
          </Chip>
        </div>
      </div>

      <div style={{ position: "absolute", left: SEGURA.x, right: SEGURA.x, top: 380, display: "flex", alignItems: "flex-end", gap: 34 }}>
        <div
          style={{
            fontFamily: fuenteTitulo,
            fontWeight: 700,
            fontSize: 440,
            lineHeight: 0.84,
            color: c.acento,
            letterSpacing: "-0.03em",
            scale: String(golpe(frame, fps, 2)),
            transformOrigin: "0% 80%",
            textShadow: "0 18px 60px rgba(0,0,0,.35)",
          }}
        >
          XV
        </div>
        <Mascara p={entra(frame, 8, 18)} style={{ paddingBottom: 6 }}>
          <div style={{ fontFamily: fuenteTitulo, fontWeight: 700, fontSize: 150, lineHeight: 0.9, color: c.texto, textTransform: "uppercase" }}>
            Ideal
          </div>
        </Mascara>
      </div>

      <div style={{ position: "absolute", left: SEGURA.x, right: SEGURA.x, top: 790 }}>
        <div style={{ height: 10, width: `${linea * 100}%`, background: c.texto }} />
        <Mascara p={entra(frame, 12 + STAGGER, 18)} style={{ marginTop: 26 }}>
          <div style={{ fontFamily: fuenteTexto, fontWeight: 700, fontSize: 54, lineHeight: 1.05, textTransform: "uppercase", letterSpacing: "0.03em", color: c.gris }}>
            Los 15 mejores de la jornada
          </div>
        </Mascara>
      </div>

      {/* rejilla 5×3 de escudos */}
      <div
        style={{
          position: "absolute",
          left: SEGURA.x,
          right: SEGURA.x,
          top: 1000,
          display: "grid",
          gridTemplateColumns: "repeat(5, 1fr)",
          rowGap: 26,
          justifyItems: "center",
        }}
      >
        {jugadores.map((j, i) => (
          <div key={j.puesto} style={{ scale: String(golpe(frame, fps, 14 + i * POR_ESCUDO)) }}>
            <Escudo src={j.escudo} lado={140} borde={j.mejor ? c.acento : undefined} />
          </div>
        ))}
      </div>
    </AbsoluteFill>
  );
};
