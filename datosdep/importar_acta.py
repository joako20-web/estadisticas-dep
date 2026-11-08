"""Importa actas guardadas a mano desde el navegador (sin tocar la web).

uso: uv run python -m datosdep.importar_acta <id_partido> <fichero>   (JSON o HTML guardado)
Comprueba que el marcador del acta coincide con el oficial antes de dejarla en la caché.
"""
from __future__ import annotations

import sys
from pathlib import Path

from datosdep.scraper.origen_a import OrigenA


def importar(id_partido: int, ruta: Path, esperado: tuple[int, int] | None = None, cliente: OrigenA | None = None) -> bool:
    c = cliente or OrigenA()
    c.guardar_acta_manual(id_partido, Path(ruta).read_bytes())
    try:
        acta = c.acta(id_partido)
    except (ValueError, KeyError):
        print(f"{id_partido}: no he podido leer ese fichero como acta")
        c.borrar_acta_cache(id_partido)
        return False
    ok = bool(acta.eventos) and (esperado is None or acta.marcador_por_eventos() == esperado)
    print(f"{id_partido}: {len(acta.eventos)} eventos, marcador {acta.marcador_por_eventos()} "
          f"{'OK' if ok else 'NO COINCIDE o vacía'}")
    if not ok:
        c.borrar_acta_cache(id_partido)
    return ok


if __name__ == "__main__":
    importar(int(sys.argv[1]), Path(sys.argv[2]))
