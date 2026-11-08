"""Que todos los módulos se puedan importar (un error de sintaxis tumba el bot)."""
import importlib
import pkgutil

import datosdep


def test_todos_los_modulos_importan():
    for m in pkgutil.walk_packages(datosdep.__path__, "datosdep."):
        importlib.import_module(m.name)
