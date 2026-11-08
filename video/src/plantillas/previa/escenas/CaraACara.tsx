import React from "react";
import type { Lado, PropsPrevia } from "../tipos";
import { textoDia } from "../tipos";
import { AbsoluteFill, interpolate, useCurrentFrame, useVideoConfig } from "remotion";
import { Chip, Escudo, Mascara, SEGURA, Sfx, tamParaAncho, useColores, useReel } from "../../../base/comun";
import { EASE_OUT, STAGGER, blurEntrada, entra, golpe, muelle } from "../../../base/movimiento";
import { Pin } from "./Pin";

const ANCHO_LADO = 380; // columna de cada equipo
const LADO_ESCUDO = 280;
const TOP_ESCUDOS = 640;

// Un equipo del cara a cara: escudo que entra de su lado, posición y nombre.
const Rival: React.FC<{ eq: Lado; desde: number; lado: 1 | -1 }> = ({ eq, desde, lado }) => {
  const frame = useCurrentFrame();
  const { fps, durationInFrames } = useVideoConfig();
  const c = useColores();
  const { fuenteTitulo } = useReel<PropsPrevia>();
  const m = muelle(frame, fps, desde, 14, 190);
  const nombre = eq.nombre.toUpperCase();
  // nombres largos: hasta 3 líneas antes que encoger la letra
  const tam = Math.max(tamParaAncho(nombre, ANCHO_LADO - 20, 76, 2), tamParaAncho(nombre, ANCHO_LADO - 20, 56, 3));
  // flotación lenta y opuesta entre los dos escudos (movimiento secundario)
  const flota = Math.sin((frame / durationInFrames) * Math.PI * 2) * 8 * lado;
  return (
    <div style={{ width: ANCHO_LADO, display: "flex", flexDirection: "column", alignItems: "center", textAlign: "center" }}>
      <div
        style={{
          translate: `${(1 - m) * 760 * lado}px ${flota}px`,
          rotate: `${(1 - m) * 18 * lado}deg`,
          filter: `blur(${blurEntrada(frame, desde, 12, 12)}px)`,
          scale: String(golpe(frame, fps, desde + 7)),
        }}
      >
        <Escudo src={eq.escudo} lado={LADO_ESCUDO} borde={c.acento} />
      </div>
      {eq.pos ? (
        <div style={{ marginTop: 34, scale: String(golpe(frame, fps, desde + 18)) }}>
          <Chip tam={44} invertido style={{ paddingLeft: 26, paddingRight: 50 }}>
            {eq.pos}º{eq.pt !== null ? ` · ${eq.pt} pts` : ""}
          </Chip>
        </div>
      ) : (
        <div style={{ height: 34 }} />
      )}
      <Mascara p={entra(frame, desde + 20, 18)} style={{ marginTop: 22, width: "100%" }}>
        <div
          style={{
            fontFamily: fuenteTitulo,
            fontWeight: 700,
            fontSize: tam,
            lineHeight: 1,
            color: c.texto,
            textTransform: "uppercase",
          }}
        >
          {eq.nombre}
        </div>
      </Mascara>
    </div>
  );
};

// Gancho: el partido destacado, cara a cara. Los dos escudos chocan en el primer
// tercio de segundo y el VS cae justo después; el contexto llega detrás.
export const CaraACara: React.FC = () => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const c = useColores();
  const { destacado, corto, jornada, fuenteTitulo, fuenteTexto } = useReel<PropsPrevia>();
  if (!destacado) return null;

  const vsEn = 10;
  const vs = golpe(frame, fps, vsEn);
  const rayo = entra(frame, vsEn - 2, 14);
  const info = entra(frame, 34, 18);

  return (
    <AbsoluteFill>
      <Sfx nombre="whoosh" en={0} volumen={0.9} />
      <Sfx nombre="impacto" en={7} />
      <Sfx nombre="pop" en={vsEn + 1} volumen={0.8} />
      <Sfx nombre="tic" en={36} volumen={0.7} />

      {/* Destello de acento al arrancar (enlaza con el final para el bucle) */}
      <AbsoluteFill
        style={{
          background: c.acento,
          opacity: interpolate(frame, [0, 6], [1, 0], { extrapolateRight: "clamp", easing: EASE_OUT }),
        }}
      />

      <div style={{ position: "absolute", left: SEGURA.x, right: SEGURA.x, top: SEGURA.arriba + 30 }}>
        <div
          style={{
            translate: `${interpolate(entra(frame, 2, 14), [0, 1], [-900, 0])}px 0px`,
            filter: `blur(${blurEntrada(frame, 2, 14)}px)`,
          }}
        >
          <Chip tam={50}>
            {corto} · Jornada {jornada}
          </Chip>
        </div>
        <div style={{ marginTop: 26 }}>
          <Mascara p={entra(frame, 12, 18)}>
            <div style={{ fontFamily: fuenteTitulo, fontWeight: 700, fontSize: 104, lineHeight: 0.98, color: c.texto, textTransform: "uppercase" }}>
              El partido
            </div>
          </Mascara>
          <Mascara p={entra(frame, 12 + STAGGER, 18)}>
            <div style={{ fontFamily: fuenteTitulo, fontWeight: 700, fontSize: 104, lineHeight: 0.98, color: c.acento, textTransform: "uppercase" }}>
              de la jornada
            </div>
          </Mascara>
        </div>
      </div>

      {/* franja diagonal que cruza por detrás del choque */}
      <div
        style={{
          position: "absolute",
          left: -200,
          right: -200,
          top: TOP_ESCUDOS + LADO_ESCUDO / 2 - 60,
          height: 120,
          background: c.panel,
          rotate: "-8deg",
          clipPath: `inset(0 ${(1 - rayo) * 50}% 0 ${(1 - rayo) * 50}%)`,
        }}
      />

      <div
        style={{
          position: "absolute",
          left: SEGURA.x,
          right: SEGURA.x,
          top: TOP_ESCUDOS,
          display: "flex",
          justifyContent: "space-between",
          alignItems: "flex-start",
        }}
      >
        <Rival eq={destacado.local} desde={0} lado={-1} />
        <Rival eq={destacado.visitante} desde={STAGGER - 1} lado={1} />
      </div>

      {/* VS en el centro, sobre el choque */}
      <div
        style={{
          position: "absolute",
          left: 0,
          right: 0,
          top: TOP_ESCUDOS + LADO_ESCUDO / 2 - 80,
          display: "flex",
          justifyContent: "center",
          pointerEvents: "none",
        }}
      >
        <div
          style={{
            fontFamily: fuenteTitulo,
            fontWeight: 700,
            fontSize: 150,
            lineHeight: 1,
            color: c.acento,
            fontStyle: "italic",
            scale: String(vs),
            rotate: `${interpolate(entra(frame, vsEn, 16), [0, 1], [-20, -6])}deg`,
            opacity: frame >= vsEn ? 1 : 0,
            textShadow: `0 0 0 ${c.fondo}, 0 12px 40px rgba(0,0,0,.6)`,
            WebkitTextStroke: `6px ${c.fondo}`,
            paintOrder: "stroke fill",
          }}
        >
          VS
        </div>
      </div>

      {/* cuándo y dónde */}
      <div
        style={{
          position: "absolute",
          left: SEGURA.x,
          right: SEGURA.x,
          top: 1290,
          display: "flex",
          flexDirection: "column",
          alignItems: "center",
          gap: 18,
          opacity: info,
          translate: `0px ${interpolate(info, [0, 1], [40, 0])}px`,
        }}
      >
        <div style={{ display: "flex", alignItems: "center", gap: 26 }}>
          <Chip tam={52} style={{ whiteSpace: "nowrap" }}>{textoDia(destacado)}</Chip>
          {destacado.hora ? (
            <div style={{ fontFamily: fuenteTitulo, fontWeight: 700, fontSize: 92, lineHeight: 1, color: c.texto }}>{destacado.hora}</div>
          ) : null}
        </div>
        {destacado.campo ? (
          <div
            style={{
              display: "flex",
              alignItems: "center",
              gap: 14,
              fontFamily: fuenteTexto,
              fontWeight: 700,
              fontSize: 44,
              lineHeight: 1.1,
              color: c.gris,
              maxWidth: "100%",
              textAlign: "center",
            }}
          >
            <Pin lado={44} />
            <span>{destacado.campo}</span>
          </div>
        ) : null}
      </div>
    </AbsoluteFill>
  );
};
