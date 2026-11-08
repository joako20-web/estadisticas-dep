import React from "react";
import { AbsoluteFill, interpolate, useCurrentFrame, useVideoConfig } from "remotion";
import { Chip, Escudo, Mascara, SEGURA, Sfx, tamParaAncho, useColores, useReel } from "../../../base/comun";
import { EASE_OUT, STAGGER, blurEntrada, cuenta, entra, golpe, muelle } from "../../../base/movimiento";
import type { EquipoFinal, PropsFinal } from "../tipos";

const ANCHO = 1080 - 2 * SEGURA.x;
const ALTO_FILA = 290;
export const MARCADOR_EN = 4; // el marcador cuenta desde aquí...
export const DECIDIDO_EN = 22; // ...y aquí se enciende el ganador
const ETIQUETA_EN = 32;

const Fila: React.FC<{ eq: EquipoFinal; desde: number; lado: 1 | -1 }> = ({ eq, desde, lado }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const c = useColores();
  const { fuenteTitulo } = useReel<PropsFinal>();
  const m = muelle(frame, fps, desde, 13, 190);
  const decidido = entra(frame, DECIDIDO_EN, 12);
  const encendido = eq.gana && decidido > 0.5;
  const tam = tamParaAncho(eq.nombre.toUpperCase(), ANCHO - 60 - 210 - 250 - 60, 80);

  return (
    <div
      style={{
        position: "relative",
        height: ALTO_FILA,
        display: "flex",
        alignItems: "center",
        gap: 30,
        padding: "0 30px",
        background: c.panel,
        overflow: "hidden",
        translate: `${(1 - m) * 1100 * lado}px 0px`,
        filter: `blur(${blurEntrada(frame, desde, 12, 10)}px)`,
      }}
    >
      {eq.gana ? (
        <div style={{ position: "absolute", inset: 0, background: c.acento, clipPath: `inset(0 ${(1 - decidido) * 100}% 0 0)` }} />
      ) : null}
      <div style={{ position: "relative", scale: String(golpe(frame, fps, desde + 3)) }}>
        <Escudo src={eq.escudo} lado={210} borde={eq.gana ? c.sobreAcento : undefined} />
      </div>
      <div
        style={{
          position: "relative",
          flex: 1,
          fontFamily: fuenteTitulo,
          fontWeight: 700,
          fontSize: tam,
          lineHeight: 1,
          textTransform: "uppercase",
          color: encendido ? c.sobreAcento : c.texto,
          opacity: eq.gana ? 1 : interpolate(decidido, [0, 1], [1, 0.55]),
        }}
      >
        {eq.nombre}
      </div>
      <div
        style={{
          position: "relative",
          width: 250,
          textAlign: "right",
          fontFamily: fuenteTitulo,
          fontWeight: 700,
          fontSize: 200,
          lineHeight: 1,
          fontVariantNumeric: "tabular-nums",
          color: encendido ? c.sobreAcento : c.texto,
          opacity: eq.gana ? 1 : interpolate(decidido, [0, 1], [1, 0.5]),
        }}
      >
        {cuenta(frame, MARCADOR_EN, eq.puntos ?? 0, 18)}
      </div>
    </div>
  );
};

// Gancho: el marcador final golpea en el primer segundo, se enciende el ganador y cae el relato.
export const Gancho: React.FC = () => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const c = useColores();
  const { local, visitante, etiqueta, frase, completa, corto, jornada, ronda, cuando, fuenteTitulo, fuenteTexto } =
    useReel<PropsFinal>();
  // ancho del rótulo ≈ letras · 0,6 em + 1,7 em de márgenes: siempre en una línea
  const tamEtiqueta = Math.min(118, Math.floor(ANCHO / (etiqueta.length * 0.6 + 1.7)));
  const subtitulo = ["Resultado final", cuando].filter(Boolean).join(" · ");

  return (
    <AbsoluteFill>
      <Sfx nombre="impacto" en={1} />
      <Sfx nombre="tic" en={MARCADOR_EN + 5} volumen={0.6} />
      <Sfx nombre="tic" en={MARCADOR_EN + 11} volumen={0.6} />
      <Sfx nombre="pop" en={DECIDIDO_EN} />
      {etiqueta ? <Sfx nombre="impacto" en={ETIQUETA_EN} volumen={0.8} /> : null}

      {/* destello de acento al arrancar: enlaza con el final del Cierre para el bucle */}
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
            {corto} · {ronda || `Jornada ${jornada}`}
          </Chip>
        </div>
        <Mascara p={entra(frame, 6, 16)} style={{ marginTop: 18 }}>
          <div
            style={{
              fontFamily: fuenteTexto,
              fontWeight: 700,
              fontSize: 46,
              color: c.gris,
              textTransform: "uppercase",
              letterSpacing: "0.06em",
            }}
          >
            {subtitulo}
          </div>
        </Mascara>
      </div>

      <div
        style={{
          position: "absolute",
          left: SEGURA.x,
          right: SEGURA.x,
          top: 480,
          display: "flex",
          flexDirection: "column",
          gap: 18,
        }}
      >
        <Fila eq={local} desde={0} lado={-1} />
        <Fila eq={visitante} desde={STAGGER} lado={1} />
      </div>

      {etiqueta ? (
        <div style={{ position: "absolute", left: SEGURA.x, right: SEGURA.x, top: 1150 }}>
          <div
            style={{
              scale: String(golpe(frame, fps, ETIQUETA_EN)),
              rotate: `${interpolate(entra(frame, ETIQUETA_EN, 16), [0, 1], [-7, -2])}deg`,
              transformOrigin: "0% 50%",
              opacity: frame >= ETIQUETA_EN ? 1 : 0,
            }}
          >
            <Chip tam={tamEtiqueta} style={{ boxShadow: "0 20px 60px rgba(0,0,0,.4)", whiteSpace: "nowrap" }}>
              {etiqueta}
            </Chip>
          </div>
          {frase ? (
            <Mascara p={entra(frame, ETIQUETA_EN + 6, 18)} style={{ marginTop: 34 }}>
              <div
                style={{
                  fontFamily: fuenteTitulo,
                  fontWeight: 500,
                  fontSize: 58,
                  lineHeight: 1.1,
                  color: c.texto,
                  textTransform: "uppercase",
                }}
              >
                {frase}
              </div>
            </Mascara>
          ) : null}
        </div>
      ) : null}
      {/* acta incompleta: se avisa de que el detalle llegará con el acta oficial */}
      {!completa ? (
        <Mascara p={entra(frame, 44, 18)} style={{ position: "absolute", left: SEGURA.x, right: SEGURA.x, top: 1420 }}>
          <div style={{ fontFamily: fuenteTexto, fontWeight: 700, fontSize: 44, color: c.apagado, textTransform: "uppercase", letterSpacing: "0.05em" }}>
            Anotadores pendientes del acta oficial
          </div>
        </Mascara>
      ) : null}
    </AbsoluteFill>
  );
};
