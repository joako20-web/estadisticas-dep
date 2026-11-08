import React from "react";
import type { PropsPrevia } from "../tipos";
import { AbsoluteFill, useCurrentFrame, useVideoConfig } from "remotion";
import { Chip, Escudo, SEGURA, Sfx, useColores, useReel } from "../../../base/comun";
import { entra, golpe, muelle } from "../../../base/movimiento";
import type { Equipo } from "../../../base/tipos";

const PASO = 4; // escalonado entre filas
const TOP = 440;
const FONDO = 1500; // límite inferior (zona segura)
const HUECO = 12;
const ANCHO_HORA = 190;

/** Tamaño para que el nombre quepa en una línea (Oswald 700 en mayúsculas: ~0,54 em por letra de media). */
const tamUnaLinea = (texto: string, ancho: number, max: number) => Math.min(max, Math.floor(ancho / (texto.length * 0.54)));

const Linea: React.FC<{ eq: Equipo; lado: number; tam: number; color: string }> = ({ eq, lado, tam, color }) => {
  const { fuenteTitulo } = useReel<PropsPrevia>();
  return (
    <div style={{ display: "flex", alignItems: "center", gap: 16, minWidth: 0 }}>
      <Escudo src={eq.escudo} lado={lado} />
      <div style={{ fontFamily: fuenteTitulo, fontWeight: 700, fontSize: tam, lineHeight: 1.05, color, textTransform: "uppercase", whiteSpace: "nowrap" }}>
        {eq.nombre}
      </div>
    </div>
  );
};

// La jornada completa de un vistazo (la "captura" para guardar): filas que entran
// escalonadas, el partido destacado resaltado en acento.
export const Agenda: React.FC = () => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const c = useColores();
  const { partidos, jornada, total, fuenteTitulo, fuenteTexto } = useReel<PropsPrevia>();
  const n = partidos.length;
  const alto = Math.min(170, Math.floor((FONDO - TOP - HUECO * (n - 1)) / n));
  const escudo = Math.min(64, Math.floor((alto - 24) / 2) - 4);
  const anchoNombre = 1080 - 2 * SEGURA.x - 56 - ANCHO_HORA - 24 - escudo - 16;
  // tamaño común para todos los nombres (el que permite la altura de la fila); un nombre
  // larguísimo encoge solo él, lo justo para caber entero
  const tamMax = Math.min(60, Math.floor((alto - 24) / 2 / 1.05));
  const tamDe = (e: Equipo) => Math.max(18, tamUnaLinea(e.nombre.toUpperCase(), anchoNombre, tamMax));
  const normales = partidos.flatMap((p) => [p.local, p.visitante].map(tamDe)).filter((t) => t >= 44);
  const tamComun = normales.length ? Math.min(...normales) : tamMax;
  const inicio = 8;

  return (
    <AbsoluteFill>
      <Sfx nombre="whoosh" en={0} />
      {partidos.map((_, i) => (
        <Sfx key={i} nombre="tic" en={inicio + i * PASO + 4} volumen={0.6} />
      ))}

      <div style={{ position: "absolute", left: SEGURA.x, top: SEGURA.arriba + 30, translate: `${(1 - entra(frame, 0, 16)) * -700}px 0px` }}>
        <Chip tam={50}>Jornada {jornada} completa</Chip>
        {total > n ? (
          <div style={{ fontFamily: fuenteTexto, fontWeight: 700, fontSize: 44, color: c.gris, marginTop: 18, textTransform: "uppercase" }}>
            {n} de {total} partidos
          </div>
        ) : null}
      </div>

      <div style={{ position: "absolute", left: SEGURA.x, right: SEGURA.x, top: TOP, display: "flex", flexDirection: "column", gap: HUECO }}>
        {partidos.map((p, i) => {
          const desde = inicio + i * PASO;
          const m = muelle(frame, fps, desde, 14, 170);
          const d = p.destacado;
          const texto = d ? c.sobreAcento : c.texto;
          return (
            <div
              key={i}
              style={{
                height: alto,
                display: "flex",
                alignItems: "center",
                gap: 24,
                padding: "0 28px",
                background: d ? c.acento : c.panel,
                translate: `${(1 - m) * 1100}px 0px`,
                scale: d ? String(golpe(frame, fps, desde + 10)) : undefined,
              }}
            >
              <div style={{ width: ANCHO_HORA, flexShrink: 0, color: texto }}>
                <div style={{ fontFamily: fuenteTexto, fontWeight: 700, fontSize: 44, lineHeight: 1, opacity: 0.75, textTransform: "uppercase" }}>
                  {p.dia ? `${p.dia} ${p.fecha.split(" ")[0]}` : "Fecha"}
                </div>
                <div style={{ fontFamily: fuenteTitulo, fontWeight: 700, fontSize: p.hora ? 64 : 44, lineHeight: 1.05, textTransform: "uppercase" }}>
                  {p.hora || (p.dia ? "--:--" : "por fijar")}
                </div>
              </div>
              <div style={{ width: 4, alignSelf: "stretch", margin: "18px 0", background: d ? c.sobreAcento : c.acento, opacity: d ? 0.4 : 1 }} />
              <div style={{ flex: 1, minWidth: 0, display: "flex", flexDirection: "column", gap: Math.max(4, Math.min(12, alto - 2 * escudo - 30)) }}>
                <Linea eq={p.local} lado={escudo} tam={Math.min(tamComun, tamDe(p.local))} color={texto} />
                <Linea eq={p.visitante} lado={escudo} tam={Math.min(tamComun, tamDe(p.visitante))} color={texto} />
              </div>
            </div>
          );
        })}
      </div>
    </AbsoluteFill>
  );
};
