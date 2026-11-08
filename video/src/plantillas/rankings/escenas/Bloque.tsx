import React from "react";
import { AbsoluteFill, interpolate, useCurrentFrame, useVideoConfig } from "remotion";
import { Chip, Escudo, SEGURA, Sfx, useColores, useReel } from "../../../base/comun";
import { cuenta, entra, golpe, muelle } from "../../../base/movimiento";
import type { Bloque as TBloque, FilaRanking, PropsRankings } from "../tipos";

export const DURACION_BLOQUE = 112;
/** Con un solo ranking se alarga para que el reel no baje de 10 s. */
export const duracionBloque = (bloques: number) => (bloques === 1 ? 172 : DURACION_BLOQUE);
const INICIO = 10;
const PASO = 5; // escalonado entre filas
const ALTO = 172;
const W = { pos: 70, escudo: 104, valor: 150 };
const GAP = 20;
const ANCHO_NOMBRE = 1080 - 2 * SEGURA.x - 2 * 24 - W.pos - W.escudo - W.valor - 3 * GAP;

const Fila: React.FC<{ f: FilaRanking; desde: number; max: number; primero: boolean }> = ({ f, desde, max, primero }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const c = useColores();
  const { fuenteTitulo, fuenteTexto } = useReel<PropsRankings>();
  const lider = primero; // con empates, solo se destaca la primera fila
  const m = muelle(frame, fps, desde, 14, 170);
  const crece = entra(frame, desde + 8, 24);
  // Oswald en mayúsculas: ~0,56 em por letra. Si los apellidos no caben a buen tamaño, el recortado.
  const ajusta = (t: string) => Math.min(66, Math.floor(ANCHO_NOMBRE / (t.length * 0.56)));
  const apellidos = ajusta(f.apellidos) >= 54 || !f.corto ? f.apellidos : f.corto;
  const tam = Math.max(44, ajusta(apellidos));
  const tinta = lider ? c.sobreAcento : c.texto;

  return (
    <div
      style={{
        height: ALTO,
        display: "flex",
        alignItems: "center",
        gap: GAP,
        padding: "0 24px",
        background: lider ? c.acento : c.panel,
        color: tinta,
        translate: `${(1 - m) * 1100}px 0px`,
        overflow: "hidden",
      }}
    >
      <div style={{ width: W.pos, flexShrink: 0, fontFamily: fuenteTitulo, fontWeight: 700, fontSize: 84, textAlign: "center" }}>{f.pos}</div>
      <div style={{ scale: String(golpe(frame, fps, desde + 3)) }}>
        <Escudo src={f.escudo} lado={W.escudo} borde={lider ? c.sobreAcento : undefined} />
      </div>
      <div style={{ flex: 1, minWidth: 0, display: "flex", flexDirection: "column" }}>
        <div
          style={{
            fontFamily: fuenteTexto,
            fontWeight: 700,
            fontSize: 44,
            lineHeight: 1,
            textTransform: "uppercase",
            color: lider ? "rgba(12,22,49,.72)" : c.gris,
            whiteSpace: "nowrap",
            overflow: "hidden",
            textOverflow: "ellipsis",
            opacity: entra(frame, desde + 4, 14),
          }}
        >
          {f.nombre}
        </div>
        <div
          style={{
            fontFamily: fuenteTitulo,
            fontWeight: 700,
            fontSize: tam,
            lineHeight: 1.05,
            textTransform: "uppercase",
            whiteSpace: "nowrap",
            overflow: "hidden",
            textOverflow: "ellipsis",
          }}
        >
          {apellidos}
        </div>
        {/* barra proporcional que crece con el contador */}
        <div style={{ height: 18, marginTop: 8, background: lider ? "rgba(12,22,49,.18)" : `${c.linea}` }}>
          <div
            style={{
              height: "100%",
              width: `${(f.valor / max) * 100 * crece}%`,
              background: lider ? c.sobreAcento : c.acento,
            }}
          />
        </div>
      </div>
      <div
        style={{
          width: W.valor,
          flexShrink: 0,
          textAlign: "right",
          fontFamily: fuenteTitulo,
          fontWeight: 700,
          fontSize: 96,
          lineHeight: 1,
          color: lider ? c.sobreAcento : c.acento,
        }}
      >
        {cuenta(frame, desde + 8, f.valor, 24)}
      </div>
    </div>
  );
};

// Un ranking de temporada: top 5 con barras proporcionales y contadores.
export const Bloque: React.FC<{ bloque: TBloque }> = ({ bloque }) => {
  const frame = useCurrentFrame();
  const c = useColores();
  const { trasJornada, fuenteTexto } = useReel<PropsRankings>();
  const max = Math.max(1, ...bloque.filas.map((f) => f.valor));

  return (
    <AbsoluteFill>
      <Sfx nombre="whoosh" en={0} />
      {bloque.filas.slice(0, 3).map((_, i) => (
        <Sfx key={i} nombre="tic" en={INICIO + i * PASO + 4} volumen={0.6} />
      ))}
      <Sfx nombre="pop" en={INICIO + 8 + 24} volumen={0.7} />

      <div style={{ position: "absolute", left: SEGURA.x, right: SEGURA.x, top: SEGURA.arriba + 30 }}>
        <div style={{ translate: `${(1 - entra(frame, 0, 16)) * -900}px 0px` }}>
          <Chip tam={60}>{bloque.titulo}</Chip>
        </div>
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
            translate: `${interpolate(entra(frame, 6, 16), [0, 1], [-40, 0])}px 0px`,
          }}
        >
          {bloque.unidad} · Tras la jornada {trasJornada}
        </div>
      </div>

      <div style={{ position: "absolute", left: SEGURA.x, right: SEGURA.x, top: 500, display: "flex", flexDirection: "column", gap: 16 }}>
        {bloque.filas.map((f, i) => (
          <Fila key={`${i}${f.nombre}${f.apellidos}`} f={f} desde={INICIO + i * PASO} max={max} primero={i === 0} />
        ))}
      </div>
    </AbsoluteFill>
  );
};
