import React from "react";
import { AbsoluteFill, interpolate, useCurrentFrame, useVideoConfig } from "remotion";
import { Chip, Escudo, SEGURA, Sfx, useColores, useReel } from "../../../base/comun";
import { EASE_IN_OUT, cuenta, entra, golpe, muelle } from "../../../base/movimiento";
import type { FilaTabla, PropsClasificacion } from "../tipos";

// Geometría de la tabla (px). Las filas viven en una "ventana" fija; si no caben,
// la cámara baja suavemente hasta el final (y la leyenda) después de que entren.
// Con pocos equipos las filas crecen (hasta ALTO_MAX) para llenar la ventana.
const ALTO = 104;
const ALTO_MAX = 170;
const HUECO = 8;
const VENTANA_Y = 500;
const VENTANA_ALTO = 1920 - SEGURA.abajo - VENTANA_Y; // hasta el borde de la zona segura
const ALTO_LEYENDA = 66;
const MARGEN_LEYENDA = 36;

// Tiempos (frames)
const INICIO = 12;
const ESCALON = 3; // escalonado entre filas
const ENTRADA = 22; // lo que tarda una fila en asentarse con su flecha
const LECTURA = 70; // pausa final para leer
const MINIMO = 180; // con pocos equipos la escena no baja de 6 s (y el reel, de 10 s)

const W = { pos: 62, mov: 62, escudo: 72, pj: 60, dif: 92, pt: 92 };
const GAP = 14;

export const planTabla = (filas: number, leyenda: number) => {
  const altoLeyenda = leyenda ? MARGEN_LEYENDA + leyenda * ALTO_LEYENDA : 0;
  const cabe = Math.floor((VENTANA_ALTO - altoLeyenda + HUECO) / Math.max(1, filas)) - HUECO;
  const fila = Math.max(ALTO, Math.min(ALTO_MAX, cabe));
  const paso = fila + HUECO;
  const alto = filas * paso - HUECO + altoLeyenda;
  const exceso = Math.max(0, alto - VENTANA_ALTO);
  const visibles = Math.min(filas, Math.floor((VENTANA_ALTO + HUECO) / paso));
  const panDesde = INICIO + visibles * ESCALON + 16;
  const panDur = exceso ? Math.round(Math.min(150, Math.max(50, exceso / 4))) : 0;
  const leyendaEn = exceso ? panDesde + panDur * 0.75 : INICIO + filas * ESCALON + ENTRADA;
  const total = Math.max(MINIMO, Math.round(Math.max(panDesde + panDur, leyendaEn + 20) + LECTURA));
  return { fila, paso, alto, exceso, visibles, panDesde, panDur, leyendaEn, total };
};

const desplazamiento = (frame: number, plan: ReturnType<typeof planTabla>) =>
  plan.exceso
    ? interpolate(frame, [plan.panDesde, plan.panDesde + plan.panDur], [0, plan.exceso], {
        extrapolateLeft: "clamp",
        extrapolateRight: "clamp",
        easing: EASE_IN_OUT,
      })
    : 0;

/** Frame en el que una fila (por su borde inferior) asoma en la ventana. */
const asoma = (fondo: number, plan: ReturnType<typeof planTabla>) => {
  if (fondo <= VENTANA_ALTO) return 0;
  for (let f = plan.panDesde; f <= plan.panDesde + plan.panDur; f++) {
    if (fondo - desplazamiento(f, plan) <= VENTANA_ALTO + plan.fila * 0.6) return f;
  }
  return plan.panDesde + plan.panDur;
};

const Flecha: React.FC<{ mov: number | null; desde: number; tam: number; sobreAcento?: boolean }> = ({ mov, desde, tam, sobreAcento }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const c = useColores();
  const { fuenteTexto } = useReel();
  if (mov === null) return null;
  const p = entra(frame, desde, 16);
  if (mov === 0) {
    return <div style={{ width: 26, height: 6, background: sobreAcento ? c.sobreAcento : c.apagado, opacity: p, scale: `${p} 1` }} />;
  }
  const sube = mov > 0;
  return (
    <div
      style={{
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        lineHeight: 0.9,
        color: sobreAcento ? c.sobreAcento : sube ? "#3ddc84" : "#ef5b4b",
        opacity: p,
        translate: `0px ${(1 - p) * (sube ? 26 : -26)}px`,
        scale: String(golpe(frame, fps, desde)),
      }}
    >
      {/* triángulo dibujado (no depende de que la fuente tenga ▲▼) */}
      <div
        style={{
          width: tam * 0.7,
          height: tam * 0.5,
          marginBottom: 4,
          background: "currentColor",
          clipPath: sube ? "polygon(50% 0, 100% 100%, 0 100%)" : "polygon(0 0, 100% 0, 50% 100%)",
        }}
      />
      <span style={{ fontFamily: fuenteTexto, fontWeight: 700, fontSize: tam }}>{Math.abs(mov)}</span>
    </div>
  );
};

const Fila: React.FC<{ f: FilaTabla; desde: number; conMov: boolean; anchoNombre: number; alto: number }> = ({
  f,
  desde,
  conMov,
  anchoNombre,
  alto,
}) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const c = useColores();
  const { fuenteTitulo, fuenteTexto } = useReel<PropsClasificacion>();
  const lider = f.pos === 1;
  const m = muelle(frame, fps, desde, 14, 170);
  const zona = entra(frame, desde + 6, 16);
  const nombre = f.nombre.toUpperCase();
  // Oswald en mayúsculas: ~0,56 em por letra (con margen; tamParaAncho se queda corto aquí)
  const e = (alto - ALTO) / (ALTO_MAX - ALTO); // 0 con filas normales, 1 con las más altas
  const ancho = anchoNombre - Math.round(e * 24); // el escudo crece con la fila
  const una = Math.min(52 + Math.round(e * 8), Math.floor(ancho / (nombre.length * 0.56)));
  const dosLineas = una < 44;
  const larga = Math.max(...nombre.split(/\s+/).map((p) => p.length), Math.ceil(nombre.length / 2));
  const tam = dosLineas ? Math.max(40, Math.min(48, Math.floor(ancho / (larga * 0.56)))) : una;
  const tinta = lider ? c.sobreAcento : c.texto;
  const sec = lider ? "rgba(12,22,49,.72)" : c.gris;
  const num: React.CSSProperties = { fontFamily: fuenteTexto, fontWeight: 700, textAlign: "center", flexShrink: 0 };

  return (
    <div
      style={{
        position: "relative",
        height: alto,
        display: "flex",
        alignItems: "center",
        gap: GAP,
        paddingLeft: 24,
        paddingRight: 18,
        background: lider ? c.acento : f.pos % 2 ? c.panel : `${c.panel}c0`,
        color: tinta,
        translate: `${(1 - m) * 1100}px 0px`,
        overflow: "hidden",
      }}
    >
      {f.zona ? (
        <>
          {/* tinte de zona que barre de izquierda a derecha */}
          <div
            style={{
              position: "absolute",
              inset: 0,
              background: `linear-gradient(90deg, ${f.zona}${lider ? "00" : "33"} 0%, transparent 55%)`,
              clipPath: `inset(0 ${(1 - zona) * 100}% 0 0)`,
            }}
          />
          {/* franja de zona que se dibuja de arriba abajo */}
          <div
            style={{
              position: "absolute",
              left: 0,
              top: 0,
              bottom: 0,
              width: 12,
              background: lider && f.zona === c.acento ? c.sobreAcento : f.zona,
              scale: `1 ${zona}`,
              transformOrigin: "50% 0%",
            }}
          />
        </>
      ) : null}
      {lider ? (
        // destello que cruza la fila del líder (movimiento secundario durante la lectura)
        <div
          style={{
            position: "absolute",
            top: 0,
            bottom: 0,
            width: 160,
            left: -200,
            background: "linear-gradient(100deg, transparent, rgba(255,255,255,.55), transparent)",
            translate: `${(frame < desde + 130 ? entra(frame, desde + 40, 26) : entra(frame, desde + 130, 26)) * 1300}px 0px`,
          }}
        />
      ) : null}
      <div style={{ position: "relative", width: W.pos, flexShrink: 0, fontFamily: fuenteTitulo, fontWeight: 700, fontSize: 56 + e * 12, textAlign: "center" }}>
        {f.pos}
      </div>
      {conMov ? (
        <div style={{ position: "relative", width: W.mov, flexShrink: 0, display: "flex", justifyContent: "center" }}>
          <Flecha mov={f.mov} desde={desde + 14} tam={42} sobreAcento={lider} />
        </div>
      ) : null}
      <div style={{ position: "relative", scale: String(golpe(frame, fps, desde + 3)) }}>
        <Escudo src={f.escudo} lado={W.escudo + Math.round(e * 24)} borde={lider ? c.sobreAcento : undefined} />
      </div>
      <div
        style={{
          position: "relative",
          flex: 1,
          minWidth: 0,
          fontFamily: fuenteTitulo,
          fontWeight: 700,
          fontSize: tam,
          lineHeight: 0.98,
          textTransform: "uppercase",
          whiteSpace: dosLineas ? "normal" : "nowrap",
          overflow: "hidden",
          textOverflow: "ellipsis",
          maxHeight: alto - 8,
        }}
      >
        {f.nombre}
      </div>
      <div style={{ ...num, position: "relative", width: W.pj, fontSize: 44 + e * 4, color: sec }}>{f.pj}</div>
      <div style={{ ...num, position: "relative", width: W.dif, fontSize: 44 + e * 4, color: lider ? tinta : f.dif > 0 ? c.texto : c.gris }}>
        {f.dif > 0 ? `+${f.dif}` : f.dif}
      </div>
      <div style={{ position: "relative", width: W.pt, flexShrink: 0, textAlign: "right", fontFamily: fuenteTitulo, fontWeight: 700, fontSize: 64 + e * 14, lineHeight: 1 }}>
        {cuenta(frame, desde + 6, f.pt, 18)}
      </div>
    </div>
  );
};

// Tabla completa: filas escalonadas, franjas de zona, flechas de movimiento y leyenda.
export const Tabla: React.FC = () => {
  const frame = useCurrentFrame();
  const c = useColores();
  const { filas, leyenda, trasJornada, fuenteTexto } = useReel<PropsClasificacion>();
  const plan = planTabla(filas.length, leyenda.length);
  const scroll = desplazamiento(frame, plan);
  const conMov = filas.some((f) => f.mov !== null);
  const anchoNombre =
    1080 - 2 * SEGURA.x - 24 - 18 - W.pos - (conMov ? W.mov + GAP : 0) - W.escudo - W.pj - W.dif - W.pt - 6 * GAP;
  const entradaFila = (i: number) => Math.max(INICIO + Math.min(i, plan.visibles) * ESCALON, asoma((i + 1) * plan.paso - HUECO, plan) - 4);
  const leyendaEn = Math.max(plan.leyendaEn, asoma(filas.length * plan.paso + MARGEN_LEYENDA + ALTO_LEYENDA, plan));
  const cab: React.CSSProperties = {
    fontFamily: fuenteTexto,
    fontWeight: 700,
    fontSize: 38,
    color: c.gris,
    textTransform: "uppercase",
    letterSpacing: "0.06em",
    textAlign: "center",
    flexShrink: 0,
  };
  const hayMas = plan.exceso > 0 && scroll < plan.exceso - 2;

  return (
    <AbsoluteFill>
      <Sfx nombre="whoosh" en={0} />
      {[0, 1, 2, 3].filter((i) => i < filas.length).map((i) => (
        <Sfx key={i} nombre="tic" en={entradaFila(i) + 4} volumen={0.6} />
      ))}
      {conMov ? <Sfx nombre="pop" en={entradaFila(0) + 14} volumen={0.8} /> : null}
      {plan.exceso ? <Sfx nombre="whoosh" en={plan.panDesde} volumen={0.45} /> : null}
      {leyenda.length ? <Sfx nombre="pop" en={Math.round(leyendaEn)} volumen={0.7} /> : null}

      <div
        style={{
          position: "absolute",
          left: SEGURA.x,
          right: SEGURA.x,
          top: SEGURA.arriba + 20,
          display: "flex",
          alignItems: "flex-end",
          justifyContent: "space-between",
          translate: `${(1 - entra(frame, 0, 16)) * -700}px 0px`,
        }}
      >
        <Chip tam={56}>Clasificación</Chip>
        <div
          style={{
            fontFamily: fuenteTexto,
            fontWeight: 700,
            fontSize: 44,
            color: c.gris,
            textTransform: "uppercase",
            letterSpacing: "0.06em",
            opacity: entra(frame, 6, 16),
          }}
        >
          Jornada {trasJornada}
        </div>
      </div>

      {/* cabecera de columnas, fija */}
      <div
        style={{
          position: "absolute",
          left: SEGURA.x,
          right: SEGURA.x,
          top: VENTANA_Y - 64,
          display: "flex",
          alignItems: "center",
          gap: GAP,
          paddingLeft: 24,
          paddingRight: 18,
          opacity: entra(frame, 8, 16),
        }}
      >
        <div style={{ ...cab, width: W.pos }}>#</div>
        {conMov ? <div style={{ ...cab, width: W.mov }} /> : null}
        <div style={{ ...cab, width: W.escudo }} />
        <div style={{ ...cab, flex: 1, textAlign: "left", flexShrink: 1 }}>Equipo</div>
        <div style={{ ...cab, width: W.pj }}>PJ</div>
        <div style={{ ...cab, width: W.dif }}>Dif</div>
        <div style={{ ...cab, width: W.pt, textAlign: "right", color: c.acento }}>Pts</div>
      </div>

      <div
        style={{
          position: "absolute",
          left: SEGURA.x,
          right: SEGURA.x,
          top: VENTANA_Y,
          height: VENTANA_ALTO,
          overflow: "hidden",
          // con más tabla por debajo, el borde inferior se difumina
          maskImage: `linear-gradient(180deg, transparent 0px, #000 ${Math.min(1, scroll / 40) * 36}px, #000 ${VENTANA_ALTO - (hayMas ? 110 : 0)}px, ${hayMas ? "transparent" : "#000"} 100%)`,
        }}
      >
        <div style={{ translate: `0px ${-scroll}px`, display: "flex", flexDirection: "column", gap: HUECO }}>
          {filas.map((f, i) => (
            <Fila key={f.pos + f.nombre} f={f} desde={entradaFila(i)} conMov={conMov} anchoNombre={anchoNombre} alto={plan.fila} />
          ))}
          {leyenda.length ? (
            <div style={{ marginTop: MARGEN_LEYENDA - HUECO, display: "flex", flexDirection: "column" }}>
              {leyenda.map((z, i) => {
                const p = entra(frame, leyendaEn + i * 4, 18);
                return (
                  <div
                    key={z.texto}
                    style={{
                      height: ALTO_LEYENDA,
                      display: "flex",
                      alignItems: "center",
                      gap: 20,
                      fontFamily: fuenteTexto,
                      fontWeight: 700,
                      fontSize: 44,
                      color: c.gris,
                      textTransform: "uppercase",
                      opacity: p,
                      translate: `${(1 - p) * 60}px 0px`,
                    }}
                  >
                    <div style={{ width: 14, height: 46, background: z.color, flexShrink: 0, scale: `1 ${p}` }} />
                    <span style={{ whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>{z.texto}</span>
                  </div>
                );
              })}
            </div>
          ) : null}
        </div>
      </div>
    </AbsoluteFill>
  );
};
