import React from "react";
import { AbsoluteFill, Img, interpolate, useCurrentFrame, useVideoConfig } from "remotion";
import { Chip, Escudo, Mascara, SEGURA, Sfx, useColores, useReel } from "../../../base/comun";
import { EASE_IN_OUT, STAGGER, blurEntrada, entra, golpe, muelle } from "../../../base/movimiento";
import type { FichaJugador } from "../tipos";

const ANCHO = 1080 - 2 * SEGURA.x;
const ARRIBA = 360; // bloque visual (foto o escudo)
const ALTO_VISUAL = 620;

/** Tamaño del apellido: en una línea si cabe a ≥96 px; si no, en dos. */
export const medidaApellido = (texto: string, max = 150) => {
  const t = texto.toUpperCase();
  const una = Math.floor(ANCHO / (t.length * 0.53));
  if (una >= 96 || !t.includes(" ")) return { tam: Math.max(64, Math.min(max, una)), lineas: 1 };
  const palabras = t.split(" ");
  // mejor corte en dos líneas
  let mejor = t.length;
  for (let i = 1; i < palabras.length; i++) {
    mejor = Math.min(mejor, Math.max(palabras.slice(0, i).join(" ").length, palabras.slice(i).join(" ").length));
  }
  return { tam: Math.max(64, Math.min(120, Math.floor(ANCHO / (mejor * 0.53)))), lineas: 2 };
};

/** Apellido letra a letra (las palabras no se parten). */
export const LetraALetra: React.FC<{ texto: string; desde: number; tam: number; color: string }> = ({
  texto,
  desde,
  tam,
  color,
}) => {
  const frame = useCurrentFrame();
  const { fuenteTitulo } = useReel();
  let i = 0;
  return (
    <div
      style={{
        fontFamily: fuenteTitulo,
        fontWeight: 700,
        fontSize: tam,
        lineHeight: 0.95,
        color,
        display: "flex",
        flexWrap: "wrap",
        columnGap: "0.22em",
      }}
    >
      {texto
        .toUpperCase()
        .split(" ")
        .map((palabra, w) => (
          <span key={w} style={{ display: "inline-flex", whiteSpace: "nowrap" }}>
            {palabra.split("").map((l, k) => {
              const p = entra(frame, desde + i++ * 1.5, 14);
              return (
                <span key={k} style={{ display: "inline-block", opacity: p, translate: `0px ${(1 - p) * 60}px` }}>
                  {l}
                </span>
              );
            })}
          </span>
        ))}
    </div>
  );
};

/** Dorsal gigante en hueco (solo contorno de acento). */
const Dorsal: React.FC<{ n: number | null; desde: number }> = ({ n, desde }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const c = useColores();
  const { fuenteTitulo, fuenteTexto } = useReel();
  if (!n) return null;
  const m = muelle(frame, fps, desde, 14, 150);
  return (
    <div style={{ position: "absolute", right: SEGURA.x, top: ARRIBA - 20, textAlign: "right", translate: `${(1 - m) * 500}px 0px` }}>
      <div style={{ fontFamily: fuenteTexto, fontWeight: 700, fontSize: 44, letterSpacing: "0.12em", color: c.gris, textTransform: "uppercase" }}>
        Dorsal
      </div>
      <div
        style={{
          fontFamily: fuenteTitulo,
          fontWeight: 700,
          fontSize: 340,
          lineHeight: 0.9,
          color: "transparent",
          WebkitTextStroke: `7px ${c.acento}`,
          letterSpacing: "-0.03em",
        }}
      >
        {n}
      </div>
    </div>
  );
};

/** Foto en tarjeta con bloque de acento desplazado; se descubre de abajo arriba. */
const Foto: React.FC<{ j: FichaJugador; desde: number }> = ({ j, desde }) => {
  const frame = useCurrentFrame();
  const { fps, durationInFrames } = useVideoConfig();
  const c = useColores();
  const ancho = Math.round(ALTO_VISUAL * 0.8);
  const revela = entra(frame, desde, 22);
  const bloque = entra(frame, desde - 4, 20);
  return (
    <div style={{ position: "absolute", left: SEGURA.x, top: ARRIBA, width: ancho, height: ALTO_VISUAL }}>
      <div
        style={{
          position: "absolute",
          inset: 0,
          background: c.acento,
          translate: `${bloque * 26}px ${bloque * 26}px`,
          opacity: bloque,
        }}
      />
      <div
        style={{
          position: "absolute",
          inset: 0,
          overflow: "hidden",
          clipPath: `inset(${(1 - revela) * 100}% 0 0 0)`,
          background: c.panel,
        }}
      >
        <Img
          src={j.foto}
          style={{
            width: "100%",
            height: "100%",
            objectFit: "cover",
            filter: "contrast(1.08) saturate(1.06)", // las fotos de el origen A suelen venir lavadas
            // Ken Burns lento durante toda la escena
            scale: String(interpolate(frame, [desde, durationInFrames], [1.14, 1.0], { extrapolateLeft: "clamp", easing: EASE_IN_OUT })),
          }}
        />
        <div style={{ position: "absolute", inset: 0, background: `linear-gradient(180deg, transparent 55%, ${c.fondo}cc 100%)` }} />
      </div>
      <div style={{ position: "absolute", right: -60, bottom: -50, scale: String(golpe(frame, fps, desde + 16)) }}>
        <Escudo src={j.escudo} lado={190} borde={c.acento} />
      </div>
    </div>
  );
};

/** Sin foto de calidad: escudo grande con un aro de acento que gira. */
const EscudoGrande: React.FC<{ j: FichaJugador; desde: number }> = ({ j, desde }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const c = useColores();
  const lado = 470;
  const aro = entra(frame, desde + 4, 24);
  const r = lado / 2 + 34;
  return (
    <div style={{ position: "absolute", left: SEGURA.x + 10, top: ARRIBA + 50, width: lado, height: lado }}>
      <svg
        width={2 * r + 20}
        height={2 * r + 20}
        style={{ position: "absolute", left: lado / 2 - r - 10, top: lado / 2 - r - 10, rotate: `${frame * 0.6}deg` }}
      >
        <circle
          cx={r + 10}
          cy={r + 10}
          r={r}
          fill="none"
          stroke={c.acento}
          strokeWidth={8}
          strokeDasharray={`${2 * Math.PI * r * 0.18} ${2 * Math.PI * r * 0.07}`}
          strokeDashoffset={(1 - aro) * 2 * Math.PI * r}
          opacity={aro}
        />
      </svg>
      <div style={{ scale: String(golpe(frame, fps, desde)), rotate: `${interpolate(entra(frame, desde, 24), [0, 1], [-20, 0])}deg` }}>
        <Escudo src={j.escudo} lado={lado} />
      </div>
    </div>
  );
};

// Presentación del jugador: foto (o escudo grande), dorsal en hueco y nombre letra a letra.
export const Presentacion: React.FC<{ j: FichaJugador; chip: string; extra?: React.ReactNode; apellido?: string }> = ({
  j,
  chip,
  extra,
  apellido,
}) => {
  const frame = useCurrentFrame();
  const { fuenteTexto } = useReel();
  const c = useColores();
  const texto = apellido ?? j.apellidos;
  const { tam, lineas } = medidaApellido(texto);
  const nombreArriba = ARRIBA + ALTO_VISUAL + (j.foto ? 70 : 40);
  const alturaApellido = tam * 0.95 * lineas;
  const sub = [j.posicion, j.dorsal && j.posicion ? `Nº ${j.dorsal}` : ""].filter(Boolean).join(" · ");

  return (
    <AbsoluteFill>
      <Sfx nombre="whoosh" en={0} />
      <Sfx nombre="impacto" en={10} volumen={0.7} />

      <div
        style={{
          position: "absolute",
          left: SEGURA.x,
          top: SEGURA.arriba + 30,
          translate: `${(1 - entra(frame, 0, 16)) * -800}px 0px`,
          filter: `blur(${blurEntrada(frame, 0, 16)}px)`,
        }}
      >
        <Chip tam={50}>{chip}</Chip>
      </div>

      {j.foto ? <Foto j={j} desde={6} /> : <EscudoGrande j={j} desde={6} />}
      <Dorsal n={j.dorsal} desde={14} />
      {extra ? <div style={{ position: "absolute", right: SEGURA.x, top: ARRIBA + 360, textAlign: "right" }}>{extra}</div> : null}

      <div style={{ position: "absolute", left: SEGURA.x, right: SEGURA.x, top: nombreArriba }}>
        <Mascara p={entra(frame, 18, 16)}>
          <div style={{ fontFamily: fuenteTexto, fontWeight: 700, fontSize: 56, textTransform: "uppercase", color: c.gris, letterSpacing: "0.04em" }}>
            {j.nombre || " "}
          </div>
        </Mascara>
        <div style={{ minHeight: alturaApellido, marginTop: 4 }}>
          <LetraALetra texto={texto} desde={22} tam={tam} color={c.texto} />
        </div>
        <div style={{ height: 12, width: `${entra(frame, 30, 20) * 55}%`, background: c.acento, marginTop: 22 }} />
        <Mascara p={entra(frame, 34 + STAGGER, 16)} style={{ marginTop: 22 }}>
          <div style={{ fontFamily: fuenteTexto, fontWeight: 700, fontSize: 48, lineHeight: 1.1, color: c.texto, textTransform: "uppercase" }}>
            {j.equipo}
            {sub ? <div style={{ color: c.gris, fontSize: 44 }}>{sub}</div> : null}
          </div>
        </Mascara>
      </div>
    </AbsoluteFill>
  );
};
