import React from "react";
import type { PropsJornada } from "../tipos";
import { AbsoluteFill, interpolate, useCurrentFrame, useVideoConfig } from "remotion";
import { Chip, Escudo, Mascara, SEGURA, Sfx, useColores, useReel } from "../../../base/comun";
import { STAGGER, cuenta, entra, golpe } from "../../../base/movimiento";

// Jugador de la jornada: apellido letra a letra, escudo de fondo y estadísticas en contador.
export const Mvp: React.FC = () => {
  const frame = useCurrentFrame();
  const { fps, durationInFrames } = useVideoConfig();
  const c = useColores();
  const { mvp, fuenteTitulo, fuenteTexto } = useReel<PropsJornada>();
  if (!mvp) return null;

  const apellidos = mvp.apellidos.toUpperCase();
  const tamApellido = Math.min(150, Math.floor((1080 - 2 * SEGURA.x) / (Math.max(...apellidos.split(" ").map((p) => p.length)) * 0.5)));
  const letras = apellidos.split("");
  const barra = entra(frame, 6, 20);
  const puntosEn = 34;

  return (
    <AbsoluteFill>
      <Sfx nombre="whoosh" en={0} />
      <Sfx nombre="impacto" en={puntosEn + 14} volumen={0.8} />

      {/* escudo gigante de fondo, girando muy despacio (movimiento secundario) */}
      <div
        style={{
          position: "absolute",
          right: -260,
          top: 300,
          // solo fuera de las transiciones: dentro de ellas el blend no funciona y sale un disco blanco
          opacity: interpolate(entra(frame, 12, 20) - entra(frame, durationInFrames - 24, 12), [0, 1], [0, 0.55]),
          mixBlendMode: "multiply",
          rotate: `${interpolate(frame, [0, durationInFrames], [-8, 4])}deg`,
          scale: String(interpolate(entra(frame, 12, 30), [0, 1], [1.25, 1])),
          filter: "grayscale(1) contrast(1.4)",
        }}
      >
        <Escudo src={mvp.escudo} lado={900} />
      </div>

      <div style={{ position: "absolute", left: SEGURA.x, top: SEGURA.arriba + 30, translate: `${(1 - entra(frame, 0, 16)) * -700}px 0px` }}>
        <Chip tam={50}>★ Jugador de la jornada</Chip>
      </div>

      <div style={{ position: "absolute", left: SEGURA.x, right: SEGURA.x, top: 560 }}>
        <Mascara p={entra(frame, 4, 16)}>
          <div style={{ fontFamily: fuenteTexto, fontWeight: 700, fontSize: 64, textTransform: "uppercase", color: c.gris, letterSpacing: "0.04em" }}>
            {mvp.nombre}
          </div>
        </Mascara>
        <div
          style={{
            fontFamily: fuenteTitulo,
            fontWeight: 700,
            fontSize: tamApellido,
            lineHeight: 0.95,
            color: c.texto,
            display: "flex",
            flexWrap: "wrap",
            marginTop: 6,
          }}
        >
          {letras.map((l, i) => {
            const p = entra(frame, 8 + i * 1.5, 14);
            return (
              <span
                key={i}
                style={{
                  display: "inline-block",
                  whiteSpace: "pre",
                  opacity: p,
                  translate: `0px ${(1 - p) * 60}px`,
                  width: l === " " ? "100%" : undefined,
                  height: l === " " ? 0 : undefined,
                }}
              >
                {l === " " ? "" : l}
              </span>
            );
          })}
        </div>
        <div style={{ height: 12, width: `${barra * 62}%`, background: c.acento, marginTop: 30 }} />
        <div style={{ display: "flex", alignItems: "center", gap: 26, marginTop: 34 }}>
          <div style={{ scale: String(golpe(frame, fps, 18)) }}>
            <Escudo src={mvp.escudo} lado={120} />
          </div>
          <Mascara p={entra(frame, 20, 16)}>
            <div style={{ fontFamily: fuenteTexto, fontWeight: 700, fontSize: 48, lineHeight: 1.1, color: c.texto, textTransform: "uppercase" }}>
              {mvp.equipo}
              <div style={{ color: c.gris, fontSize: 44 }}>
                {mvp.posicion}
                {mvp.dorsal && !mvp.posicion.includes(String(mvp.dorsal)) ? ` · Nº ${mvp.dorsal}` : ""}
              </div>
            </div>
          </Mascara>
        </div>
      </div>

      <div
        style={{
          position: "absolute",
          left: SEGURA.x,
          right: SEGURA.x,
          top: 1230,
          display: "flex",
          alignItems: "flex-end",
          gap: 40,
        }}
      >
        <div style={{ display: "flex", alignItems: "baseline", gap: 16, translate: `0px ${(1 - entra(frame, puntosEn - 4, 16)) * 80}px`, opacity: entra(frame, puntosEn - 4, 10) }}>
          <span style={{ fontFamily: fuenteTitulo, fontWeight: 700, fontSize: 200, lineHeight: 0.85, color: c.acento }}>
            {cuenta(frame, puntosEn, mvp.puntos, 14)}
          </span>
          <span style={{ fontFamily: fuenteTitulo, fontWeight: 700, fontSize: 64, color: c.acento }}>PTS</span>
        </div>
        <div style={{ display: "flex", flexDirection: "column", gap: 6, paddingBottom: 10 }}>
          {mvp.stats.map((s, i) => {
            const p = entra(frame, puntosEn + 6 + i * STAGGER, 16);
            return (
              <div
                key={s.texto}
                style={{
                  fontFamily: fuenteTexto,
                  fontWeight: 700,
                  fontSize: 50,
                  color: c.texto,
                  textTransform: "uppercase",
                  opacity: p,
                  translate: `${(1 - p) * 60}px 0px`,
                }}
              >
                {cuenta(frame, puntosEn + 6 + i * STAGGER, s.valor, 12)} {s.texto}
              </div>
            );
          })}
        </div>
      </div>
    </AbsoluteFill>
  );
};
