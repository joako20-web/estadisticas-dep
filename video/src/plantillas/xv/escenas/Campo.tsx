import React from "react";
import { AbsoluteFill, interpolate, useCurrentFrame, useVideoConfig } from "remotion";
import { Chip, Escudo, Mascara, SEGURA, Sfx, useColores, useReel } from "../../../base/comun";
import { EASE_IN_OUT, STAGGER, blurEntrada, entra, golpe, sale } from "../../../base/movimiento";
import type { JugadorXV, PropsXV } from "../tipos";

// Campo de rugby estilizado (en vertical, delanteros arriba).
const CAMPO = { x: 50, y: 420, ancho: 980, alto: 1080 };
const DIBUJO = 4; // las líneas se dibujan desde este frame
export const PRIMERA = 30; // primera fila de jugadores
export const POR_LINEA = 30;
export const ANCHO_FICHA = 300;

/** Frame en el que se destaca al mejor (después de la última fila). */
export const destacaEn = (filas: number) => PRIMERA + filas * POR_LINEA + 12;
export const duracionCampo = (filas: number) => destacaEn(filas) + 74;

const xs = (n: number) => (n === 3 ? [230, 540, 850] : n === 2 ? [340, 740] : n === 1 ? [540] : [175, 405, 675, 905].slice(0, n));
// Filas repartidas entre el 12 % y el 90 % del campo; las líneas van entre fila y fila
// para no cruzar nunca los nombres.
const FILA0 = 0.12;
const FILA1 = 0.885;
const fraccion = (i: number, filas: number) => FILA0 + (i * (FILA1 - FILA0)) / Math.max(1, filas - 1);
const ys = (filas: number) => Array.from({ length: filas }, (_, i) => CAMPO.y + CAMPO.alto * fraccion(i, filas));
const entre = (i: number, filas: number) => (fraccion(i, filas) + fraccion(i + 1, filas)) / 2;

/** Tamaño del apellido para que quepa en una línea en la ficha (mínimo 34 px). */
const tamApellido = (t: string) => Math.max(34, Math.min(46, Math.floor((ANCHO_FICHA - 10) / (t.length * 0.53))));

const Lineas: React.FC<{ filas: number }> = ({ filas }) => {
  const frame = useCurrentFrame();
  const c = useColores();
  const { x, y, ancho, alto } = CAMPO;
  const p = (i: number) => entra(frame, DIBUJO + i * 3, 22);
  const trazo = { stroke: c.texto, strokeOpacity: 0.28, strokeWidth: 4, fill: "none" } as const;
  const dibuja = (i: number) => ({ pathLength: 1, strokeDasharray: 1, strokeDashoffset: 1 - p(i) });
  const h = (f: number) => y + alto * f;
  const franjas = 8;
  // ensayo, 22, 10 m, medio campo, 10 m, 22, ensayo (con 6 filas caen entre fila y fila)
  const ensayo = [0.035, 0.968];
  const veintidos = [entre(0, filas), entre(filas - 2, filas)];
  const diez = [entre(1, filas), entre(filas - 3, filas)];
  const medio = entre(Math.floor((filas - 1) / 2), filas);
  return (
    <svg width={1080} height={1920} style={{ position: "absolute", inset: 0 }}>
      {/* franjas de césped cortado */}
      {Array.from({ length: franjas }, (_, i) => (
        <rect
          key={i}
          x={x}
          y={y + (i * alto) / franjas}
          width={ancho}
          height={alto / franjas}
          fill={i % 2 ? c.panel : "transparent"}
          opacity={0.55 * entra(frame, DIBUJO + i * 2, 20)}
        />
      ))}
      <rect x={x} y={y} width={ancho} height={alto} {...trazo} strokeOpacity={0.4} {...dibuja(0)} />
      {ensayo.map((f, i) => (
        <path key={`m${f}`} d={`M${x} ${h(f)} H${x + ancho}`} {...trazo} strokeOpacity={0.45} {...dibuja(1 + i)} />
      ))}
      {veintidos.map((f, i) => (
        <path key={`v${f}`} d={`M${x} ${h(f)} H${x + ancho}`} {...trazo} {...dibuja(3 + i)} />
      ))}
      <path d={`M${x} ${h(medio)} H${x + ancho}`} {...trazo} strokeOpacity={0.45} {...dibuja(5)} />
      {/* líneas de 10 m y de 5 m: discontinuas, aparecen sin dibujarse */}
      {diez.map((f) => (
        <path
          key={`d${f}`}
          d={`M${x} ${h(f)} H${x + ancho}`}
          {...trazo}
          strokeDasharray="26 22"
          opacity={entra(frame, DIBUJO + 18, 16)}
        />
      ))}
      {[0.06, 0.94].map((f) => (
        <path
          key={`c${f}`}
          d={`M${x + ancho * f} ${h(ensayo[0])} V${h(ensayo[1])}`}
          {...trazo}
          strokeDasharray="18 30"
          opacity={0.7 * entra(frame, DIBUJO + 22, 16)}
        />
      ))}
      {/* palos en H en las dos líneas de ensayo, hacia fuera (zona de marca) */}
      {ensayo.map((f, i) => {
        const yy = h(f);
        const s = i ? 1 : -1;
        return (
          <path
            key={`h${f}`}
            d={`M${540 - 50} ${yy} V${yy + s * 28} M${540 + 50} ${yy} V${yy + s * 28} M${540 - 50} ${yy + s * 12} H${540 + 50}`}
            stroke={c.acento}
            strokeWidth={6}
            fill="none"
            pathLength={1}
            strokeDasharray={1}
            strokeDashoffset={1 - entra(frame, DIBUJO + 20, 18)}
          />
        );
      })}
    </svg>
  );
};

const Ficha: React.FC<{ j: JugadorXV; x: number; y: number; desde: number; destaca: number }> = ({ j, x, y, desde, destaca }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const c = useColores();
  const { fuenteTitulo } = useReel();
  const apellido = j.apellido.toUpperCase();
  const foco = entra(frame, destaca, 18);
  const atenua = j.mejor ? 1 : interpolate(foco, [0, 1], [1, 0.32]);
  const escala = j.mejor ? 1 + 0.22 * golpe(frame, fps, destaca) * Math.min(1, foco * 3) : 1;
  return (
    <div
      style={{
        position: "absolute",
        left: x - ANCHO_FICHA / 2,
        top: y - 66,
        width: ANCHO_FICHA,
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        opacity: atenua,
        scale: String(escala),
        zIndex: j.mejor ? 2 : 1,
      }}
    >
      <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
        <div
          style={{
            width: 76,
            height: 76,
            borderRadius: "50%",
            background: j.mejor && foco > 0 ? c.acento : c.texto,
            color: c.sobreAcento,
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            fontFamily: fuenteTitulo,
            fontWeight: 700,
            fontSize: 46,
            boxShadow: j.mejor ? `0 0 0 ${foco * 8}px ${c.acento}55, 0 10px 30px rgba(0,0,0,.4)` : "0 10px 30px rgba(0,0,0,.4)",
            scale: String(golpe(frame, fps, desde)),
          }}
        >
          {j.puesto}
        </div>
        <div style={{ scale: String(golpe(frame, fps, desde + 3)) }}>
          <Escudo src={j.escudo} lado={62} />
        </div>
      </div>
      <Mascara p={entra(frame, desde + 4, 16)} style={{ marginTop: 8, width: ANCHO_FICHA }}>
        <div
          style={{
            fontFamily: fuenteTitulo,
            fontWeight: 700,
            fontSize: tamApellido(apellido),
            lineHeight: 1.0,
            color: c.texto,
            textAlign: "center",
            overflowWrap: "anywhere", // nombres que no caben a 34 px: a dos líneas
            textShadow: "0 4px 18px rgba(0,0,0,.55)",
          }}
        >
          {apellido}
        </div>
      </Mascara>
    </div>
  );
};

// El XV en el campo: las líneas se dibujan, los jugadores entran por filas y al final se destaca al mejor.
export const Campo: React.FC = () => {
  const frame = useCurrentFrame();
  const { durationInFrames } = useVideoConfig();
  const c = useColores();
  const { lineas, corto, jornada, fuenteTitulo } = useReel<PropsXV>();
  const filas = ys(lineas.length);
  const destaca = destacaEn(lineas.length);
  const actual = Math.max(0, Math.min(lineas.length - 1, Math.floor((frame - PRIMERA) / POR_LINEA)));
  const enFila = frame - (PRIMERA + actual * POR_LINEA);
  const cambio = actual < lineas.length - 1 ? sale(frame, PRIMERA + (actual + 1) * POR_LINEA - 9, 8) : 0;
  const titulo = frame >= destaca ? "★ Mejor nota" : lineas[actual]?.titulo ?? "";
  const pTitulo = frame >= destaca ? entra(frame, destaca, 14) : frame < PRIMERA ? 0 : entra(enFila, 0, 12) * (1 - cambio);
  const vistos = lineas.slice(0, actual + 1).reduce((n, l) => n + l.jugadores.length, 0);

  return (
    <AbsoluteFill>
      <Sfx nombre="whoosh" en={0} volumen={0.7} />
      {lineas.map((_, i) => (
        <Sfx key={i} nombre="pop" en={PRIMERA + i * POR_LINEA} volumen={0.55} />
      ))}
      <Sfx nombre="impacto" en={destaca} volumen={0.8} />

      <AbsoluteFill
        style={{
          // empuje de cámara muy lento
          scale: String(interpolate(frame, [0, durationInFrames], [1, 1.035], { easing: EASE_IN_OUT })),
          transformOrigin: "50% 60%",
        }}
      >
        <Lineas filas={lineas.length} />
        {lineas.map((l, i) => {
          const pos = xs(l.jugadores.length);
          return l.jugadores.map((j, k) => (
            <Ficha key={j.puesto} j={j} x={pos[k]} y={filas[i]} desde={PRIMERA + i * POR_LINEA + k * STAGGER} destaca={destaca} />
          ));
        })}
      </AbsoluteFill>

      <div
        style={{
          position: "absolute",
          left: SEGURA.x,
          top: SEGURA.arriba + 20,
          translate: `${(1 - entra(frame, 0, 16)) * -800}px 0px`,
          filter: `blur(${blurEntrada(frame, 0, 16)}px)`,
        }}
      >
        <Chip tam={44}>
          XV ideal · {corto} · J{jornada}
        </Chip>
      </div>
      <div
        style={{
          position: "absolute",
          left: SEGURA.x,
          right: SEGURA.x,
          top: SEGURA.arriba + 92,
          display: "flex",
          justifyContent: "space-between",
          alignItems: "baseline",
        }}
      >
        <Mascara p={pTitulo}>
          <div style={{ fontFamily: fuenteTitulo, fontWeight: 700, fontSize: 60, lineHeight: 1, color: c.acento, textTransform: "uppercase" }}>
            {titulo}
          </div>
        </Mascara>
        <div style={{ fontFamily: fuenteTitulo, fontWeight: 700, fontSize: 52, color: c.gris, opacity: entra(frame, PRIMERA, 12) }}>
          {frame < PRIMERA ? 0 : vistos}
          <span style={{ color: c.apagado }}>/15</span>
        </div>
      </div>
    </AbsoluteFill>
  );
};
