import React from "react";
import { AbsoluteFill, interpolate, useCurrentFrame, useVideoConfig } from "remotion";
import { Chip, Escudo, Mascara, SEGURA, Sfx, useColores, useReel } from "../../../base/comun";
import { EASE_OUT, STAGGER, blurEntrada, cuenta, entra, golpe } from "../../../base/movimiento";
import type { PropsRankings } from "../tipos";

const ANCHO = 1080 - 2 * SEGURA.x;
const SINGULAR: Record<string, string> = {
  anotadores: "Máximo anotador",
  ensayadores: "Máximo ensayador",
  pateadores: "Mejor pateador",
};

// Gancho: la cifra del líder del primer ranking en el primer segundo.
export const Gancho: React.FC = () => {
  const frame = useCurrentFrame();
  const { fps, durationInFrames } = useVideoConfig();
  const c = useColores();
  const { bloques, corto, temporada, fuenteTitulo, fuenteTexto } = useReel<PropsRankings>();
  const b = bloques[0];
  const top = b?.filas[0];
  if (!b || !top) return null;

  // apellidos muy largos (tres palabras): los recortados, para no pasar de dos líneas
  const texto = top.apellidos.length > 16 && top.corto ? top.corto : top.apellidos;
  const apellidos = texto.toUpperCase();
  const larga = Math.max(...apellidos.split(" ").map((p) => p.length));
  const tamApellido = Math.min(140, Math.floor(ANCHO / (Math.max(larga, apellidos.length / 2) * 0.5)));

  return (
    <AbsoluteFill>
      <Sfx nombre="impacto" en={2} />
      <Sfx nombre="tic" en={8} />
      <Sfx nombre="tic" en={12} />
      <Sfx nombre="whoosh" en={22} volumen={0.7} />

      <AbsoluteFill
        style={{
          background: c.acento,
          opacity: interpolate(frame, [0, 6], [1, 0], { extrapolateRight: "clamp", easing: EASE_OUT }),
        }}
      />

      <div style={{ position: "absolute", left: SEGURA.x, right: SEGURA.x, top: SEGURA.arriba + 30 }}>
        <div
          style={{
            translate: `${interpolate(entra(frame, 0, 14), [0, 1], [-900, 0])}px 0px`,
            filter: `blur(${blurEntrada(frame, 0, 14)}px)`,
          }}
        >
          <Chip tam={50}>
            {corto} · Temporada {temporada}
          </Chip>
        </div>
      </div>

      <div style={{ position: "absolute", left: SEGURA.x, right: SEGURA.x, top: 400, display: "flex", alignItems: "flex-end", justifyContent: "space-between" }}>
        <div
          style={{
            fontFamily: fuenteTitulo,
            fontWeight: 700,
            fontSize: 460,
            lineHeight: 0.9,
            color: c.acento,
            letterSpacing: "-0.02em",
            scale: String(golpe(frame, fps, 2) * interpolate(frame, [14, durationInFrames], [1, 1.04], { extrapolateLeft: "clamp" })),
            transformOrigin: "0% 80%",
            textShadow: "0 18px 60px rgba(0,0,0,.35)",
          }}
        >
          {cuenta(frame, 4, top.valor, 14)}
        </div>
        <div style={{ scale: String(golpe(frame, fps, 10)), marginBottom: 40 }}>
          <Escudo src={top.escudo} lado={230} borde={c.acento} />
        </div>
      </div>

      <div style={{ position: "absolute", left: SEGURA.x, right: SEGURA.x, top: 850 }}>
        <div style={{ height: 10, width: `${entra(frame, 14, 16) * 100}%`, background: c.texto }} />
        <Mascara p={entra(frame, 14 + STAGGER, 18)} style={{ marginTop: 24 }}>
          <div style={{ fontFamily: fuenteTexto, fontWeight: 700, fontSize: 54, textTransform: "uppercase", letterSpacing: "0.03em", color: c.gris }}>
            {b.unidad} · {SINGULAR[b.clave] ?? b.titulo}
          </div>
        </Mascara>
      </div>

      <div style={{ position: "absolute", left: SEGURA.x, right: SEGURA.x, top: 1080 }}>
        <Mascara p={entra(frame, 22, 16)}>
          <div style={{ fontFamily: fuenteTexto, fontWeight: 700, fontSize: 60, textTransform: "uppercase", color: c.texto, letterSpacing: "0.04em" }}>
            {top.nombre}
          </div>
        </Mascara>
        <Mascara p={entra(frame, 26, 18)}>
          <div style={{ fontFamily: fuenteTitulo, fontWeight: 700, fontSize: tamApellido, lineHeight: 0.95, textTransform: "uppercase", color: c.texto }}>
            {texto}
          </div>
        </Mascara>
        <Mascara p={entra(frame, 30, 16)} style={{ marginTop: 14 }}>
          <div style={{ fontFamily: fuenteTexto, fontWeight: 700, fontSize: 46, textTransform: "uppercase", color: c.acento, letterSpacing: "0.04em" }}>
            {top.equipo}
          </div>
        </Mascara>
      </div>
    </AbsoluteFill>
  );
};
