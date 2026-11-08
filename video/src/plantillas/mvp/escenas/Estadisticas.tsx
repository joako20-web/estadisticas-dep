import React from "react";
import { AbsoluteFill, Easing, interpolate, useCurrentFrame, useVideoConfig } from "remotion";
import { Chip, Escudo, Mascara, SEGURA, Sfx, tamParaAncho, useColores, useReel } from "../../../base/comun";
import { STAGGER, blurEntrada, cuenta, entra, golpe, muelle } from "../../../base/movimiento";
import type { PropsMvp } from "../tipos";

const ANCHO = 1080 - 2 * SEGURA.x;
const HERO = 24; // frame en que arranca el contador grande
const TILES = 50;
const PARTIDO = 86;

/** Contador con decimales (para la valoración). */
const cuentaDecimal = (frame: number, desde: number, valor: number, dur = 18) =>
  interpolate(frame, [desde, desde + dur], [0, valor], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
    easing: Easing.bezier(0.25, 1, 0.5, 1),
  }).toFixed(1);

// Los números: puntos (o valoración si no anotó) en grande, el desglose en fichas y el partido.
export const Estadisticas: React.FC = () => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const c = useColores();
  const { jugador: j, fuenteTitulo, fuenteTexto } = useReel<PropsMvp>();
  if (!j) return null;

  const anota = j.puntos > 0;
  const heroValor = anota ? String(cuenta(frame, HERO, j.puntos, 20)) : cuentaDecimal(frame, HERO, j.nota, 20);
  const heroP = entra(frame, HERO - 6, 16);
  const n = j.stats.length;
  const hueco = 20;
  const anchoTile = (ANCHO - hueco * (n - 1)) / Math.max(1, n);
  const p = j.partido;
  const tamRival = p ? tamParaAncho(p.rival.toUpperCase(), ANCHO - 60 - 150 - 36 - 60, 80, 2) : 0;

  return (
    <AbsoluteFill>
      <Sfx nombre="whoosh" en={0} volumen={0.8} />
      <Sfx nombre="impacto" en={HERO + 18} volumen={0.8} />
      {j.stats.map((s, i) => (
        <Sfx key={s.clave} nombre="tic" en={TILES + i * STAGGER + 4} volumen={0.6} />
      ))}
      {p ? <Sfx nombre="pop" en={PARTIDO + 4} volumen={0.7} /> : null}

      <div
        style={{
          position: "absolute",
          left: SEGURA.x,
          top: SEGURA.arriba + 30,
          translate: `${(1 - entra(frame, 0, 16)) * -800}px 0px`,
          filter: `blur(${blurEntrada(frame, 0, 16)}px)`,
        }}
      >
        <Chip tam={50}>{j.corto} · sus números</Chip>
      </div>

      {/* número protagonista */}
      <div
        style={{
          position: "absolute",
          left: SEGURA.x,
          right: SEGURA.x,
          top: 360,
          display: "flex",
          alignItems: "flex-end",
          gap: 28,
          opacity: heroP,
          translate: `0px ${(1 - heroP) * 90}px`,
        }}
      >
        <div
          style={{
            fontFamily: fuenteTitulo,
            fontWeight: 700,
            fontSize: anota ? 380 : 300,
            lineHeight: 0.82,
            color: c.acento,
            letterSpacing: "-0.03em",
            // golpe al terminar de contar (antes, tamaño normal)
            scale: String(frame < HERO + 18 ? 1 : golpe(frame, fps, HERO + 18)),
            transformOrigin: "0% 100%",
            textShadow: "0 18px 60px rgba(0,0,0,.35)",
          }}
        >
          {heroValor}
        </div>
        <div style={{ paddingBottom: 18 }}>
          <div style={{ fontFamily: fuenteTitulo, fontWeight: 700, fontSize: 96, lineHeight: 0.9, color: c.texto, textTransform: "uppercase" }}>
            {anota ? (j.puntos === 1 ? "Punto" : "Puntos") : "Nota"}
          </div>
          <div style={{ fontFamily: fuenteTexto, fontWeight: 700, fontSize: 44, color: c.gris, textTransform: "uppercase", marginTop: 8 }}>
            {anota ? `Nota ${j.nota.toFixed(1)}` : "Valoración"}
          </div>
        </div>
      </div>

      {/* desglose */}
      <div style={{ position: "absolute", left: SEGURA.x, top: 760, display: "flex", gap: hueco }}>
        {j.stats.map((s, i) => {
          const desde = TILES + i * STAGGER;
          const m = muelle(frame, fps, desde, 12, 170);
          const cero = s.valor === 0;
          return (
            <div
              key={s.clave}
              style={{
                width: anchoTile,
                height: 290,
                background: c.panel,
                borderTop: `10px solid ${cero ? c.linea : c.acento}`,
                padding: "26px 0 0 28px",
                translate: `0px ${(1 - m) * 240}px`,
                opacity: entra(frame, desde, 10),
              }}
            >
              <div style={{ fontFamily: fuenteTitulo, fontWeight: 700, fontSize: 150, lineHeight: 0.9, color: cero ? c.apagado : c.texto }}>
                {cuenta(frame, desde + 4, s.valor, 14)}
              </div>
              <div style={{ fontFamily: fuenteTexto, fontWeight: 700, fontSize: 44, color: c.gris, textTransform: "uppercase", marginTop: 14 }}>
                {s.texto}
              </div>
            </div>
          );
        })}
      </div>

      {/* rival y resultado */}
      {p ? (
        <div
          style={{
            position: "absolute",
            left: SEGURA.x,
            right: SEGURA.x,
            top: 1110,
            padding: "30px 30px 34px",
            background: c.panel,
            clipPath: `inset(0 ${(1 - entra(frame, PARTIDO, 18)) * 100}% 0 0)`,
          }}
        >
          <Mascara p={entra(frame, PARTIDO + 4, 14)}>
            <div style={{ fontFamily: fuenteTexto, fontWeight: 700, fontSize: 44, color: c.gris, textTransform: "uppercase", letterSpacing: "0.08em" }}>
              Contra
            </div>
          </Mascara>
          <div style={{ display: "flex", alignItems: "center", gap: 36, marginTop: 16 }}>
            <div style={{ scale: String(golpe(frame, fps, PARTIDO + 6)) }}>
              <Escudo src={p.escudoRival} lado={150} />
            </div>
            <Mascara p={entra(frame, PARTIDO + 8, 16)} style={{ flex: 1 }}>
              <div style={{ fontFamily: fuenteTitulo, fontWeight: 700, fontSize: tamRival, lineHeight: 0.98, color: c.texto, textTransform: "uppercase" }}>
                {p.rival}
              </div>
            </Mascara>
          </div>
          {p.texto ? (
            <div
              style={{
                marginTop: 28,
                translate: `${(1 - entra(frame, PARTIDO + 16, 16)) * -900}px 0px`,
              }}
            >
              <Chip tam={64} invertido={p.letra !== "G"}>
                {p.texto}
                {p.propios !== null ? ` ${p.propios}-${p.contra}` : ""}
              </Chip>
            </div>
          ) : null}
        </div>
      ) : null}
    </AbsoluteFill>
  );
};
