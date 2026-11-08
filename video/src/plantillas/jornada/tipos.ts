import type { Partido, PropsBase } from "../../base/tipos";

export type PropsJornada = PropsBase & {
  gancho: { numero: string; unidad: string; titular: string; escudo: string } | null;
  partidos: Partido[];
  mvp: {
    nombre: string;
    apellidos: string;
    equipo: string;
    escudo: string;
    posicion: string;
    dorsal: number | null;
    puntos: number;
    stats: { valor: number; texto: string }[];
  } | null;
  top: { pos: number; nombre: string; escudo: string; pt: number; pj: number; zona: string }[];
  trasJornada: number;
  zonaTop: string;
};
