"""MFA con códigos TOTP (RFC 6238) para administradores (RNF-S-1). Lógica pura: la hora se recibe.

El intervalo de 30 s y los 6 dígitos no son supuestos del proyecto: son los que usan Google Authenticator,
Authy y Microsoft Authenticator. Lo que sí se puede ajustar (tolerancia, intentos y bloqueo) viene de
``config/parametros.yaml`` (sección ``mfa``).
"""

from __future__ import annotations

import hmac
from datetime import UTC, datetime, timedelta

import pyotp

PASO_SEGUNDOS = 30
DIGITOS = 6


def nuevo_secreto() -> str:
    """Secreto aleatorio en base32 de 32 caracteres (160 bits, lo que recomienda RFC 4226)."""
    return pyotp.random_base32()


def secreto_legible(secreto: str) -> str:
    """El secreto en grupos de 4, para escribirlo a mano en la aplicación."""
    return " ".join(secreto[i : i + 4] for i in range(0, len(secreto), 4))


def uri_aprovisionamiento(secreto: str, cuenta: str, emisor: str) -> str:
    """URI ``otpauth://`` que entienden las aplicaciones de autenticación."""
    return pyotp.TOTP(secreto).provisioning_uri(name=cuenta, issuer_name=emisor)


def verificar_codigo(
    secreto: str, codigo: str | None, *, ahora: datetime, ultimo_paso: int | None, tolerancia: int
) -> int | None:
    """Devuelve el paso de tiempo del código si es válido, o ``None``.

    Acepta el paso actual y ``tolerancia`` pasos antes y después (desfase de reloj del teléfono). Un paso
    igual o anterior a ``ultimo_paso`` se rechaza: así un código ya usado no sirve otra vez.
    """
    codigo = "".join((codigo or "").split())
    if len(codigo) != DIGITOS or not codigo.isdigit():
        return None
    totp = pyotp.TOTP(secreto)
    paso_actual = int(ahora.timestamp()) // PASO_SEGUNDOS
    for paso in range(paso_actual - tolerancia, paso_actual + tolerancia + 1):
        if ultimo_paso is not None and paso <= ultimo_paso:
            continue
        if hmac.compare_digest(totp.at(paso * PASO_SEGUNDOS), codigo):
            return paso
    return None


def _con_zona(momento: datetime) -> datetime:
    # SQLite devuelve las fechas sin zona horaria; en SART se guardan siempre en UTC.
    return momento if momento.tzinfo else momento.replace(tzinfo=UTC)


def bloqueado(bloqueado_hasta: datetime | None, ahora: datetime) -> bool:
    return bloqueado_hasta is not None and ahora < _con_zona(bloqueado_hasta)


def tras_fallo(
    intentos_previos: int, *, maximo: int, minutos: int, ahora: datetime
) -> tuple[int, datetime | None]:
    """Suma un código fallido. Al llegar al máximo devuelve el fin del bloqueo y el conteo vuelve a 0."""
    intentos = intentos_previos + 1
    if intentos >= maximo:
        return 0, ahora + timedelta(minutes=minutos)
    return intentos, None
