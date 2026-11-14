"""Alertas de demanda que se entregan a RF-5 (RF-3 paso 4, RF-5 E2, pendientes #29).

La regla está en ``sart.dominio.alerta_demanda.debe_notificarse``; aquí se busca, por centro y semana, el
nivel más alto ya notificado. Una notificación «fallida» no cuenta como notificada (RF-5 E1): la ALERTA
vuelve a quedar pendiente en la corrida siguiente.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from sart.db.modelos import Alerta, Notificacion, Pronostico
from sart.dominio.alerta_demanda import ORDEN_NIVELES, debe_notificarse
from sart.dominio.valores import EstadoNotificacion, TipoAlerta


def _niveles_notificados(sesion: Session, anio: int, semana: int) -> dict[int, str]:
    """{centro: nivel más alto ya notificado} de las alertas de demanda de esa semana."""
    filas = sesion.execute(
        select(Alerta.centro_id, Alerta.nivel)
        .join(Pronostico, Alerta.pronostico_id == Pronostico.id)
        .join(Notificacion, Notificacion.alerta_id == Alerta.id)
        .where(
            Alerta.tipo == TipoAlerta.DEMANDA,
            Pronostico.anio == anio,
            Pronostico.semana == semana,
            Notificacion.estado != EstadoNotificacion.FALLIDA,
        )
    ).all()
    salida: dict[int, str] = {}
    for centro_id, nivel in filas:
        if centro_id not in salida or ORDEN_NIVELES[nivel] > ORDEN_NIVELES[salida[centro_id]]:
            salida[centro_id] = nivel
    return salida


def alertas_por_notificar(sesion: Session, anio: int, semana: int) -> list[Alerta]:
    """Alertas de demanda del pronóstico vigente de esa semana que RF-5 debe enviar."""
    notificados = _niveles_notificados(sesion, anio, semana)
    vigentes = sesion.scalars(
        select(Alerta)
        .join(Pronostico, Alerta.pronostico_id == Pronostico.id)
        .where(
            Alerta.tipo == TipoAlerta.DEMANDA,
            Pronostico.vigente.is_(True),
            Pronostico.anio == anio,
            Pronostico.semana == semana,
        )
        .order_by(Alerta.centro_id)
    ).all()
    return [a for a in vigentes if debe_notificarse(a.nivel, notificados.get(a.centro_id))]
