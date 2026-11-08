import React from "react";
import { AbsoluteFill, interpolate, useCurrentFrame, useVideoConfig } from "remotion";
import { Chip, Escudo, Mascara, SEGURA, Sfx, tamParaAncho, useColores, useReel } from "../../../base/comun";
import { EASE_OUT, STAGGER, blurEntrada, cuenta, entra, golpe } from "../../../base/movimiento";
import type { PropsClasificacion } from "../tipos";

const ANCHO = 1080 - 2 * SEGURA.x;

// Gancho: el líder en el primer segundo (escudo grande y puntos), antes que la tabla.
export const Lider: React.FC = () => {
  const frame = useCurrentFrame();
  const { fps, durationInFrames } = useVideoConfig();
  const c = useColores();
  const { filas, ventaja, corto, trasJornada, fuenteTitulo, fuenteTexto } = useReel<PropsClasificacion>();
  const lider = filas[0];
  if (!lider) return null;

  const nombre = lider.nombre.toUpperCase();
  const tamNombre = Math.max(72, tamParaAncho(nombre, ANCHO, 130, nombre.length > 14 ? 2 : 1));
  const ptsEn = 20;
  const balance = [
    `${lider.pg} G`,
    lider.pe ? `${lider.pe} E` : "",
    `${lider.pp} P`,
  ].filter(Boolean).join(" · ");
  const sobre =
    filas.length < 2 ? "" : ventaja > 0 ? `+${ventaja} sobre el 2º` : "Empatado con el 2º";

  return (
    <AbsoluteFill>
      <Sfx nombre="impacto" en={2} />
      <Sfx nombre="whoosh" en={14} volumen={0.7} />
      <Sfx nombre="tic" en={ptsEn + 6} volumen={0.8} />

      {/* destello de acento al arrancar (enlaza con el final para el bucle) */}
      <AbsoluteFill
        style={{
          background: c.acento,
          opacity: interpolate(frame, [0, 6], [1, 0], { extrapolateRight: "clamp", easing: EASE_OUT }),
        }}
      />

      {/* "LÍDER" gigante en contorno, deslizándose detrás (movimiento secundario) */}
      <div
        style={{
          position: "absolute",
          top: 330,
          left: 0,
          whiteSpace: "nowrap",
          fontFamily: fuenteTitulo,
          fontWeight: 700,
          fontSize: 420,
          lineHeight: 1,
          color: "transparent",
          WebkitTextStroke: `4px ${c.acento}`,
          opacity: 0.22 * entra(frame, 4, 20),
          translate: `${interpolate(frame, [0, durationInFrames], [-40, -260])}px 0px`,
        }}
      >
        LÍDER LÍDER
      </div>

      <div style={{ position: "absolute", left: SEGURA.x, right: SEGURA.x, top: SEGURA.arriba + 30 }}>
        <div
          style={{
            translate: `${interpolate(entra(frame, 0, 14), [0, 1], [-900, 0])}px 0px`,
            filter: `blur(${blurEntrada(frame, 0, 14)}px)`,
          }}
        >
          <Chip tam={50}>
            {corto} · Líder tras la J{trasJornada}
          </Chip>
        </div>
      </div>

      <div style={{ position: "absolute", left: 0, right: 0, top: 400, display: "flex", justifyContent: "center" }}>
        <div
          style={{
            scale: String(golpe(frame, fps, 2) * interpolate(frame, [12, durationInFrames], [1, 1.05], { extrapolateLeft: "clamp" })),
            rotate: `${interpolate(entra(frame, 2, 22), [0, 1], [-10, 0])}deg`,
          }}
        >
          <Escudo src={lider.escudo} lado={400} borde={c.acento} />
        </div>
      </div>

      <div style={{ position: "absolute", left: SEGURA.x, right: SEGURA.x, top: 860 }}>
        <Mascara p={entra(frame, 8, 18)}>
          <div
            style={{
              fontFamily: fuenteTitulo,
              fontWeight: 700,
              fontSize: tamNombre,
              lineHeight: 0.98,
              textTransform: "uppercase",
              color: c.texto,
              textAlign: "center",
            }}
          >
            {lider.nombre}
          </div>
        </Mascara>
        <div
          style={{
            height: 10,
            width: `${entra(frame, 14, 18) * 100}%`,
            background: c.acento,
            margin: "26px auto 0",
          }}
        />
      </div>

      <div
        style={{
          position: "absolute",
          left: SEGURA.x,
          right: SEGURA.x,
          top: 1170,
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          gap: 44,
        }}
      >
        <div
          style={{
            display: "flex",
            alignItems: "baseline",
            gap: 14,
            opacity: entra(frame, ptsEn - 4, 10),
            translate: `0px ${(1 - entra(frame, ptsEn - 4, 16)) * 80}px`,
          }}
        >
          <span style={{ fontFamily: fuenteTitulo, fontWeight: 700, fontSize: 220, lineHeight: 0.85, color: c.acento }}>
            {cuenta(frame, ptsEn, lider.pt, 16)}
          </span>
          <span style={{ fontFamily: fuenteTitulo, fontWeight: 700, fontSize: 64, color: c.acento }}>PTS</span>
        </div>
        <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
          {[balance, sobre].filter(Boolean).map((t, i) => {
            const p = entra(frame, ptsEn + 8 + i * STAGGER, 16);
            return (
              <div
                key={t}
                style={{
                  fontFamily: fuenteTexto,
                  fontWeight: 700,
                  fontSize: 48,
                  textTransform: "uppercase",
                  color: i === 0 ? c.texto : c.gris,
                  opacity: p,
                  translate: `${(1 - p) * 60}px 0px`,
                  whiteSpace: "nowrap",
                }}
              >
                {t}
              </div>
            );
          })}
        </div>
      </div>
    </AbsoluteFill>
  );
};
