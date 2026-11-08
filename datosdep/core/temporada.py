"""XV y MVP de la temporada: acumulado de las notas de jornada de cada jugador.

Criterio: suma de las notas de cada partido (datosdep.core.estadisticas.nota).
Premia rendir y también jugar: un jugador que está todas las jornadas a buen
nivel supera a uno que tuvo un partido enorme. Para el XV se usa el dorsal que
más veces llevó de titular (1-15) y se exige un mínimo de partidos de titular
(la mitad de las jornadas jugadas, redondeando hacia arriba, máx. 3) para que no
entre alguien con un único partido.
"""
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field

from datosdep.core import estadisticas as E
from datosdep.pipeline import cargar_config
from datosdep.scraper.origen_a import cliente_para


@dataclass
class Acumulado:
    nombre: str
    equipo: str
    nota: float = 0.0
    partidos: int = 0
    titular: int = 0
    puntos: int = 0
    ensayos: int = 0
    dorsales: Counter = field(default_factory=Counter)

    @property
    def dorsal(self) -> int:
        """Dorsal de titular más repetido (0 si nunca fue titular)."""
        return self.dorsales.most_common(1)[0][0] if self.dorsales else 0


def lineas_temporada(comp: str, grupo: str = "unico", cliente=None) -> dict[int, list[E.LineaJugador]]:
    """Líneas de jugador de cada partido jugado con acta completa, por jornada."""
    cfg = cargar_config()["competiciones"][comp]
    cliente = cliente or cliente_para(cfg)
    id_grupo = cfg["grupos"][grupo]
    clas = cliente.clasificacion(id_grupo)
    competicion = cliente.competicion(id_grupo).filtrar(id_grupo, {f.equipo for f in clas})
    por_jornada: dict[int, list[E.LineaJugador]] = {}
    for p in competicion.partidos:
        if not p.jugado or not p.jornada:
            continue
        acta = cliente.acta(p.id)
        if acta.marcador_por_eventos() != (p.puntos_local, p.puntos_visitante):
            continue  # acta incompleta: sus estadísticas no cuentan
        por_jornada.setdefault(p.jornada, []).extend(E.lineas_partido(p, acta))
    return dict(sorted(por_jornada.items()))


def acumular(por_jornada: dict[int, list[E.LineaJugador]]) -> list[Acumulado]:
    acum: dict[tuple[str, str], Acumulado] = {}
    for lineas in por_jornada.values():
        for ln in lineas:
            a = acum.setdefault((ln.nombre, ln.equipo), Acumulado(ln.nombre, ln.equipo))
            a.partidos += 1
            a.nota = round(a.nota + ln.nota, 2)
            a.puntos += ln.puntos
            a.ensayos += ln.ensayos
            if 1 <= ln.dorsal <= 15:
                a.titular += 1
                a.dorsales[ln.dorsal] += 1
    return list(acum.values())


def minimo_titularidades(jornadas: int) -> int:
    return min(3, max(1, -(-jornadas // 2)))


def mvp_temporada(acumulados: list[Acumulado], top: int = 8) -> list[Acumulado]:
    return sorted(acumulados, key=lambda a: (-a.nota, -a.puntos, a.nombre))[:top]


def xv_temporada(acumulados: list[Acumulado], jornadas: int, max_por_equipo: int = 4) -> dict[int, E.LineaJugador]:
    """XV de la temporada reutilizando el reparto por posiciones de xv_ideal()."""
    minimo = minimo_titularidades(jornadas)
    candidatos = [
        E.LineaJugador(a.nombre, a.equipo, a.dorsal, puntos=a.puntos, ensayos=a.ensayos, nota=a.nota)
        for a in acumulados
        if a.dorsal and a.titular >= minimo
    ]
    return E.xv_ideal(candidatos, max_por_equipo=max_por_equipo)
