"""Página de acuse de una notificación (RF-15, TC-06).

- ``GET /acuse/{token_acuse}``: la alerta y el estado del acuse. **No** registra nada: algunos filtros de correo abren
  los enlaces solos (RF-15 paso 2).
- ``POST /acuse/{token_acuse}/confirmar``: el botón «Confirmar lectura». Registra la fecha una sola vez (RF-15 E1) y
  queda en la auditoría (RNF-S-4).

Exigen iniciar sesión y solo el destinatario ve su notificación (pendientes #34, opción recomendada). Un token
ajeno o inventado da 404, para no revelar cuáles existen.
"""

from __future__ import annotations

from datetime import UTC, date, datetime

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select

from sart.api.dependencias import SesionDB, UsuarioActual
from sart.db.auditoria import registrar_auditoria
from sart.db.modelos import Alerta, CentroSalud, Notificacion, Zona
from sart.dominio.valores import EstadoNotificacion

router = APIRouter(prefix="/acuse", tags=["acuse"])


class AlertaAcuse(BaseModel):
    tipo: str
    nivel: str
    mensaje: str
    fecha_emision: datetime
    lugar: str  # centro (demanda) o zona (ambiental)
    dia_pronosticado: date | None


class Acuse(BaseModel):
    estado: EstadoNotificacion
    fecha_envio: datetime
    fecha_confirmacion: datetime | None
    alerta: AlertaAcuse


def _propia(sesion: SesionDB, token: str, usuario: UsuarioActual) -> Notificacion:
    notificacion = sesion.scalar(select(Notificacion).where(Notificacion.token_acuse == token))
    if notificacion is None or notificacion.usuario_id != usuario.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No existe esa notificación para su cuenta.")
    return notificacion


def _acuse(sesion: SesionDB, notificacion: Notificacion) -> Acuse:
    alerta = sesion.get(Alerta, notificacion.alerta_id)
    lugar = sesion.get(CentroSalud, alerta.centro_id) if alerta.centro_id else sesion.get(Zona, alerta.zona_id)
    return Acuse(
        estado=notificacion.estado,
        fecha_envio=notificacion.fecha_envio,
        fecha_confirmacion=notificacion.fecha_confirmacion,
        alerta=AlertaAcuse(
            tipo=alerta.tipo.value,
            nivel=alerta.nivel,
            mensaje=alerta.mensaje,
            fecha_emision=alerta.fecha_emision,
            lugar=lugar.nombre,
            dia_pronosticado=alerta.dia_pronosticado,
        ),
    )


@router.get("/{token_acuse}")
def ver(token_acuse: str, sesion: SesionDB, usuario: UsuarioActual) -> Acuse:
    return _acuse(sesion, _propia(sesion, token_acuse, usuario))


@router.post("/{token_acuse}/confirmar")
def confirmar(token_acuse: str, sesion: SesionDB, usuario: UsuarioActual) -> Acuse:
    notificacion = _propia(sesion, token_acuse, usuario)
    if notificacion.estado is EstadoNotificacion.FALLIDA:
        raise HTTPException(status.HTTP_409_CONFLICT, "Esta notificación no se pudo enviar.")
    if notificacion.fecha_confirmacion is None:  # RF-15 E1: la segunda vez no cambia nada
        notificacion.estado = EstadoNotificacion.CONFIRMADA
        notificacion.fecha_confirmacion = datetime.now(UTC)
        registrar_auditoria(
            sesion, autor=usuario, accion="confirmar_lectura", entidad="notificacion", entidad_id=notificacion.id
        )
        sesion.commit()
    return _acuse(sesion, notificacion)
