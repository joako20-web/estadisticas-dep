import React from "react";
import type { PartidoPrevia, PropsPrevia } from "../tipos";
import { textoDia } from "../tipos";
import { AbsoluteFill, Sequence, interpolate, useCurrentFrame, useVideoConfig } from "remotion";
import { Chip, Escudo, Mascara, SEGURA, Sfx, tamParaAncho, useColores, useReel } from "../../../base/comun";
import { STAGGER, blurEntrada, entra, golpe, muelle, sale } from "../../../base/movimiento";
import type { Equipo } from "../../../base/tipos";
import { Pin } from "./Pin";

/** Frames por partido: con muchos partidos, algo más rápido para no pasar de ~22 s. */
export const porPartido = (n: number) => (n <= 5 ? 60 : 50);

const ANCHO = 1080 - 2 * SEGURA.x;
const ALTO_FILA = 210;
const LADO_ESCUDO = 160;
const TOP_FECHA = 470;
const TOP_FILAS = 650;

const Fila: React.FC<{ eq: Equipo; desde: number; lado: 1 | -1; dur: number }> = ({ eq, desde, lado, dur }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const c = useColores();
  const { fuenteTitulo } = useReel<PropsPrevia>();
  const m = muelle(frame, fps, desde, 13, 160);
  const salida = sale(frame, dur - 11, 10);
  const tam = tamParaAncho(eq.nombre.toUpperCase(), ANCHO - 60 - LADO_ESCUDO - 30, 84, 2);
  return (
    <div
      style={{
        height: ALTO_FILA,
        display: "flex",
        alignItems: "center",
        gap: 30,
        padding: "0 30px",
        background: c.panel,
        translate: `${(1 - m) * 1100 * lado + salida * -1100 * lado}px 0px`,
        filter: `blur(${blurEntrada(frame, desde, 12, 10) + salida * 10}px)`,
      }}
    >
      <div style={{ scale: String(golpe(frame, fps, desde + 4)) }}>
        <Escudo src={eq.escudo} lado={LADO_ESCUDO} />
      </div>
      <div style={{ flex: 1, fontFamily: fuenteTitulo, fontWeight: 700, fontSize: tam, lineHeight: 1, color: c.texto, textTransform: "uppercase" }}>
        {eq.nombre}
      </div>
    </div>
  );
};

const Tarjeta: React.FC<{ p: PartidoPrevia; dur: number }> = ({ p, dur }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const c = useColores();
  const { fuenteTitulo, fuenteTexto } = useReel<PropsPrevia>();
  const salida = sale(frame, dur - 11, 10);
  const fuera = { opacity: 1 - salida, translate: `0px ${salida * -40}px` };
  const dia = muelle(frame, fps, 0, 14, 180);
  const vs = golpe(frame, fps, 12);

  return (
    <AbsoluteFill>
      <Sfx nombre="whoosh" en={0} volumen={0.8} />
      <Sfx nombre="tic" en={6} volumen={0.6} />
      <Sfx nombre="pop" en={13} volumen={0.7} />

      {/* cuándo: día en rótulo y hora grande */}
      <div style={{ position: "absolute", left: SEGURA.x, right: SEGURA.x, top: TOP_FECHA, ...fuera }}>
        <div style={{ display: "flex", alignItems: "center", gap: 28 }}>
          <div style={{ translate: `${(1 - dia) * -800}px 0px` }}>
            <Chip tam={58} style={{ whiteSpace: "nowrap" }}>{textoDia(p)}</Chip>
          </div>
          <Mascara p={entra(frame, 5, 16)}>
            <div
              style={{
                fontFamily: fuenteTitulo,
                fontWeight: 700,
                fontSize: p.hora ? 128 : 52,
                lineHeight: 1,
                color: p.hora ? c.texto : c.gris,
                textTransform: "uppercase",
                whiteSpace: "nowrap",
                fontVariantNumeric: "tabular-nums",
              }}
            >
              {p.hora || (p.dia ? "Hora por confirmar" : "")}
            </div>
          </Mascara>
        </div>
      </div>

      <div style={{ position: "absolute", left: SEGURA.x, right: SEGURA.x, top: TOP_FILAS, display: "flex", flexDirection: "column", gap: 16 }}>
        <Fila eq={p.local} desde={2} lado={-1} dur={dur} />
        <Fila eq={p.visitante} desde={2 + STAGGER} lado={1} dur={dur} />
      </div>

      {/* VS entre los dos escudos */}
      <div
        style={{
          position: "absolute",
          left: SEGURA.x + 30 + LADO_ESCUDO / 2 - 52,
          top: TOP_FILAS + ALTO_FILA + 8 - 52,
          width: 104,
          height: 104,
          borderRadius: "50%",
          background: c.acento,
          color: c.sobreAcento,
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          fontFamily: fuenteTitulo,
          fontWeight: 700,
          fontSize: 48,
          boxShadow: `0 0 0 8px ${c.fondo}`,
          scale: String(vs * (1 - salida)),
          opacity: frame >= 12 ? 1 : 0,
        }}
      >
        VS
      </div>

      {p.campo || p.destacado ? (
        <div style={{ position: "absolute", left: SEGURA.x, right: SEGURA.x, top: TOP_FILAS + 2 * ALTO_FILA + 16 + 40, ...fuera }}>
          {p.campo ? (
            <Mascara p={entra(frame, 14, 16)}>
              <div style={{ display: "flex", alignItems: "center", gap: 16, fontFamily: fuenteTexto, fontWeight: 700, fontSize: 46, lineHeight: 1.1, color: c.gris }}>
                <Pin lado={50} />
                <span>{p.campo}</span>
              </div>
            </Mascara>
          ) : null}
          {p.destacado ? (
            <div style={{ marginTop: p.campo ? 26 : 0, scale: String(golpe(frame, fps, 20)), transformOrigin: "0% 50%" }}>
              <Chip tam={44} invertido>
                ★ El partido de la jornada
              </Chip>
            </div>
          ) : null}
        </div>
      ) : null}
    </AbsoluteFill>
  );
};

const Progreso: React.FC<{ total: number; dur: number }> = ({ total, dur }) => {
  const frame = useCurrentFrame();
  const c = useColores();
  return (
    <div style={{ position: "absolute", left: SEGURA.x, right: SEGURA.x, top: 1400, display: "flex", gap: 12 }}>
      {Array.from({ length: total }).map((_, i) => (
        <div key={i} style={{ flex: 1, height: 10, background: c.linea, overflow: "hidden" }}>
          <div
            style={{
              height: "100%",
              background: c.acento,
              width: `${interpolate(frame, [i * dur, (i + 1) * dur - 6], [0, 100], {
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

// Cada partido de la jornada, uno detrás de otro, con el rótulo y la barra de progreso fijos.
export const Partidos: React.FC = () => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const c = useColores();
  const { partidos, jornada, fuenteTexto } = useReel<PropsPrevia>();
  const dur = porPartido(partidos.length);
  const rotulo = entra(frame, 0, 16);
  return (
    <AbsoluteFill>
      <div style={{ position: "absolute", left: SEGURA.x, top: SEGURA.arriba + 30, translate: `${(1 - rotulo) * -700}px 0px` }}>
        <Chip tam={50}>Próxima jornada</Chip>
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
        <Sequence key={i} name={`Partido ${i + 1}`} from={i * dur} durationInFrames={dur} premountFor={fps}>
          <Tarjeta p={p} dur={dur} />
        </Sequence>
      ))}
      <Progreso total={partidos.length} dur={dur} />
      <div
        style={{
          position: "absolute",
          right: SEGURA.x,
          top: 1430,
          fontFamily: fuenteTexto,
          fontWeight: 700,
          fontSize: 44,
          color: c.apagado,
          opacity: entra(frame, 10, 16),
        }}
      >
        {Math.min(partidos.length, Math.floor(frame / dur) + 1)}/{partidos.length}
      </div>
    </AbsoluteFill>
  );
};
