import React from "react";
import type { PropsJornada } from "../tipos";
import { AbsoluteFill, interpolate, useCurrentFrame, useVideoConfig } from "remotion";
import { Chip, Escudo, SEGURA, Sfx, tamParaAncho, useColores, useReel } from "../../../base/comun";
import { cuenta, entra, golpe, muelle } from "../../../base/movimiento";

const PASO = 5; // escalonado entre filas

// Top 4: filas que entran escalonadas, franja de zona que se dibuja y barras de puntos.
export const Clasificacion: React.FC = () => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const c = useColores();
  const { top, zonaTop, trasJornada, fuenteTitulo, fuenteTexto } = useReel<PropsJornada>();
  const maxPt = Math.max(1, ...top.map((f) => f.pt));
  const inicio = 10;

  return (
    <AbsoluteFill>
      <Sfx nombre="whoosh" en={0} />
      {top.map((_, i) => (
        <Sfx key={i} nombre="tic" en={inicio + i * PASO + 4} volumen={0.8} />
      ))}
      <Sfx nombre="pop" en={inicio + 3 * PASO + 26} />

      <div style={{ position: "absolute", left: SEGURA.x, top: SEGURA.arriba + 30, translate: `${(1 - entra(frame, 0, 16)) * -700}px 0px` }}>
        <Chip tam={50}>Clasificación</Chip>
        <div
          style={{
            fontFamily: fuenteTexto,
            fontWeight: 700,
            fontSize: 46,
            color: c.gris,
            textTransform: "uppercase",
            letterSpacing: "0.06em",
            marginTop: 22,
            opacity: entra(frame, 6, 16),
          }}
        >
          Tras la jornada {trasJornada}
        </div>
      </div>

      <div style={{ position: "absolute", left: SEGURA.x, right: SEGURA.x, top: 600, display: "flex", flexDirection: "column", gap: 16 }}>
        {top.map((f, i) => {
          const desde = inicio + i * PASO;
          const m = muelle(frame, fps, desde, 14, 170);
          const lider = i === 0;
          const zona = entra(frame, desde + 8, 14);
          const barra = entra(frame, desde + 10, 22);
          const tam = tamParaAncho(f.nombre.toUpperCase(), 470, 58, 1);
          return (
            <div
              key={f.pos}
              style={{
                position: "relative",
                height: 160,
                display: "flex",
                alignItems: "center",
                gap: 22,
                paddingLeft: 40,
                paddingRight: 28,
                background: lider ? c.acento : c.panel,
                color: lider ? c.sobreAcento : c.texto,
                translate: `${(1 - m) * 1100}px 0px`,
                overflow: "hidden",
              }}
            >
              {/* franja de zona (semifinales) que se dibuja de arriba abajo */}
              <div
                style={{
                  position: "absolute",
                  left: 0,
                  top: 0,
                  bottom: 0,
                  width: 12,
                  background: lider ? c.sobreAcento : c.acento,
                  scale: `1 ${f.zona ? zona : 0}`,
                  transformOrigin: "50% 0%",
                }}
              />
              {/* barra de puntos proporcional */}
              <div
                style={{
                  position: "absolute",
                  left: 0,
                  bottom: 0,
                  height: 8,
                  width: `${(f.pt / maxPt) * 100 * barra}%`,
                  background: lider ? c.sobreAcento : c.acento,
                  opacity: lider ? 0.35 : 0.7,
                }}
              />
              <div style={{ width: 60, fontFamily: fuenteTitulo, fontWeight: 700, fontSize: 76, textAlign: "center" }}>{f.pos}</div>
              <div style={{ scale: String(golpe(frame, fps, desde + 3)) }}>
                <Escudo src={f.escudo} lado={110} borde={lider ? c.sobreAcento : undefined} />
              </div>
              <div style={{ flex: 1, fontFamily: fuenteTitulo, fontWeight: 700, fontSize: tam, lineHeight: 1, textTransform: "uppercase", whiteSpace: "nowrap" }}>
                {f.nombre}
              </div>
              <div style={{ textAlign: "right" }}>
                <div style={{ fontFamily: fuenteTitulo, fontWeight: 700, fontSize: 84, lineHeight: 0.9 }}>{cuenta(frame, desde + 8, f.pt, 18)}</div>
                <div style={{ fontFamily: fuenteTexto, fontWeight: 700, fontSize: 26, opacity: 0.7, letterSpacing: "0.08em" }}>PTS</div>
              </div>
            </div>
          );
        })}
      </div>

      {zonaTop ? (
        <div
          style={{
            position: "absolute",
            left: SEGURA.x,
            top: 1330,
            display: "flex",
            alignItems: "center",
            gap: 18,
            fontFamily: fuenteTexto,
            fontWeight: 700,
            fontSize: 44,
            color: c.gris,
            textTransform: "uppercase",
            opacity: entra(frame, inicio + 4 * PASO + 10, 16),
            translate: `0px ${interpolate(entra(frame, inicio + 4 * PASO + 10, 16), [0, 1], [30, 0])}px`,
          }}
        >
          <div style={{ width: 12, height: 50, background: c.acento }} />
          {zonaTop}
        </div>
      ) : null}
    </AbsoluteFill>
  );
};
