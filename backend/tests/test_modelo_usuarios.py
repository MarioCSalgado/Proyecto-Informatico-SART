"""Modelo de Usuario y de aceptación de la finalidad (§5.1, RF-16, RNF-S-1, RNF-S-2).

Corre en SQLite en memoria: no necesita Docker. La migración real se prueba en test_migraciones.py.
"""

from datetime import UTC, datetime

import pytest
from sqlalchemy import create_engine, event, select
from sqlalchemy.exc import IntegrityError, StatementError
from sqlalchemy.orm import Session

from sart.db.modelos import AceptacionFinalidad, Base, Usuario
from sart.dominio.roles import Rol


@pytest.fixture
def sesion():
    motor = create_engine("sqlite://")
    # SQLite no revisa las claves foráneas si no se le pide
    event.listen(motor, "connect", lambda conexion, _: conexion.execute("PRAGMA foreign_keys=ON"))
    Base.metadata.create_all(motor)
    with Session(motor) as sesion:
        yield sesion
    motor.dispose()


def _usuario(correo="jefatura@demo.sart", rol=Rol.JEFATURA) -> Usuario:
    return Usuario(nombre="Jefatura de prueba", correo=correo, rol=rol, hash_contrasena="$argon2id$falso")


def test_guarda_usuario_con_su_aceptacion(sesion):
    usuario = _usuario()
    usuario.aceptaciones.append(
        AceptacionFinalidad(version_texto="2026-1", aceptada_en=datetime(2026, 11, 13, 12, tzinfo=UTC))
    )
    sesion.add(usuario)
    sesion.commit()

    guardado = sesion.scalars(select(Usuario)).one()
    assert guardado.id is not None
    assert guardado.rol is Rol.JEFATURA
    assert guardado.creado_en is not None
    assert [a.version_texto for a in guardado.aceptaciones] == ["2026-1"]


def test_el_correo_es_unico(sesion):
    """§5.1: correo único."""
    sesion.add(_usuario())
    sesion.commit()
    sesion.add(_usuario(rol=Rol.SUBDIRECTOR))

    with pytest.raises(IntegrityError):
        sesion.commit()


def test_rol_fuera_de_los_tres_definidos_se_rechaza(sesion):
    """RNF-S-2: solo jefatura, subdirector o administrador."""
    sesion.add(_usuario(rol="paciente"))

    with pytest.raises(StatementError):
        sesion.commit()


def test_los_tres_roles_de_rnf_s2():
    assert {r.value for r in Rol} == {"jefatura", "subdirector", "administrador"}


def test_baja_de_la_cuenta_borra_sus_aceptaciones(sesion):
    """RF-16 E2: al dar de baja se eliminan los datos de la cuenta."""
    usuario = _usuario()
    usuario.aceptaciones.append(AceptacionFinalidad(version_texto="2026-1", aceptada_en=datetime.now(UTC)))
    sesion.add(usuario)
    sesion.commit()

    sesion.delete(usuario)
    sesion.commit()

    assert sesion.scalars(select(AceptacionFinalidad)).all() == []


def test_sin_campos_de_pacientes():
    """RNF-S-5: la tabla de usuarios solo tiene datos de la cuenta (§5.3)."""
    columnas = set(Usuario.__table__.columns.keys())
    assert columnas == {"id", "nombre", "correo", "rol", "hash_contrasena", "creado_en", "actualizado_en"}
