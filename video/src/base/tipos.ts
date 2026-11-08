// Tipos comunes a todas las plantillas. Las props las genera Python (datosdep/videos/).
export type Equipo = {
  nombre: string;
  abr: string;
  escudo: string;
  puntos: number | null;
  gana: boolean;
};

export type Partido = { local: Equipo; visitante: Equipo };

export type Fuente = { familia: string; peso: string; archivo: string; rango: string };

/** Lo que llevan todas las plantillas: marca, competición, tema y fuentes. */
export type PropsBase = {
  competicion: string;
  corto: string;
  jornada: number;
  temporada: string;
  handle: string;
  logo: string;
  tema: Record<string, string>;
  fuenteTitulo: string;
  fuenteTexto: string;
  fuentes: Fuente[];
};

export const PROPS_BASE: PropsBase = {
  competicion: "División de Honor",
  corto: "DH",
  jornada: 1,
  temporada: "2026/27",
  handle: "",
  logo: "",
  tema: {},
  fuenteTitulo: "Oswald",
  fuenteTexto: "Roboto Condensed",
  fuentes: [],
};
