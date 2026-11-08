from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

PUNTOS = {"ensayo": 5, "ensayo_castigo": 7, "conversion": 2, "golpe": 3, "drop": 3}
TARJETAS = {"amarilla", "roja20", "roja"}


@dataclass
class Partido:
    id: int
    jornada: int
    fecha: datetime | None
    local: str
    visitante: str
    puntos_local: int | None
    puntos_visitante: int | None
    campo: str
    estado: str  # "jugado" | "pendiente" | ...
    grupo: int | None = None  # id de grupo/fase de el origen A
    ronda: str = ""  # "Cuartos de Final", "Semifinales", "Final"... (eliminatorias)

    @property
    def jugado(self) -> bool:
        return self.estado == "jugado" and self.puntos_local is not None

    @property
    def ganador(self) -> str | None:
        if not self.jugado or self.puntos_local == self.puntos_visitante:
            return None
        return self.local if self.puntos_local > self.puntos_visitante else self.visitante


@dataclass
class Evento:
    minuto: int
    tipo: str  # clave de PUNTOS, de TARJETAS u "otro"
    tipo_original: str
    marcador: tuple[int, int] | None
    equipo: str
    jugador: str

    @property
    def puntos(self) -> int:
        return PUNTOS.get(self.tipo, 0)


@dataclass
class Jugador:
    nombre: str
    dorsal: int  # posición en el partido: 1-15 titulares, 16+ banquillo (ver origen_b.posiciones)
    tantos: int = 0
    foto: str = ""
    camiseta: int | None = None  # número de la camiseta, si no coincide con la posición


@dataclass
class Acta:
    id_partido: int
    local: str
    visitante: str
    eventos: list[Evento]
    alineacion_local: list[Jugador]
    alineacion_visitante: list[Jugador]

    def marcador_por_eventos(self) -> tuple[int, int]:
        loc = sum(e.puntos for e in self.eventos if e.equipo == self.local)
        vis = sum(e.puntos for e in self.eventos if e.equipo == self.visitante)
        return loc, vis


@dataclass
class FilaClasificacion:
    posicion: int
    equipo: str
    racha: list[str]
    pt: int
    pj: int
    pg: int
    pe: int
    pp: int
    tf: int
    tc: int
    dt: int
    ef: int
    ec: int
    de: int
    bo: int
    bd: int
    escudo: str = ""


@dataclass
class JugadorTemporada:
    id: int | None
    nombre: str
    equipo: str
    pj: int
    puntos: int
    ensayos: int
    amarillas: int
    rojas: int


@dataclass
class Competicion:
    partidos: list[Partido] = field(default_factory=list)
    jugadores: list[JugadorTemporada] = field(default_factory=list)

    def jornada(self, n: int) -> list[Partido]:
        return [p for p in self.partidos if p.jornada == n]

    def filtrar(self, id_grupo: int, equipos: set[str]) -> Competicion:
        """Solo los partidos de ese grupo/fase y los jugadores de esos equipos
        (la página de estadísticas mezcla todas las fases y grupos)."""
        return Competicion(
            [p for p in self.partidos if p.grupo in (id_grupo, None)],
            [j for j in self.jugadores if j.equipo in equipos],
        )

    def ultima_jornada_jugada(self) -> int | None:
        js = [p.jornada for p in self.partidos if p.jugado]
        return max(js) if js else None
