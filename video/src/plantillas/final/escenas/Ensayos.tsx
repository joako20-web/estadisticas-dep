import React from "react";
import { AbsoluteFill, interpolate, useCurrentFrame, useVideoConfig } from "remotion";
import { Chip, Escudo, SEGURA, Sfx, useColores, useReel } from "../../../base/comun";
import { EASE_IN_OUT, entra, golpe, muelle } from "../../../base/movimiento";
import { minutoFinal, useLados } from "../comun";
import type { Lado, PropsFinal } from "../tipos";

export const DUR_ENSAYOS = 126;
const CENTRO = 540;
const YT = 590; // minuto 0
const YB = 1450; // minuto 80
const CRECE_DESDE = 8;
const CRECE = 56; // lo que tarda la línea en llegar al 80'
const ALTO = 60; // separación mínima entre rótulos del mismo lado
const SEP = 58; // del eje al rótulo

const clamp = { extrapolateLeft: "clamp", extrapolateRight: "clamp" } as const;
const avance = (frame: number) => interpolate(frame, [CRECE_DESDE, CRECE_DESDE + CRECE], [0, 1], { ...clamp, easing: EASE_IN_OUT });

/** Reparte los rótulos de un lado para que no se pisen, lo más cerca posible de su minuto. */
const repartir = (ys: number[]) => {
  const out = [...ys];
  for (let i = 1; i < out.length; i++) out[i] = Math.max(out[i], out[i - 1] + ALTO);
  for (let i = out.length - 1; i >= 0; i--) out[i] = Math.min(out[i], i === out.length - 1 ? YB : out[i + 1] - ALTO);
  return out;
};

// Línea de tiempo vertical: cada ensayo en su minuto, a la izquierda el local y a la derecha el visitante.
export const Ensayos: React.FC = () => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const c = useColores();
  const props = useReel<PropsFinal>();
  const { ensayos, fuenteTitulo, fuenteTexto } = props;
  const lados = useLados();
  const dom = minutoFinal(props);
  const y = (m: number) => YT + (m / dom) * (YB - YT);
  const p = avance(frame);
  const frameDe = (m: number) => {
    for (let f = CRECE_DESDE; f <= CRECE_DESDE + CRECE; f++) if (avance(f) >= m / dom) return f;
    return CRECE_DESDE + CRECE;
  };

  const filas = (["L", "V"] as Lado[]).flatMap((lado) => {
    const suyos = ensayos.filter((e) => e.lado === lado).sort((a, b) => a.minuto - b.minuto);
    const pos = repartir(suyos.map((e) => y(e.minuto)));
    return suyos.map((e, i) => ({ ...e, yRotulo: pos[i], desde: frameDe(e.minuto) }));
  });

  return (
    <AbsoluteFill>
      <Sfx nombre="whoosh" en={0} />
      {filas.slice(0, 16).map((f, i) => (
        <Sfx key={i} nombre="tic" en={f.desde} volumen={0.45} />
      ))}

      <div style={{ position: "absolute", left: SEGURA.x, top: SEGURA.arriba + 30, translate: `${(1 - entra(frame, 0, 16)) * -700}px 0px` }}>
        <Chip tam={50}>Los ensayos</Chip>
      </div>

      {/* cabecera: escudo y ensayos de cada equipo (cuentan a medida que salen) */}
      {(["L", "V"] as Lado[]).map((lado, i) => {
        const { eq, color } = lados[lado];
        const n = filas.filter((f) => f.lado === lado && frame >= f.desde).length;
        const izq = lado === "L";
        return (
          <div
            key={lado}
            style={{
              position: "absolute",
              top: 380,
              left: izq ? SEGURA.x : CENTRO + 40,
              right: izq ? CENTRO + 40 : SEGURA.x,
              display: "flex",
              flexDirection: izq ? "row" : "row-reverse",
              alignItems: "center",
              gap: 24,
              scale: String(golpe(frame, fps, 3 + i * 4)),
              opacity: frame >= 3 + i * 4 ? 1 : 0,
            }}
          >
            <Escudo src={eq.escudo} lado={120} borde={eq.gana ? c.acento : undefined} />
            <div style={{ display: "flex", flexDirection: "column", alignItems: izq ? "flex-start" : "flex-end" }}>
              <span style={{ fontFamily: fuenteTitulo, fontWeight: 700, fontSize: 110, lineHeight: 0.9, color, fontVariantNumeric: "tabular-nums" }}>
                {n}
              </span>
              <span style={{ fontFamily: fuenteTexto, fontWeight: 700, fontSize: 44, color: c.gris, textTransform: "uppercase" }}>
                {filas.filter((f) => f.lado === lado).length === 1 ? "ensayo" : "ensayos"}
              </span>
            </div>
          </div>
        );
      })}

      <svg width={1080} height={1920} style={{ position: "absolute", inset: 0 }}>
        {/* eje */}
        <line x1={CENTRO} x2={CENTRO} y1={YT} y2={YT + (YB - YT) * p} stroke={c.gris} strokeWidth={6} strokeLinecap="round" />
        {/* conectores y puntos */}
        {filas.map((f, i) => {
          const s = muelle(frame, fps, f.desde, 10, 220);
          const lado = f.lado === "L" ? -1 : 1;
          const yd = y(f.minuto);
          const l = entra(frame, f.desde, 12);
          return (
            <g key={i} opacity={frame >= f.desde ? 1 : 0}>
              <polyline
                points={`${CENTRO},${yd} ${CENTRO + lado * 22},${yd} ${CENTRO + lado * (22 + (SEP - 30) * l)},${f.yRotulo}`}
                fill="none"
                stroke={lados[f.lado].color}
                strokeWidth={3}
                opacity={0.7}
              />
              <circle cx={CENTRO} cy={yd} r={15 * s} fill={lados[f.lado].color} stroke={c.fondo} strokeWidth={5} />
            </g>
          );
        })}
      </svg>

      {/* marcas de 0', descanso y final sobre el eje */}
      {[
        { m: 0, t: "0'" },
        { m: 40, t: "40'" },
        { m: dom, t: `${dom}'` },
      ].map(({ m, t }) => (
        <div
          key={t}
          style={{
            position: "absolute",
            left: CENTRO - 60,
            width: 120,
            top: y(m) - 30,
            textAlign: "center",
            fontFamily: fuenteTitulo,
            fontWeight: 700,
            fontSize: 44,
            lineHeight: "60px",
            color: c.apagado,
            background: c.fondo,
            opacity: p >= m / dom ? 1 : 0,
            scale: String(golpe(frame, fps, frameDe(m))),
          }}
        >
          {t}
        </div>
      ))}

      {/* rótulos: jugador y minuto, pegados al eje */}
      {filas.map((f, i) => {
        const izq = f.lado === "L";
        const l = entra(frame, f.desde + 1, 14);
        return (
          <div
            key={i}
            style={{
              position: "absolute",
              top: f.yRotulo - ALTO / 2,
              height: ALTO,
              left: izq ? SEGURA.x : CENTRO + SEP,
              right: izq ? 1080 - CENTRO + SEP : SEGURA.x,
              display: "flex",
              flexDirection: izq ? "row-reverse" : "row",
              alignItems: "center",
              gap: 14,
              whiteSpace: "nowrap",
              opacity: l,
              translate: `${(1 - l) * (izq ? 50 : -50)}px 0px`,
            }}
          >
            <span style={{ fontFamily: fuenteTitulo, fontWeight: 700, fontSize: 46, color: lados[f.lado].color, fontVariantNumeric: "tabular-nums" }}>
              {f.minuto}'
            </span>
            <span style={{ fontFamily: fuenteTitulo, fontWeight: 500, fontSize: 44, color: c.texto, overflow: "hidden" }}>
              {f.castigo ? "De castigo" : f.jugador}
            </span>
          </div>
        );
      })}
    </AbsoluteFill>
  );
};
