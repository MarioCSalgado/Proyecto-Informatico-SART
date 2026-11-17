
"""Selección de destinatarios de alertas para RF-5."""

from sqlalchemy import and_, or_, select
from sqlalchemy.orm import Session

from sart.db.modelos import Alerta, CentroSalud, Usuario
from sart.dominio.roles import Rol
from sart.dominio.valores import TipoAlerta


def destinatarios_de_alerta(sesion: Session, alerta: Alerta) -> list[Usuario]:
    """Devuelve jefaturas pertinentes y subdirectores, sin incluir administradores.

    Demanda: la jefatura debe tener asignado el centro de la alerta.
    Ambiental: debe tener asignado al menos un centro de la zona afectada.
    Subdirector: recibe todas las alertas.
    """
    if alerta.tipo == TipoAlerta.DEMANDA:
        alcance_jefatura = Usuario.centros.any(
            CentroSalud.id == alerta.centro_id
        )
    elif alerta.tipo == TipoAlerta.AMBIENTAL:
        alcance_jefatura = Usuario.centros.any(
            CentroSalud.zona_id == alerta.zona_id
        )
    else:
        raise ValueError(f"Tipo de alerta no reconocido: {alerta.tipo}")

    consulta = (
        select(Usuario)
        .where(
            or_(
                Usuario.rol == Rol.SUBDIRECTOR,
                and_(
                    Usuario.rol == Rol.JEFATURA,
                    alcance_jefatura,
                ),
            )
        )
        .distinct()
        .order_by(Usuario.id)
    )
    return list(sesion.scalars(consulta).all())
