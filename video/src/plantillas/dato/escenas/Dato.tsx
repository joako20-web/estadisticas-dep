import React from "react";
import { AbsoluteFill, interpolate, useCurrentFrame, useVideoConfig } from "remotion";
import { Chip, Escudo, Mascara, SEGURA, Sfx, useColores, useReel } from "../../../base/comun";
import { EASE_OUT, STAGGER, blurEntrada, entra, golpe } from "../../../base/movimiento";
import type { PropsDato } from "../tipos";

export const DURACION_DATO = 186;
const LATIDO = 92; // segundo golpe del número mientras se lee (movimiento secundario)
const ANCHO = 1080 - 2 * SEGURA.x;

// El dato: número gigante con contador; unidad, titular y contexto tras máscara; escudo.
export const Dato: React.FC = () => {
  const frame = useCurrentFrame();
  const { fps, durationInFrames } = useVideoConfig();
  const c = useColores();
  const { dato, corto, jornada, fuenteTitulo, fuenteTexto } = useReel<PropsDato>();

  // el contador arranca a media cifra: en el primer frame ya hay un número fuerte, no un 0
  const contado = dato.valor === null ? 0 : Math.round(interpolate(frame, [0, 16], [Math.ceil(dato.valor * 0.5), dato.valor], { extrapolateRight: "clamp", easing: EASE_OUT }));
  const numero = dato.valor === null ? dato.numero : `${dato.antes}${contado}${dato.despues}`;
  // Oswald: ~0.5 em por cifra; se reserva el ancho del número final para que no baile
  const tamNumero = Math.min(560, Math.floor(ANCHO / (Math.max(1, dato.numero.length) * 0.52)));
  const titular = dato.titular.toUpperCase();
  const tamTitular = titular.length > 34 ? 72 : titular.length > 22 ? 84 : 100;
  const anchoTitular = dato.escudo ? ANCHO - 170 - 36 : ANCHO;
  const tamContexto = dato.contexto.length > 90 ? 46 : 52;
  const marca = entra(frame, 30, 18);

  return (
    <AbsoluteFill>
      <Sfx nombre="impacto" en={2} />
      <Sfx nombre="tic" en={8} />
      <Sfx nombre="tic" en={14} />
      <Sfx nombre="whoosh" en={26} volumen={0.7} />
      {dato.escudo ? <Sfx nombre="pop" en={38} volumen={0.8} /> : null}
      <Sfx nombre="tic" en={LATIDO} volumen={0.5} />

      <AbsoluteFill
        style={{
          background: c.acento,
          opacity: interpolate(frame, [0, 6], [1, 0], { extrapolateRight: "clamp", easing: EASE_OUT }),
        }}
      />

      {/* escudo gigante de fondo, girando despacio (fuera de las transiciones: el blend falla en ellas) */}
      {dato.escudo ? (
        <div
          style={{
            position: "absolute",
            right: -300,
            top: 260,
            opacity: interpolate(entra(frame, 16, 24) - entra(frame, durationInFrames - 24, 12), [0, 1], [0, 0.5]),
            mixBlendMode: "multiply",
            rotate: `${interpolate(frame, [0, durationInFrames], [-10, 4])}deg`,
            scale: String(interpolate(entra(frame, 16, 40), [0, 1], [1.25, 1])),
            filter: "grayscale(1) contrast(1.4)",
          }}
        >
          <Escudo src={dato.escudo} lado={900} />
        </div>
      ) : null}

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
        <Mascara p={entra(frame, 6, 16)} style={{ marginTop: 18 }}>
          <div style={{ fontFamily: fuenteTexto, fontWeight: 700, fontSize: 46, textTransform: "uppercase", letterSpacing: "0.08em", color: c.gris }}>
            El dato de la jornada
          </div>
        </Mascara>
      </div>

      <div style={{ position: "absolute", left: SEGURA.x, right: SEGURA.x, top: 440 }}>
        <div
          style={{
            fontFamily: fuenteTitulo,
            fontWeight: 700,
            fontSize: tamNumero,
            lineHeight: 0.9,
            height: tamNumero * 0.9,
            color: c.acento,
            letterSpacing: "-0.02em",
            whiteSpace: "nowrap",
            scale: String(
              golpe(frame, fps, 2) *
                interpolate(frame, [18, durationInFrames], [1, 1.05], { extrapolateLeft: "clamp" }) *
                interpolate(frame, [LATIDO, LATIDO + 4, LATIDO + 16], [1, 1.06, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp", easing: EASE_OUT }),
            ),
            transformOrigin: "0% 80%",
            textShadow: "0 18px 60px rgba(0,0,0,.35)",
          }}
        >
          {numero}
        </div>
        <div style={{ height: 10, width: `${entra(frame, 18, 18) * 100}%`, background: c.texto, marginTop: 28 }} />
        <Mascara p={entra(frame, 18 + STAGGER, 18)} style={{ marginTop: 24 }}>
          <div style={{ fontFamily: fuenteTexto, fontWeight: 700, fontSize: 56, lineHeight: 1.05, textTransform: "uppercase", letterSpacing: "0.03em", color: c.gris }}>
            {dato.unidad}
          </div>
        </Mascara>
      </div>

      <div style={{ position: "absolute", left: SEGURA.x, right: SEGURA.x, top: 1120 }}>
        <div style={{ display: "flex", alignItems: "center", gap: 36 }}>
          {dato.escudo ? (
            <div style={{ scale: String(golpe(frame, fps, 34)) }}>
              <Escudo src={dato.escudo} lado={170} borde={c.acento} />
            </div>
          ) : null}
          <Mascara p={entra(frame, 30, 20)} style={{ width: anchoTitular }}>
            <div style={{ fontFamily: fuenteTitulo, fontWeight: 700, fontSize: tamTitular, lineHeight: 0.98, textTransform: "uppercase", color: c.texto }}>
              {dato.titular}
            </div>
          </Mascara>
        </div>
        {dato.contexto ? (
          <div style={{ display: "flex", gap: 24, marginTop: 44 }}>
            <div style={{ width: 8, background: c.acento, scale: `1 ${marca}`, transformOrigin: "50% 0%", flexShrink: 0 }} />
            <Mascara p={entra(frame, 44, 20)} style={{ flex: 1 }}>
              <div style={{ fontFamily: fuenteTexto, fontWeight: 500, fontSize: tamContexto, lineHeight: 1.18, color: c.texto, opacity: 0.88 }}>
                {dato.contexto}
              </div>
            </Mascara>
          </div>
        ) : null}
      </div>
    </AbsoluteFill>
  );
};
