import React from "react";
import { AbsoluteFill, interpolate, useCurrentFrame, useVideoConfig } from "remotion";
import { Chip, Escudo, SEGURA, Sfx, useColores, useReel } from "../../../base/comun";
import { cuenta, entra, golpe, muelle } from "../../../base/movimiento";
import { useLados } from "../comun";
import type { PropsFinal } from "../tipos";

export const DUR_ANOTADORES = 104;
const PASO = 5;
const INICIO = 8;
const ANCHO = 1080 - 2 * SEGURA.x;

// Anotadores del partido: filas escalonadas, el máximo anotador encendido en el acento.
export const Anotadores: React.FC = () => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const c = useColores();
  const { anotadores, fuenteTitulo, fuenteTexto } = useReel<PropsFinal>();
  const lados = useLados();
  const alto = anotadores.length > 3 ? 220 : 250;

  return (
    <AbsoluteFill>
      <Sfx nombre="whoosh" en={0} />
      {anotadores.map((_, i) => (
        <Sfx key={i} nombre="tic" en={INICIO + i * PASO + 4} volumen={0.7} />
      ))}
      <Sfx nombre="pop" en={INICIO + 26} />

      <div style={{ position: "absolute", left: SEGURA.x, top: SEGURA.arriba + 30, translate: `${(1 - entra(frame, 0, 16)) * -700}px 0px` }}>
        <Chip tam={50}>Anotadores</Chip>
      </div>

      <div
        style={{
          position: "absolute",
          left: SEGURA.x,
          right: SEGURA.x,
          top: 400,
          display: "flex",
          flexDirection: "column",
          gap: 20,
        }}
      >
        {anotadores.map((a, i) => {
          const desde = INICIO + i * PASO;
          const m = muelle(frame, fps, desde, 14, 170);
          const primero = i === 0;
          const enciende = primero ? entra(frame, INICIO + 24, 12) : 0;
          const eq = lados[a.lado].eq;
          const tinta = primero && enciende > 0.5 ? c.sobreAcento : c.texto;
          const anchoNombre = ANCHO - 60 - 130 - 2 * 28 - 210;
          // Oswald en mayúsculas ocupa ~0,52 em por letra: una sola línea, que siempre quepa
          const tam = Math.max(44, Math.min(76, Math.floor(anchoNombre / (a.apellidos.length * 0.52))));
          return (
            <div
              key={i}
              style={{
                position: "relative",
                minHeight: alto,
                display: "flex",
                alignItems: "center",
                gap: 28,
                padding: "18px 30px",
                background: c.panel,
                overflow: "hidden",
                translate: `${(1 - m) * 1100}px 0px`,
              }}
            >
              {primero ? (
                <div style={{ position: "absolute", inset: 0, background: c.acento, clipPath: `inset(0 ${(1 - enciende) * 100}% 0 0)` }} />
              ) : null}
              <div style={{ position: "relative", scale: String(golpe(frame, fps, desde + 3)) }}>
                <Escudo src={eq.escudo} lado={130} borde={primero ? c.sobreAcento : undefined} />
              </div>
              <div style={{ position: "relative", flex: 1, minWidth: 0 }}>
                <div
                  style={{
                    fontFamily: fuenteTexto,
                    fontWeight: 700,
                    fontSize: 44,
                    lineHeight: 1.1,
                    textTransform: "uppercase",
                    color: primero && enciende > 0.5 ? c.sobreAcento : c.gris,
                  }}
                >
                  {a.nombre}
                </div>
                <div
                  style={{
                    fontFamily: fuenteTitulo,
                    fontWeight: 700,
                    fontSize: tam,
                    lineHeight: 1.02,
                    whiteSpace: "nowrap",
                    textTransform: "uppercase",
                    color: tinta,
                  }}
                >
                  {a.apellidos}
                </div>
                <div
                  style={{
                    fontFamily: fuenteTexto,
                    fontWeight: 700,
                    fontSize: 44,
                    lineHeight: 1.1,
                    color: primero && enciende > 0.5 ? c.sobreAcento : c.gris,
                    opacity: entra(frame, desde + 10, 14),
                  }}
                >
                  {a.detalle}
                </div>
              </div>
              <div style={{ position: "relative", width: 210, textAlign: "right", color: primero && enciende > 0.5 ? c.sobreAcento : c.acento }}>
                <span style={{ fontFamily: fuenteTitulo, fontWeight: 700, fontSize: 130, lineHeight: 1, fontVariantNumeric: "tabular-nums" }}>
                  {cuenta(frame, desde + 6, a.puntos, 16)}
                </span>
                <div
                  style={{
                    fontFamily: fuenteTitulo,
                    fontWeight: 700,
                    fontSize: 44,
                    lineHeight: 1,
                    opacity: interpolate(entra(frame, desde + 8, 14), [0, 1], [0, 1]),
                  }}
                >
                  PTS
                </div>
              </div>
            </div>
          );
        })}
      </div>
    </AbsoluteFill>
  );
};
