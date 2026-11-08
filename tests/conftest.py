import os

# Servidores ficticios: los reales se leen de variables de entorno y no están en el repositorio.
for _k, _v in (("ORIGEN_A_URL", "https://origen-a.invalid"), ("ORIGEN_A_IMG_URL", "https://img.origen-a.invalid"),
               ("ORIGEN_B_URL", "https://origen-b.invalid")):
    os.environ.setdefault(_k, _v)

import pytest

from datosdep import pipeline
from datosdep.rutas import RAIZ

# Copia congelada de data/ (DH masculina, jornadas 1-3): los tests de vídeos y carteles
# no dependen de lo que el bot vaya guardando cada fin de semana.
DATOS_TEST = RAIZ / "tests" / "fixtures" / "data"


@pytest.fixture(autouse=True)
def datos_congelados(monkeypatch):
    monkeypatch.setattr(pipeline, "DATA", DATOS_TEST)
