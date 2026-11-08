import React from "react";
import type { PropsJornada } from "../tipos";
import { AbsoluteFill, Sequence, interpolate, useCurrentFrame, useVideoConfig } from "remotion";
import { Chip, Escudo, SEGURA, Sfx, tamParaAncho, useColores, useReel } from "../../../base/comun";
import { STAGGER, blurEntrada, cuenta, entra, golpe, muelle, sale } from "../../../base/movimiento";
import type { Equipo, Partido } from "../../../base/tipos";

export const POR_PARTIDO = 60;
const ANCHO = 1080 - 2 * SEGURA.x;
const ALTO_FILA = 300;

const Fila: React.FC<{ eq: Equipo; desde: number; lado: 1 | -1; marcadorEn: number; final: number }> = ({
  eq,
  desde,
  lado,
  marcadorEn,
  final,
}) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const c = useColores();
  const { fuenteTitulo } = useReel<PropsJornada>();
  const m = muelle(frame, fps, desde, 13, 160);
  const decidido = entra(frame, final, 12); // ganador se enciende, perdedor se apaga
  const salida = sale(frame, POR_PARTIDO - 11, 10);
  const anchoNombre = ANCHO - 200 - 260 - 60;
  const tam = tamParaAncho(eq.nombre.toUpperCase(), anchoNombre, 76);
  const encendido = eq.gana && decidido > 0.5;

  return (
    <div
      style={{
        position: "relative",
        height: ALTO_FILA,
        display: "flex",
        alignItems: "center",
        gap: 30,
        padding: "0 30px",
        background: c.panel,
        translate: `${(1 - m) * 1100 * lado + salida * -1100 * lado}px 0px`,
        filter: `blur(${blurEntrada(frame, desde, 12, 10) + salida * 10}px)`,
        overflow: "hidden",
      }}
    >
      {/* barrido de acento detrás del ganador */}
      {eq.gana ? (
        <div
          style={{
            position: "absolute",
            inset: 0,
            background: c.acento,
            clipPath: `inset(0 ${(1 - decidido) * 100}% 0 0)`,
          }}
        />
      ) : null}
      <div style={{ scale: String(golpe(frame, fps, desde + 4)), position: "relative" }}>
        <Escudo src={eq.escudo} lado={220} borde={eq.gana ? c.sobreAcento : undefined} />
      </div>
      <div
        style={{
          position: "relative",
          flex: 1,
          fontFamily: fuenteTitulo,
          fontWeight: 700,
          fontSize: tam,
          lineHeight: 1,
          textTransform: "uppercase",
          color: encendido ? c.sobreAcento : c.texto,
          opacity: eq.gana ? 1 : interpolate(decidido, [0, 1], [1, 0.5]),
        }}
      >
        {eq.nombre}
      </div>
      <div
        style={{
          position: "relative",
          width: 240,
          textAlign: "right",
          fontFamily: fuenteTitulo,
          fontWeight: 700,
          fontSize: 190,
          lineHeight: 1,
          fontVariantNumeric: "tabular-nums",
          color: encendido ? c.sobreAcento : c.texto,
          opacity: eq.gana ? 1 : interpolate(decidido, [0, 1], [1, 0.45]),
        }}
      >
        {cuenta(frame, marcadorEn, eq.puntos ?? 0, 18)}
      </div>
    </div>
  );
};

const Marcador: React.FC<{ p: Partido }> = ({ p }) => {
  const marcadorEn = 8;
  const final = marcadorEn + 18;
  return (
    <AbsoluteFill>
      <Sfx nombre="whoosh" en={0} volumen={0.9} />
      <Sfx nombre="tic" en={marcadorEn + 4} volumen={0.7} />
      <Sfx nombre="tic" en={marcadorEn + 10} volumen={0.7} />
      <Sfx nombre="pop" en={final} />
      <div
        style={{
          position: "absolute",
          left: SEGURA.x,
          right: SEGURA.x,
          top: 600,
          display: "flex",
          flexDirection: "column",
          gap: 18,
        }}
      >
        <Fila eq={p.local} desde={0} lado={-1} marcadorEn={marcadorEn} final={final} />
        <Fila eq={p.visitante} desde={STAGGER} lado={1} marcadorEn={marcadorEn} final={final} />
      </div>
    </AbsoluteFill>
  );
};

const Progreso: React.FC<{ total: number }> = ({ total }) => {
  const frame = useCurrentFrame();
  const c = useColores();
  return (
    <div style={{ position: "absolute", left: SEGURA.x, right: SEGURA.x, top: 1290, display: "flex", gap: 12 }}>
      {Array.from({ length: total }).map((_, i) => (
        <div key={i} style={{ flex: 1, height: 10, background: c.linea, overflow: "hidden" }}>
          <div
            style={{
              height: "100%",
              background: c.acento,
              width: `${interpolate(frame, [i * POR_PARTIDO, (i + 1) * POR_PARTIDO - 6], [0, 100], {
                extrapolateLeft: "clamp",
                extrapolateRight: "clamp",
              })}%`,
            }}
          />
        </div>
      ))}
    </div>
  );
};

// Los resultados, uno detrás de otro, con el rótulo y la barra de progreso fijos.
export const Resultados: React.FC = () => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const c = useColores();
  const { partidos, jornada, fuenteTexto } = useReel<PropsJornada>();
  const rotulo = entra(frame, 0, 16);
  return (
    <AbsoluteFill>
      <div
        style={{
          position: "absolute",
          left: SEGURA.x,
          top: SEGURA.arriba + 30,
          translate: `${(1 - rotulo) * -700}px 0px`,
        }}
      >
        <Chip tam={50}>Resultados</Chip>
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
          Jornada {jornada}
        </div>
      </div>
      {partidos.map((p, i) => (
        <Sequence
          key={i}
          name={`Partido ${i + 1}`}
          from={i * POR_PARTIDO}
          durationInFrames={POR_PARTIDO}
          premountFor={fps}
        >
          <Marcador p={p} />
        </Sequence>
      ))}
      <Progreso total={partidos.length} />
      <div
        style={{
          position: "absolute",
          right: SEGURA.x,
          top: 1320,
          fontFamily: fuenteTexto,
          fontWeight: 700,
          fontSize: 44,
          color: c.apagado,
          opacity: entra(frame, 10, 16),
        }}
      >
        {Math.min(partidos.length, Math.floor(frame / POR_PARTIDO) + 1)}/{partidos.length}
      </div>
    </AbsoluteFill>
  );
};
