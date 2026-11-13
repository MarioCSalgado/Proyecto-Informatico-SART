"""Entorno de Alembic: toma la URL de ``DATABASE_URL`` (entorno o .env, ver ``sart.configuracion``).

Las pruebas pasan otra URL en ``config.attributes["url"]`` para usar una base temporal.
"""

from logging.config import fileConfig

from alembic import context
from sqlalchemy import create_engine

from sart.configuracion import obtener_configuracion
from sart.db.modelos import Base

config = context.config
if config.config_file_name is not None and not config.attributes.get("url"):
    fileConfig(config.config_file_name, disable_existing_loggers=False)

target_metadata = Base.metadata


def _url() -> str:
    url = config.attributes.get("url") or obtener_configuracion().database_url
    if not url:
        raise RuntimeError("Falta DATABASE_URL (en el entorno o en el .env de la raíz del repositorio)")
    return url


def correr_sin_conexion() -> None:
    """Genera el SQL sin conectarse (``alembic upgrade head --sql``)."""
    context.configure(url=_url(), target_metadata=target_metadata, literal_binds=True)
    with context.begin_transaction():
        context.run_migrations()


def correr_con_conexion() -> None:
    motor = create_engine(_url())
    try:
        with motor.connect() as conexion:
            context.configure(connection=conexion, target_metadata=target_metadata)
            with context.begin_transaction():
                context.run_migrations()
    finally:
        motor.dispose()


if context.is_offline_mode():
    correr_sin_conexion()
else:
    correr_con_conexion()
