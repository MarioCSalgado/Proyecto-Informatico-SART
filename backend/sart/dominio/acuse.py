"""Enlace de acuse de cada notificación y plazos de reenvío y escalamiento (RF-15, RB-2)."""

from __future__ import annotations

import secrets
from datetime import datetime, timedelta
from typing import Literal

from sart.dominio.valores import EstadoNotificacion


def nuevo_token_acuse() -> str:
    """43 caracteres aleatorios (256 bits), seguros para una URL. No se puede adivinar el de otra
    notificación, como sí pasaría con el número correlativo."""
    return secrets.token_urlsafe(32)


def paso_rb2(
    estado: EstadoNotificacion,
    fecha_envio: datetime,
    ahora: datetime,
    *,
    reenvio_horas: float,
    escalamiento_horas: float,
) -> Literal["reenviar", "escalar"] | None:
    """RB-2 · RF-15: qué toca con una notificación sin acuse. Plazos de ``notificaciones`` (RNF-M-4).

    Desde la emisión original: a las ``reenvio_horas`` se reenvía una vez; a las ``escalamiento_horas`` se
    avisa al Subdirector, una vez. Confirmada, fallida (RF-15 E2) o ya escalada: nada.
    """
    horas = (ahora - fecha_envio) / timedelta(hours=1)
    if estado in (EstadoNotificacion.ENVIADA, EstadoNotificacion.REENVIADA) and horas >= escalamiento_horas:
        return "escalar"
    if estado is EstadoNotificacion.ENVIADA and horas >= reenvio_horas:
        return "reenviar"
    return None
