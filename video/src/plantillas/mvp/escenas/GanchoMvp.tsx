import React from "react";
import { AbsoluteFill, interpolate, useCurrentFrame, useVideoConfig } from "remotion";
import { Chip, Escudo, Mascara, SEGURA, Sfx, useColores, useReel } from "../../../base/comun";
import { EASE_OUT, STAGGER, blurEntrada, entra, golpe } from "../../../base/movimiento";
import type { PropsMvp } from "../tipos";

// Gancho: "MVP" enorme de golpe, el escudo del equipo y la pregunta. El nombre se guarda para después.
export const GanchoMvp: React.FC = () => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const c = useColores();
  const { jugador, corto, jornada, fuenteTitulo, fuenteTexto } = useReel<PropsMvp>();
  if (!jugador) return null;
  const linea = entra(frame, 14, 16);

  return (
    <AbsoluteFill>
      <Sfx nombre="impacto" en={2} />
      <Sfx nombre="whoosh" en={16} volumen={0.8} />
      <Sfx nombre="pop" en={26} volumen={0.7} />

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
            {corto} · Jornada {jornada}
          </Chip>
        </div>
      </div>

      <div style={{ position: "absolute", left: SEGURA.x, right: SEGURA.x, top: 400 }}>
        <div
          style={{
            fontFamily: fuenteTitulo,
            fontWeight: 700,
            fontSize: 470,
            lineHeight: 0.86,
            color: c.acento,
            letterSpacing: "-0.02em",
            scale: String(golpe(frame, fps, 2)),
            transformOrigin: "0% 80%",
            textShadow: "0 18px 60px rgba(0,0,0,.35)",
          }}
        >
          MVP
        </div>
        <div style={{ height: 10, width: `${linea * 100}%`, background: c.texto, marginTop: 30 }} />
        <Mascara p={entra(frame, 12 + STAGGER, 18)} style={{ marginTop: 28 }}>
          <div
            style={{
              fontFamily: fuenteTitulo,
              fontWeight: 700,
              fontSize: 104,
              lineHeight: 0.95,
              textTransform: "uppercase",
              color: c.texto,
            }}
          >
            Jugador de
            <br />
            la jornada
          </div>
        </Mascara>
      </div>

      <div
        style={{
          position: "absolute",
          left: SEGURA.x,
          right: SEGURA.x,
          top: 1230,
          display: "flex",
          alignItems: "center",
          gap: 36,
        }}
      >
        <div style={{ scale: String(golpe(frame, fps, 24)), rotate: `${interpolate(entra(frame, 24, 20), [0, 1], [-30, 0])}deg` }}>
          <Escudo src={jugador.escudo} lado={190} borde={c.acento} />
        </div>
        <Mascara p={entra(frame, 28, 18)} style={{ flex: 1 }}>
          <div
            style={{
              fontFamily: fuenteTexto,
              fontWeight: 700,
              fontSize: 54,
              lineHeight: 1.05,
              textTransform: "uppercase",
              letterSpacing: "0.03em",
              color: c.gris,
            }}
          >
            ¿Quién ha sido
            <br />
            el mejor?
          </div>
        </Mascara>
      </div>
    </AbsoluteFill>
  );
};
