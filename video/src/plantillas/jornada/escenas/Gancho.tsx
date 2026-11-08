import React from "react";
import type { PropsJornada } from "../tipos";
import { AbsoluteFill, interpolate, useCurrentFrame, useVideoConfig } from "remotion";
import { Chip, Escudo, Mascara, SEGURA, Sfx, useColores, useReel } from "../../../base/comun";
import { EASE_OUT, STAGGER, blurEntrada, cuenta, entra, golpe } from "../../../base/movimiento";

// Gancho (primer segundo): el dato más fuerte de la jornada, antes que el contexto.
export const Gancho: React.FC = () => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const c = useColores();
  const { gancho, corto, jornada, fuenteTitulo, fuenteTexto } = useReel<PropsJornada>();
  if (!gancho) return null;

  const numerico = /^\d+$/.test(gancho.numero);
  const valor = numerico ? cuenta(frame, 4, Number(gancho.numero), 14) : gancho.numero;
  const escalaNum = golpe(frame, fps, 2);
  const linea = entra(frame, 18, 16);

  return (
    <AbsoluteFill>
      <Sfx nombre="impacto" en={2} />
      <Sfx nombre="tic" en={8} />
      <Sfx nombre="tic" en={12} />
      <Sfx nombre="whoosh" en={20} volumen={0.8} />

      {/* Destello de acento al arrancar (enlaza con el final para el bucle) */}
      <AbsoluteFill
        style={{
          background: c.acento,
          opacity: interpolate(frame, [0, 6], [1, 0], { extrapolateRight: "clamp", easing: EASE_OUT }),
        }}
      />

      <div style={{ position: "absolute", left: SEGURA.x, right: SEGURA.x, top: SEGURA.arriba + 30 }}>
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

      <div
        style={{
          position: "absolute",
          left: SEGURA.x,
          right: SEGURA.x,
          top: 420,
          display: "flex",
          flexDirection: "column",
        }}
      >
        <div
          style={{
            fontFamily: fuenteTitulo,
            fontWeight: 700,
            fontSize: 520,
            lineHeight: 0.9,
            color: c.acento,
            letterSpacing: "-0.02em",
            scale: String(escalaNum),
            transformOrigin: "0% 80%",
            textShadow: "0 18px 60px rgba(0,0,0,.35)",
          }}
        >
          {valor}
        </div>
        <div
          style={{
            height: 10,
            width: `${linea * 100}%`,
            background: c.texto,
            marginTop: 24,
          }}
        />
        <Mascara p={entra(frame, 16 + STAGGER, 18)} style={{ marginTop: 26 }}>
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
            {gancho.unidad}
          </div>
        </Mascara>
      </div>

      <div
        style={{
          position: "absolute",
          left: SEGURA.x,
          right: SEGURA.x,
          top: 1190,
          display: "flex",
          alignItems: "center",
          gap: 36,
        }}
      >
        {gancho.escudo ? (
          <div style={{ scale: String(golpe(frame, fps, 24)) }}>
            <Escudo src={gancho.escudo} lado={190} borde={c.acento} />
          </div>
        ) : null}
        <Mascara p={entra(frame, 26, 18)} style={{ flex: 1 }}>
          <div
            style={{
              fontFamily: fuenteTitulo,
              fontWeight: 700,
              fontSize: gancho.titular.length > 26 ? 76 : 96,
              lineHeight: 0.98,
              textTransform: "uppercase",
              color: c.texto,
            }}
          >
            {gancho.titular}
          </div>
        </Mascara>
      </div>
    </AbsoluteFill>
  );
};
