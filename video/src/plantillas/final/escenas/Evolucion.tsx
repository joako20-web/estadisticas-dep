import React from "react";
import { AbsoluteFill, interpolate, useCurrentFrame, useVideoConfig } from "remotion";
import { Chip, Escudo, SEGURA, Sfx, tamParaAncho, useColores, useReel } from "../../../base/comun";
import { EASE_IN_OUT, entra, golpe, muelle } from "../../../base/movimiento";
import { minutoFinal, useLados } from "../comun";
import type { Lado, PropsFinal } from "../tipos";

export const DUR_EVOLUCION = 168;
const DESDE = 16; // empieza a dibujarse
const DIBUJO = 112; // frames que tarda en recorrer los 80'
const X0 = SEGURA.x + 24;
const X1 = 1080 - SEGURA.x - 24;
const Y0 = 720;
const Y1 = 1300;

const clamp = { extrapolateLeft: "clamp", extrapolateRight: "clamp" } as const;

/** Minuto que marca el cursor en cada frame (curva suave, nunca lineal). */
const minutoEn = (frame: number, dom: number) =>
  interpolate(frame, [DESDE, DESDE + DIBUJO], [0, dom], { ...clamp, easing: EASE_IN_OUT });

/** Primer frame en que el cursor llega a ese minuto. */
const frameDe = (minuto: number, dom: number) => {
  for (let f = DESDE; f <= DESDE + DIBUJO; f++) if (minutoEn(f, dom) >= minuto) return f;
  return DESDE + DIBUJO;
};

// "Así fue": la diferencia del marcador minuto a minuto, dibujándose con un marcador en vivo.
export const Evolucion: React.FC = () => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const c = useColores();
  const props = useReel<PropsFinal>();
  const { evolucion, fuenteTitulo, fuenteTexto } = props;
  const lados = useLados();
  const dom = minutoFinal(props);

  // Escala vertical: asimétrica (si un equipo nunca fue por delante no se gasta media gráfica)
  const difs = [0, ...evolucion.map((a) => a.local - a.visitante)];
  const maxD = Math.max(...difs);
  const minD = Math.min(...difs);
  const mag = Math.max(maxD, -minD, 8);
  const hi = Math.max(maxD, mag * 0.3) * 1.14;
  const lo = Math.min(minD, -mag * 0.3) * 1.14;
  const x = (m: number) => X0 + (m / dom) * (X1 - X0);
  const y = (d: number) => Y0 + ((hi - d) / (hi - lo)) * (Y1 - Y0);
  const yCero = y(0);

  // Escalera: horizontal hasta el minuto de la anotación y salto vertical
  let d = "";
  let prev = 0;
  d += `M ${x(0)} ${yCero}`;
  for (const a of evolucion) {
    const nuevo = a.local - a.visitante;
    d += ` L ${x(a.minuto)} ${y(prev)} L ${x(a.minuto)} ${y(nuevo)}`;
    prev = nuevo;
  }
  d += ` L ${x(dom)} ${y(prev)}`;
  const area = `${d} L ${x(dom)} ${yCero} L ${x(0)} ${yCero} Z`;

  const m = minutoEn(frame, dom);
  const hechos = evolucion.filter((a) => a.minuto <= m);
  const ultimo = hechos[hechos.length - 1];
  const marL = ultimo?.local ?? 0;
  const marV = ultimo?.visitante ?? 0;
  const difAhora = marL - marV;
  const terminado = frame >= DESDE + DIBUJO;
  const cabeza = { x: x(m), y: y(difAhora) };

  // Momentos a señalar: la mayor ventaja de cada equipo (si fue de 5 o más)
  const picos: { a: (typeof evolucion)[number]; lado: Lado; dif: number }[] = [];
  if (maxD >= 5) {
    const a = evolucion.find((e) => e.local - e.visitante === maxD)!;
    picos.push({ a, lado: "L", dif: maxD });
  }
  if (minD <= -5) {
    const a = evolucion.find((e) => e.local - e.visitante === minD)!;
    picos.push({ a, lado: "V", dif: -minD });
  }

  const marcadorPop = (lado: Lado) => {
    const ult = [...hechos].reverse().find((a) => a.lado === lado);
    if (!ult) return 1;
    const f = frameDe(ult.minuto, dom);
    return 1 + 0.18 * (1 - entra(frame, f, 10));
  };

  // Fila de cada equipo (arriba el local, abajo el visitante) con su mayor ventaja,
  // que aparece cuando el trazo llega a ese momento.
  const Etiqueta: React.FC<{ lado: Lado; desde: number }> = ({ lado, desde }) => {
    const { eq, color } = lados[lado];
    const p = entra(frame, desde, 18);
    const pico = picos.find((x) => x.lado === lado);
    const fPico = pico ? frameDe(pico.a.minuto, dom) + 2 : 0;
    const arriba = lado === "L";
    return (
      <div
        style={{
          position: "absolute",
          left: SEGURA.x,
          right: SEGURA.x,
          ...(arriba ? { bottom: 1920 - Y0 + 22 } : { top: Y1 + 84 }),
          display: "flex",
          alignItems: "center",
          gap: 18,
          opacity: p,
          translate: `${(1 - p) * -60}px 0px`,
        }}
      >
        <span style={{ fontFamily: fuenteTitulo, fontSize: 44, color, lineHeight: 1 }}>{arriba ? "▲" : "▼"}</span>
        <Escudo src={eq.escudo} lado={70} />
        <span
          style={{
            flex: 1,
            fontFamily: fuenteTitulo,
            fontWeight: 700,
            fontSize: Math.max(44, tamParaAncho(eq.nombre.toUpperCase(), 440, 54, 2)),
            textTransform: "uppercase",
            color,
            lineHeight: 1,
          }}
        >
          {eq.nombre}
        </span>
        {pico ? (
          <div style={{ scale: String(golpe(frame, fps, fPico)), opacity: frame >= fPico ? 1 : 0, transformOrigin: "100% 50%" }}>
            <div
              style={{
                background: color,
                color: c.sobreAcento,
                fontFamily: fuenteTitulo,
                fontWeight: 700,
                fontSize: 54,
                lineHeight: 1,
                padding: "10px 20px 8px",
                whiteSpace: "nowrap",
                boxShadow: "0 12px 30px rgba(0,0,0,.35)",
              }}
            >
              +{pico.dif} <span style={{ fontSize: 44, fontWeight: 500 }}>· {pico.a.minuto}'</span>
            </div>
          </div>
        ) : null}
      </div>
    );
  };

  return (
    <AbsoluteFill>
      <Sfx nombre="whoosh" en={0} />
      <Sfx nombre="riser" en={DESDE + DIBUJO - 40} volumen={0.45} />
      {evolucion
        .filter((a) => a.tipo === "ensayo" || a.tipo === "ensayo_castigo" || a.tipo === "drop")
        .slice(0, 14)
        .map((a, i) => (
          <Sfx key={i} nombre="tic" en={frameDe(a.minuto, dom)} volumen={0.4} />
        ))}
      <Sfx nombre="pop" en={DESDE + DIBUJO + 2} />

      {/* rótulo y minuto */}
      <div style={{ position: "absolute", left: SEGURA.x, top: SEGURA.arriba + 30, translate: `${(1 - entra(frame, 0, 16)) * -700}px 0px` }}>
        <Chip tam={50}>Así fue</Chip>
      </div>
      <div
        style={{
          position: "absolute",
          right: SEGURA.x,
          top: SEGURA.arriba + 30,
          scale: String(golpe(frame, fps, 4)),
          opacity: frame >= 4 ? 1 : 0,
        }}
      >
        <Chip tam={50} invertido style={{ fontVariantNumeric: "tabular-nums", minWidth: 150, textAlign: "center" }}>
          {terminado ? "Final" : `${Math.floor(m)}'`}
        </Chip>
      </div>

      {/* marcador en vivo */}
      <div
        style={{
          position: "absolute",
          left: SEGURA.x,
          right: SEGURA.x,
          top: 400,
          height: 150,
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          gap: 34,
          opacity: entra(frame, 4, 16),
          translate: `0px ${(1 - entra(frame, 4, 18)) * 40}px`,
        }}
      >
        <Escudo src={lados.L.eq.escudo} lado={120} />
        {(["L", "V"] as Lado[]).map((lado, i) => (
          <React.Fragment key={lado}>
            {i === 1 ? (
              <span style={{ fontFamily: fuenteTitulo, fontWeight: 700, fontSize: 100, color: c.apagado, lineHeight: 1 }}>–</span>
            ) : null}
            <span
              style={{
                width: 200,
                textAlign: i === 0 ? "right" : "left",
                fontFamily: fuenteTitulo,
                fontWeight: 700,
                fontSize: 140,
                lineHeight: 1,
                fontVariantNumeric: "tabular-nums",
                color: terminado ? lados[lado].color : (lado === "L" ? difAhora > 0 : difAhora < 0) ? c.acento : c.texto,
                scale: String(marcadorPop(lado)),
              }}
            >
              {lado === "L" ? marL : marV}
            </span>
          </React.Fragment>
        ))}
        <Escudo src={lados.V.eq.escudo} lado={120} />
      </div>

      <Etiqueta lado="L" desde={8} />
      <Etiqueta lado="V" desde={12} />

      {/* gráfico */}
      <svg width={1080} height={1920} style={{ position: "absolute", inset: 0, overflow: "visible" }}>
        <defs>
          <clipPath id="fin-revela">
            <rect x={0} y={0} width={cabeza.x} height={1920} />
          </clipPath>
          <clipPath id="fin-arriba">
            <rect x={0} y={0} width={1080} height={yCero} />
          </clipPath>
          <clipPath id="fin-abajo">
            <rect x={0} y={yCero} width={1080} height={1920 - yCero} />
          </clipPath>
        </defs>

        {/* rejilla: 0', 20', 40' (descanso), 60', 80' */}
        {[0, 20, 40, 60, 80].map((min, i) => (
          <line
            key={min}
            x1={x(min)}
            x2={x(min)}
            y1={Y0}
            y2={Y0 + (Y1 - Y0) * entra(frame, 6 + i * 3, 20)}
            stroke={min === 40 ? c.gris : c.linea}
            strokeWidth={min === 40 ? 3 : 2}
            strokeDasharray={min === 40 ? "10 10" : undefined}
            opacity={0.8}
          />
        ))}
        <line
          x1={X0}
          x2={X0 + (X1 - X0) * entra(frame, 4, 22)}
          y1={yCero}
          y2={yCero}
          stroke={c.gris}
          strokeWidth={3}
        />

        <g clipPath="url(#fin-revela)">
          <path d={area} fill={lados.L.color} opacity={0.36} clipPath="url(#fin-arriba)" />
          <path d={area} fill={lados.V.color} opacity={0.22} clipPath="url(#fin-abajo)" />
          <path d={d} fill="none" stroke={c.texto} strokeWidth={7} strokeLinejoin="round" strokeLinecap="round" />
        </g>

        {/* una marca por anotación (más grande en los ensayos) */}
        {evolucion.map((a, i) => {
          const f = frameDe(a.minuto, dom);
          const s = muelle(frame, fps, f, 10, 220);
          const grande = a.tipo === "ensayo" || a.tipo === "ensayo_castigo";
          return (
            <circle
              key={i}
              cx={x(a.minuto)}
              cy={y(a.local - a.visitante)}
              r={(grande ? 14 : 8) * s}
              fill={lados[a.lado].color}
              stroke={c.fondo}
              strokeWidth={4}
            />
          );
        })}

        {/* aro sobre la mayor ventaja de cada equipo */}
        {picos.map(({ a, lado }) => {
          const f = frameDe(a.minuto, dom) + 2;
          const r = entra(frame, f, 16);
          return (
            <circle
              key={lado}
              cx={x(a.minuto)}
              cy={y(a.local - a.visitante)}
              r={14 + 16 * r}
              fill="none"
              stroke={lados[lado].color}
              strokeWidth={5}
              opacity={frame >= f ? 1 : 0}
            />
          );
        })}

        {/* cabeza del trazo */}
        {!terminado && frame >= DESDE ? (
          <>
            <line x1={cabeza.x} x2={cabeza.x} y1={Y0} y2={Y1} stroke={c.acento} strokeWidth={2} opacity={0.5} />
            <circle cx={cabeza.x} cy={cabeza.y} r={30} fill={c.acento} opacity={0.25} />
            <circle cx={cabeza.x} cy={cabeza.y} r={13} fill={c.acento} />
          </>
        ) : null}
      </svg>

      {/* eje de minutos */}
      {[0, 40, 80].map((min) => (
        <div
          key={min}
          style={{
            position: "absolute",
            top: Y1 + 18,
            left: x(min) - 150,
            width: 300,
            textAlign: min === 0 ? "left" : min === 80 ? "right" : "center",
            translate: min === 0 ? "150px 0px" : min === 80 ? "-150px 0px" : undefined,
            fontFamily: fuenteTexto,
            fontWeight: 700,
            fontSize: 44,
            color: c.apagado,
            textTransform: "uppercase",
            opacity: entra(frame, 10, 16),
          }}
        >
          {min === 40 ? "Descanso" : `${min}'`}
        </div>
      ))}

    </AbsoluteFill>
  );
};
