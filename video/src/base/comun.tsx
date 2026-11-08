import React, { createContext, useContext, useEffect, useState } from "react";
import { Audio } from "@remotion/media";
import {
  AbsoluteFill,
  Img,
  Sequence,
  continueRender,
  delayRender,
  interpolate,
  staticFile,
  useCurrentFrame,
  useVideoConfig,
} from "remotion";
import type { Fuente, PropsBase } from "./tipos";

// Zona segura de vídeos: la interfaz de la red tapa arriba y abajo.
export const SEGURA = { x: 80, arriba: 230, abajo: 400 };

export const ReelCtx = createContext<PropsBase | null>(null);
/** Props de la plantilla actual (cada plantilla pasa su tipo: useReel<PropsJornada>()). */
export const useReel = <T extends PropsBase = PropsBase>() => useContext(ReelCtx) as T;

export const useColores = () => {
  const t = useReel().tema;
  return {
    fondo: t.fondo ?? "#0c1631",
    panel: t.panel ?? "#14224a",
    linea: t.linea ?? "#24365f",
    texto: t.texto ?? "#ffffff",
    gris: t.gris ?? "#aab7d6",
    apagado: t.apagado ?? "#66769c",
    acento: t.acento ?? "#f5c518",
    sobreAcento: t["sobre-acento"] ?? "#0c1631",
  };
};

/** Carga las woff2 del tema (con su unicode-range) antes de pintar ningún frame. */
export const useFuentes = (fuentes: Fuente[]) => {
  const [handle] = useState(() => delayRender("fuentes"));
  useEffect(() => {
    Promise.all(
      fuentes.map((f) => {
        const ff = new FontFace(f.familia, `url(${staticFile(f.archivo)}) format("woff2")`, {
          weight: f.peso,
          unicodeRange: f.rango,
        });
        document.fonts.add(ff);
        return ff.load();
      }),
    )
      .catch((e) => console.error(e))
      .finally(() => continueRender(handle));
  }, [fuentes, handle]);
};

/** Efecto de sonido de public/sfx en un frame concreto (relativo a la escena). */
export const Sfx: React.FC<{ nombre: string; en: number; volumen?: number }> = ({ nombre, en, volumen = 1 }) => {
  const { fps } = useVideoConfig();
  return (
    <Sequence from={en} durationInFrames={3 * fps} name={`sfx ${nombre}`} layout="none">
      <Audio src={staticFile(`sfx/${nombre}.wav`)} volume={volumen} premountFor={fps} />
    </Sequence>
  );
};

/** Escudo en círculo blanco: el escudo entero dentro (contain) con margen. */
export const Escudo: React.FC<{ src: string; lado: number; style?: React.CSSProperties; borde?: string }> = ({
  src,
  lado,
  style,
  borde,
}) => (
  <div
    style={{
      width: lado,
      height: lado,
      borderRadius: "50%",
      background: "#fff",
      boxShadow: `0 0 0 ${Math.round(lado * 0.025)}px ${borde ?? "rgba(255,255,255,.0)"}, 0 ${lado * 0.06}px ${lado * 0.18}px rgba(0,0,0,.35)`,
      display: "flex",
      alignItems: "center",
      justifyContent: "center",
      overflow: "hidden",
      flexShrink: 0,
      ...style,
    }}
  >
    {src ? (
      <Img src={src} style={{ width: "74%", height: "74%", objectFit: "contain" }} />
    ) : null}
  </div>
);

/** Rótulo de tele: bloque de acento con el lado derecho en diagonal. */
export const Chip: React.FC<{ children: React.ReactNode; style?: React.CSSProperties; tam?: number; invertido?: boolean }> = ({
  children,
  style,
  tam = 44,
  invertido,
}) => {
  const c = useColores();
  const { fuenteTitulo } = useReel();
  return (
    <div
      style={{
        display: "inline-block",
        background: invertido ? c.texto : c.acento,
        color: c.sobreAcento,
        fontFamily: fuenteTitulo,
        fontWeight: 700,
        fontSize: tam,
        lineHeight: 1,
        textTransform: "uppercase",
        letterSpacing: "0.04em",
        padding: `${tam * 0.3}px ${tam * 1.1}px ${tam * 0.24}px ${tam * 0.5}px`,
        clipPath: `polygon(0 0, 100% 0, calc(100% - ${tam * 0.6}px) 100%, 0 100%)`,
        ...style,
      }}
    >
      {children}
    </div>
  );
};

const TESELA_GRANO = 256;
const GRANO = Array.from({ length: 8 }, (_, semilla) => {
  const svg =
    `<svg xmlns='http://www.w3.org/2000/svg' width='${TESELA_GRANO}' height='${TESELA_GRANO}'>` +
    `<filter id='g'><feTurbulence type='fractalNoise' baseFrequency='0.9' numOctaves='2' seed='${semilla}' stitchTiles='stitch'/>` +
    `<feColorMatrix type='saturate' values='0'/></filter><rect width='100%' height='100%' filter='url(#g)'/></svg>`;
  return `url("data:image/svg+xml,${encodeURIComponent(svg)}")`;
});

/** Fondo común: degradado, franjas diagonales en paralaje, brillo de acento y grano. */
export const Fondo: React.FC = () => {
  const frame = useCurrentFrame();
  const c = useColores();
  const desliza = frame * 0.6;
  const grano = Math.floor(frame / 2) % 8; // el grano cambia cada 2 frames, no en cada uno
  return (
    <AbsoluteFill style={{ background: c.fondo, overflow: "hidden" }}>
      <AbsoluteFill
        style={{
          background: `radial-gradient(120% 70% at 85% 8%, ${c.panel} 0%, transparent 60%), radial-gradient(90% 60% at 0% 100%, ${c.panel} 0%, transparent 70%)`,
        }}
      />
      <AbsoluteFill
        style={{
          opacity: 0.55,
          backgroundImage: `repeating-linear-gradient(-58deg, transparent 0 46px, ${c.linea}55 46px 48px)`,
          backgroundPosition: `${desliza}px 0`,
        }}
      />
      <div
        style={{
          position: "absolute",
          width: 1400,
          height: 220,
          left: -200,
          top: 1260,
          rotate: "-58deg",
          translate: `${interpolate(frame, [0, 600], [-120, 160])}px 0px`,
          background: `linear-gradient(90deg, transparent, ${c.acento}18, transparent)`,
        }}
      />
      {/* Grano: el mismo ruido (feTurbulence) en una tesela de 256 px que encaja sin costuras
          (stitchTiles) y se repite. A la vista es idéntico y el filtro calcula 32 veces menos
          píxeles por frame (antes era ~20 % del tiempo de render). */}
      <div
        style={{
          position: "absolute",
          inset: 0,
          opacity: 0.09,
          mixBlendMode: "overlay",
          backgroundImage: GRANO[grano],
          backgroundSize: `${TESELA_GRANO}px ${TESELA_GRANO}px`,
        }}
      />
      <AbsoluteFill
        style={{ background: "radial-gradient(130% 90% at 50% 45%, transparent 55%, rgba(0,0,0,.45) 100%)" }}
      />
    </AbsoluteFill>
  );
};

/** Texto que aparece desde abajo tras una máscara (el contenedor recorta). */
export const Mascara: React.FC<{ p: number; children: React.ReactNode; style?: React.CSSProperties }> = ({
  p,
  children,
  style,
}) => (
  <div style={{ overflow: "hidden", paddingBottom: "0.08em", ...style }}>
    <div style={{ translate: `0px ${(1 - p) * 110}%` }}>{children}</div>
  </div>
);

/** Tamaño de letra para que un nombre de equipo quepa en `ancho` px (Oswald en mayúsculas). */
export const tamParaAncho = (texto: string, ancho: number, max: number, lineas = 2) => {
  const palabras = texto.split(/\s+/);
  const larga = Math.max(...palabras.map((p) => p.length));
  const total = texto.length / lineas;
  const caracteres = Math.max(larga, total);
  return Math.min(max, Math.floor(ancho / (caracteres * 0.5)));
};

export const Logo: React.FC<{ lado: number; style?: React.CSSProperties }> = ({ lado, style }) => {
  const { logo } = useReel();
  return <Img src={logo} style={{ width: lado, height: lado, objectFit: "contain", ...style }} />;
};

/** Marco común de cada plantilla: contexto con las props, fuentes y fondo animado. */
export const Marco = <T extends PropsBase>({ props, children }: { props: T; children: React.ReactNode }) => {
  useFuentes(props.fuentes);
  return (
    <ReelCtx.Provider value={props}>
      <AbsoluteFill style={{ fontFamily: props.fuenteTexto }}>
        <Fondo />
        {children}
      </AbsoluteFill>
    </ReelCtx.Provider>
  );
};
