"""Migraciones Alembic contra PostgreSQL real (RNF-P-1).

Crea una base temporal, aplica ``upgrade head``, comprueba que el esquema coincide con los modelos y vuelve
con ``downgrade base``. Se salta si no hay PostgreSQL disponible (por ejemplo, en CI sin servicio de base).
"""

from datetime import UTC, datetime
from pathlib import Path

import pytest
from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.config import Config
from alembic.migration import MigrationContext
from sqlalchemy import create_engine, inspect
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from sart.db.modelos import Alerta, Base, Estacion, Medicion, Notificacion, Zona
from sart.dominio.valores import (
    UNIDAD_POR_TIPO,
    EstadoNotificacion,
    FuenteEstacion,
    OrigenMedicion,
    TipoAlerta,
    TipoMedicion,
)

pytestmark = pytest.mark.integracion

ALEMBIC_INI = Path(__file__).resolve().parents[1] / "alembic.ini"


@pytest.fixture
def url_base_temporal(crear_base_temporal):
    return crear_base_temporal()


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


def test_restricciones_migradas_aceptan_las_unidades_de_cada_medicion(url_base_temporal):
    """compare_metadata no revisa el texto de los CHECK: aquí se prueba con datos reales. Así se detectó que
    Alembic había escrito '%%' en vez de '%' y la base rechazaba toda humedad."""
    command.upgrade(_config(url_base_temporal), "head")

    motor = create_engine(url_base_temporal)
    try:
        with Session(motor) as sesion:
            zona = Zona(nombre="Concepción")
            estacion = Estacion(
                nombre="Kingston College", comuna="Concepción", zona=zona, fuente=FuenteEstacion.SINCA
            )
            sesion.add(estacion)
            sesion.flush()
            ahora = datetime.now(UTC)
            sesion.add_all(
                Medicion(estacion_id=estacion.id, fecha_hora=ahora, tipo=tipo, valor=10.0, unidad=unidad)
                for tipo, unidad in UNIDAD_POR_TIPO.items()
            )
            sesion.commit()

            sesion.add(
                Medicion(
                    estacion_id=estacion.id,
                    fecha_hora=ahora,
                    tipo=TipoMedicion.HUMEDAD,
                    valor=10.0,
                    unidad="%%",
                    origen=OrigenMedicion.PRONOSTICO,
                )
            )
            with pytest.raises(IntegrityError):
                sesion.commit()
    finally:
        motor.dispose()


def test_restricciones_de_notificacion_escritas_a_mano(url_base_temporal):
    """Los CHECK de reenvío y escalamiento (RB-2) se escribieron a mano en la 0004: se prueba que existen."""
    command.upgrade(_config(url_base_temporal), "head")

    motor = create_engine(url_base_temporal)
    try:
        with Session(motor) as sesion:
            zona = Zona(nombre="Concepción")
            sesion.add(zona)
            sesion.flush()
            alerta = Alerta(
                tipo=TipoAlerta.AMBIENTAL,
                nivel="alerta",
                fecha_emision=datetime.now(UTC),
                mensaje="MP2,5",
                zona_id=zona.id,
                dia_pronosticado=datetime.now(UTC).date(),
                valor_mp25=85.0,
            )
            sesion.add(alerta)
            sesion.commit()

            enviada = Notificacion(
                alerta_id=alerta.id, estado=EstadoNotificacion.ENVIADA, fecha_envio=datetime.now(UTC)
            )
            sesion.add(enviada)
            sesion.commit()
            assert len(enviada.token_acuse) >= 43

            for estado in (EstadoNotificacion.REENVIADA, EstadoNotificacion.ESCALADA):
                enviada.estado = estado
                with pytest.raises(IntegrityError):
                    sesion.commit()
                sesion.rollback()
    finally:
        motor.dispose()


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
