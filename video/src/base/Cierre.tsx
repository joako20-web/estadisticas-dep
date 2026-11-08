import React from "react";
import { AbsoluteFill, Img, interpolate, useCurrentFrame, useVideoConfig } from "remotion";
import { Chip, Mascara, SEGURA, Sfx, useColores, useReel } from "./comun";
import { EASE_IN, entra, golpe } from "./movimiento";

// Cierre: logo + llamada a seguir. Los últimos frames se funden en el destello de acento
// con el que empieza el vídeo, para que el bucle de vídeos no tenga salto.
export const Cierre: React.FC = () => {
  const frame = useCurrentFrame();
  const { fps, durationInFrames } = useVideoConfig();
  const c = useColores();
  const { logo, handle, fuenteTitulo, fuenteTexto, corto } = useReel();
  const destello = interpolate(frame, [durationInFrames - 9, durationInFrames - 1], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
    easing: EASE_IN,
  });

  return (
    <AbsoluteFill>
      <Sfx nombre="acorde" en={4} />
      <Sfx nombre="riser" en={durationInFrames - 30} />

      <div
        style={{
          position: "absolute",
          left: 0,
          right: 0,
          top: 470,
          display: "flex",
          flexDirection: "column",
          alignItems: "center",
        }}
      >
        <div
          style={{
            width: 420,
            height: 420,
            borderRadius: "50%",
            background: "#fff",
            boxShadow: `0 0 0 10px ${c.acento}, 0 30px 90px rgba(0,0,0,.45)`,
            overflow: "hidden",
            scale: String(golpe(frame, fps, 2)),
            rotate: `${interpolate(entra(frame, 2, 24), [0, 1], [-14, 0])}deg`,
          }}
        >
          <Img src={logo} style={{ width: "100%", height: "100%", objectFit: "cover" }} />
        </div>
        <Mascara p={entra(frame, 14, 18)} style={{ marginTop: 70 }}>
          <div
            style={{
              fontFamily: fuenteTitulo,
              fontWeight: 700,
              fontSize: 92,
              lineHeight: 1,
              textTransform: "uppercase",
              color: c.texto,
              textAlign: "center",
            }}
          >
            Cada jornada
          </div>
        </Mascara>
        <Mascara p={entra(frame, 18, 18)}>
          <div
            style={{
              fontFamily: fuenteTexto,
              fontWeight: 700,
              fontSize: 48,
              textTransform: "uppercase",
              letterSpacing: "0.05em",
              color: c.gris,
              textAlign: "center",
              marginTop: 10,
            }}
          >
            de {corto}, aquí
          </div>
        </Mascara>
        <div style={{ marginTop: 50, scale: String(golpe(frame, fps, 24)) }}>
          <Chip tam={64} style={{ paddingLeft: 40, paddingRight: 80 }}>
            {handle}
          </Chip>
        </div>
      </div>

      <div
        style={{
          position: "absolute",
          left: SEGURA.x,
          right: SEGURA.x,
          bottom: SEGURA.abajo - 40,
          textAlign: "center",
          fontFamily: fuenteTexto,
          fontWeight: 700,
          fontSize: 44,
          color: c.apagado,
          opacity: entra(frame, 30, 16),
          textTransform: "uppercase",
          letterSpacing: "0.08em",
        }}
      >
        Síguenos ➜
      </div>

      <AbsoluteFill style={{ background: c.acento, opacity: destello }} />
    </AbsoluteFill>
  );
};
