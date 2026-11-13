"""Lector de ``config/parametros.yaml`` (RNF-M-4, RF-9).

Ningún supuesto (k, percentiles, minutos por atención, horarios, plazos de RB-2…) se escribe en el código:
todo se lee de aquí. La ruta se toma de la variable de entorno ``SART_PARAMETROS``; si no está, se usa
``config/parametros.yaml`` en la raíz del repositorio.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import yaml

RUTA_POR_DEFECTO = Path(__file__).resolve().parents[2] / "config" / "parametros.yaml"

SECCIONES_OBLIGATORIAS = (
    "zona_horaria",
    "horarios",
    "escenario",
    "modelo",
    "umbrales",
    "regla_alerta",
    "mp25_niveles",
    "notificaciones",
    "dotacion",
    "ingesta",
    "consulta",
    "auditoria",
)


class ErrorParametros(Exception):
    """El archivo de parámetros no existe, no es YAML válido o le falta una sección."""


def ruta_parametros() -> Path:
    """Ruta del archivo de parámetros: ``SART_PARAMETROS`` o la ruta por defecto."""
    return Path(os.environ.get("SART_PARAMETROS", RUTA_POR_DEFECTO))


def cargar_parametros(ruta: str | Path | None = None) -> dict[str, Any]:
    """Lee y valida el archivo de parámetros.

    Lanza ``ErrorParametros`` con un mensaje claro si el archivo falta, no es un mapa YAML o le falta
    alguna de las secciones obligatorias.
    """
    ruta = Path(ruta) if ruta is not None else ruta_parametros()
    if not ruta.is_file():
        raise ErrorParametros(f"No existe el archivo de parámetros: {ruta}")
    try:
        with ruta.open(encoding="utf-8") as archivo:
            datos = yaml.safe_load(archivo)
    except yaml.YAMLError as error:
        raise ErrorParametros(f"{ruta} no es un YAML válido: {error}") from error
    if not isinstance(datos, dict):
        raise ErrorParametros(f"{ruta} debe contener un mapa de secciones")
    faltantes = [s for s in SECCIONES_OBLIGATORIAS if s not in datos]
    if faltantes:
        raise ErrorParametros(f"Faltan secciones en {ruta}: {', '.join(faltantes)}")
    return datos
