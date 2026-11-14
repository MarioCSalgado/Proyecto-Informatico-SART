"""Campos de la notificación para el acuse y el escalamiento (RF-15, RB-2)."""

from datetime import UTC, date, datetime

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from sart.db.modelos import Alerta, Base, Estacion, Notificacion, Usuario, Zona
from sart.dominio.roles import Rol
from sart.dominio.valores import EstadoNotificacion, FuenteEstacion, TipoAlerta

AHORA = datetime(2026, 11, 13, 9, tzinfo=UTC)


@pytest.fixture
def sesion():
    motor = create_engine("sqlite://")
    Base.metadata.create_all(motor)
    with Session(motor) as sesion:
        zona = Zona(nombre="Concepción")
        sesion.add(
            Estacion(nombre="Kingston College", comuna="Concepción", zona=zona, fuente=FuenteEstacion.SINCA)
        )
        sesion.add_all(
            Usuario(nombre=f"J{i}", correo=f"j{i}@demo.sart", rol=Rol.JEFATURA, hash_contrasena="x")
            for i in range(3)
        )
        sesion.flush()
        sesion.add(
            Alerta(
                tipo=TipoAlerta.AMBIENTAL,
                nivel="alerta",
                fecha_emision=AHORA,
                mensaje="MP2,5",
                zona_id=zona.id,
                dia_pronosticado=date(2026, 11, 14),
                valor_mp25=85.0,
            )
        )
        sesion.commit()
        yield sesion
    motor.dispose()


def _notificar(sesion, usuario_id, **cambios) -> Notificacion:
    alerta = sesion.scalars(select(Alerta)).one()
    datos = {
        "alerta_id": alerta.id,
        "usuario_id": usuario_id,
        "estado": EstadoNotificacion.ENVIADA,
        "fecha_envio": AHORA,
    }
    notificacion = Notificacion(**{**datos, **cambios})
    sesion.add(notificacion)
    sesion.commit()
    return notificacion


def _usuarios(sesion) -> list[int]:
    return list(sesion.scalars(select(Usuario.id).order_by(Usuario.id)))


def test_cada_notificacion_tiene_un_token_de_acuse_distinto_y_largo(sesion):
    """RF-15: «un identificador único por notificación», que no se pueda adivinar."""
    tokens = [_notificar(sesion, u).token_acuse for u in _usuarios(sesion)]

    assert len(set(tokens)) == 3
    assert all(len(t) >= 43 and t.replace("-", "").replace("_", "").isalnum() for t in tokens)


def test_reenviada_y_escalada_exigen_su_fecha(sesion):
    """RB-2: reenvío a las 24 h y escalamiento a las 48 h quedan con su hora."""
    usuario = _usuarios(sesion)[0]
    with pytest.raises(IntegrityError):
        _notificar(sesion, usuario, estado=EstadoNotificacion.REENVIADA)
    sesion.rollback()
    with pytest.raises(IntegrityError):
        _notificar(sesion, usuario, estado=EstadoNotificacion.ESCALADA, fecha_reenvio=AHORA)
    sesion.rollback()

    escalada = _notificar(
        sesion, usuario, estado=EstadoNotificacion.ESCALADA, fecha_reenvio=AHORA, fecha_escalamiento=AHORA
    )
    assert escalada.id is not None
