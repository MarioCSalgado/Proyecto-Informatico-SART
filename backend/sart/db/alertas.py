"""Consultas de alertas de demanda para el envío (RF-5) y el historial (RF-10).

La regla está en ``sart.dominio.alerta_demanda.debe_notificarse``; aquí se busca, por centro y semana, el
nivel más alto ya notificado. Una notificación «fallida» no cuenta como notificada (RF-5 E1): la ALERTA
vuelve a quedar pendiente en la corrida siguiente.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Sequence
from datetime import datetime

from sqlalchemy import Row, and_, func, select, tuple_
from sqlalchemy.orm import Session, joinedload

from sart.db.modelos import (
    Alerta,
    CentroSalud,
    ConsultaSemanal,
    Notificacion,
    Pronostico,
    SemanaCarga,
    UmbralCentro,
)
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


def historial_de_alertas(
    sesion: Session,
    centros: list[CentroSalud],
    causas: list[str],
    *,
    desde: tuple[int, int] | None = None,
    hasta: tuple[int, int] | None = None,
    nivel: str | None = None,
) -> Sequence[Row[tuple[Alerta, CentroSalud, Pronostico, float | None, int | None]]]:
    """RF-10: una fila por alerta emitida, con el pronóstico original y el total observado válido."""
    if not centros:
        return []

    # RB-4: SUM devuelve NULL si no hay una observación válida, y conserva un total real de cero.
    consultas = (
        select(func.sum(ConsultaSemanal.cantidad))
        .join(
            SemanaCarga,
            (SemanaCarga.anio == ConsultaSemanal.anio) & (SemanaCarga.semana == ConsultaSemanal.semana),
        )
        .where(
            ConsultaSemanal.centro_id == Alerta.centro_id,
            ConsultaSemanal.anio == Pronostico.anio,
            ConsultaSemanal.semana == Pronostico.semana,
            ConsultaSemanal.causa.in_(causas),
            SemanaCarga.completa.is_(True),
        )
        .correlate(Alerta, Pronostico)
        .scalar_subquery()
    )
    consulta = (
        select(Alerta, CentroSalud, Pronostico, UmbralCentro.umbral_alerta, consultas)
        .select_from(Alerta)
        .join(CentroSalud, Alerta.centro_id == CentroSalud.id)
        # Las FK identifican cada fila, pero no garantizan que sus centros coincidan (RNF-S-2).
        .join(Pronostico, and_(Alerta.pronostico_id == Pronostico.id, Pronostico.centro_id == CentroSalud.id))
        .outerjoin(
            UmbralCentro,
            and_(Pronostico.umbral_id == UmbralCentro.id, UmbralCentro.centro_id == CentroSalud.id),
        )
        .options(joinedload(Pronostico.dotacion))
        .where(Alerta.tipo == TipoAlerta.DEMANDA, Alerta.centro_id.in_([centro.id for centro in centros]))
        .order_by(
            Pronostico.anio.desc(), Pronostico.semana.desc(), Alerta.fecha_emision.desc(), Alerta.id.desc()
        )
    )
    semana_objetivo = tuple_(Pronostico.anio, Pronostico.semana)
    if desde is not None:
        consulta = consulta.where(semana_objetivo >= tuple_(*desde))
    if hasta is not None:
        consulta = consulta.where(semana_objetivo <= tuple_(*hasta))
    if nivel is not None:
        consulta = consulta.where(Alerta.nivel == nivel)
    return sesion.execute(consulta).all()


def acuses_propios(
    sesion: Session, alertas: list[int], usuario_id: int
) -> dict[int, tuple[EstadoNotificacion, datetime | None]]:
    """Lee solo el estado y el acuse del destinatario autenticado (RF-10, RNF-S-2)."""
    if not alertas:
        return {}
    filas = sesion.execute(
        select(Notificacion.alerta_id, Notificacion.estado, Notificacion.fecha_confirmacion).where(
            Notificacion.alerta_id.in_(alertas), Notificacion.usuario_id == usuario_id
        )
    )
    return {alerta_id: (estado, fecha) for alerta_id, estado, fecha in filas}


def resumen_notificaciones(sesion: Session, alertas: list[int]) -> dict[int, dict[EstadoNotificacion, int]]:
    """Cuenta estados por alerta sin recuperar destinatarios ni credenciales de acuse (RF-10)."""
    if not alertas:
        return {}
    filas = sesion.execute(
        select(Notificacion.alerta_id, Notificacion.estado, func.count())
        .where(Notificacion.alerta_id.in_(alertas))
        .group_by(Notificacion.alerta_id, Notificacion.estado)
    )
    resumen: dict[int, dict[EstadoNotificacion, int]] = defaultdict(dict)
    for alerta_id, estado, total in filas:
        resumen[alerta_id][estado] = total
    return dict(resumen)
