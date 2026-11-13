"""Migraciones Alembic contra PostgreSQL real (RNF-P-1).

Crea una base temporal, aplica ``upgrade head``, comprueba que el esquema coincide con los modelos y vuelve
con ``downgrade base``. Se salta si no hay PostgreSQL disponible (por ejemplo, en CI sin servicio de base).
"""

import os
import uuid
from pathlib import Path

import pytest
from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.config import Config
from alembic.migration import MigrationContext
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.engine import make_url

from sart.configuracion import RAIZ_REPOSITORIO, Configuracion
from sart.db.modelos import Base

pytestmark = pytest.mark.integracion

ALEMBIC_INI = Path(__file__).resolve().parents[1] / "alembic.ini"


def _url_postgres() -> str | None:
    """DATABASE_URL del entorno o del .env real (conftest aísla el .env, por eso se lee aquí a mano)."""
    return os.environ.get("DATABASE_URL") or Configuracion(_env_file=RAIZ_REPOSITORIO / ".env").database_url


@pytest.fixture
def url_base_temporal():
    url = _url_postgres()
    if not url:
        pytest.skip("sin DATABASE_URL: no hay PostgreSQL para probar migraciones")
    nombre = f"sart_prueba_{uuid.uuid4().hex[:8]}"
    administrador = create_engine(
        make_url(url).set(database="postgres"),
        isolation_level="AUTOCOMMIT",
        connect_args={"connect_timeout": 5},  # sin límite, una base inalcanzable cuelga la prueba
    )
    try:
        with administrador.connect() as conexion:
            conexion.execute(text(f'CREATE DATABASE "{nombre}"'))
    except Exception as error:  # base apagada o sin permisos: se salta, no falla
        administrador.dispose()
        pytest.skip(f"PostgreSQL no disponible ({type(error).__name__})")
    try:
        yield make_url(url).set(database=nombre).render_as_string(hide_password=False)
    finally:
        with administrador.connect() as conexion:
            conexion.execute(text(f'DROP DATABASE IF EXISTS "{nombre}" WITH (FORCE)'))
        administrador.dispose()


def _config(url: str) -> Config:
    config = Config(str(ALEMBIC_INI))
    config.attributes["url"] = url
    return config


def test_upgrade_crea_el_esquema_igual_a_los_modelos(url_base_temporal):
    command.upgrade(_config(url_base_temporal), "head")

    motor = create_engine(url_base_temporal)
    try:
        with motor.connect() as conexion:
            tablas = set(inspect(conexion).get_table_names())
            diferencias = compare_metadata(MigrationContext.configure(conexion), Base.metadata)
    finally:
        motor.dispose()

    assert {"usuario", "aceptacion_finalidad", "alembic_version"} <= tablas
    assert diferencias == [], f"la migración no coincide con los modelos: {diferencias}"


def test_downgrade_deja_la_base_vacia(url_base_temporal):
    config = _config(url_base_temporal)
    command.upgrade(config, "head")
    command.downgrade(config, "base")

    motor = create_engine(url_base_temporal)
    try:
        with motor.connect() as conexion:
            tablas = set(inspect(conexion).get_table_names())
    finally:
        motor.dispose()

    assert tablas <= {"alembic_version"}
