"""Conexión a la base a partir de ``DATABASE_URL`` (``sart.configuracion``)."""

from __future__ import annotations

from sqlalchemy import Engine, create_engine
from sqlalchemy.engine import make_url

from sart.configuracion import obtener_configuracion

SEGUNDOS_PARA_CONECTAR = 5  # sin límite, una base inalcanzable deja la API o el comando colgados


class SinBaseDeDatos(RuntimeError):
    """No hay ``DATABASE_URL`` en el entorno ni en el ``.env``."""


def url_base_de_datos() -> str:
    url = obtener_configuracion().database_url
    if not url:
        raise SinBaseDeDatos("Falta DATABASE_URL (en el entorno o en el .env de la raíz del repositorio).")
    return url


def crear_motor(url: str | None = None) -> Engine:
    """Motor SQLAlchemy. En PostgreSQL agrega un límite de tiempo para conectar."""
    url = url or url_base_de_datos()
    argumentos = {}
    if make_url(url).get_backend_name() == "postgresql":
        argumentos["connect_timeout"] = SEGUNDOS_PARA_CONECTAR
    return create_engine(url, pool_pre_ping=True, connect_args=argumentos)
