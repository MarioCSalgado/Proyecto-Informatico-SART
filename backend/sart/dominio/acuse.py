"""Identificador del enlace de acuse de cada notificación (RF-15)."""

from __future__ import annotations

import secrets


def nuevo_token_acuse() -> str:
    """43 caracteres aleatorios (256 bits), seguros para una URL. No se puede adivinar el de otra
    notificación, como sí pasaría con el número correlativo."""
    return secrets.token_urlsafe(32)
