"""MFA de administradores en la base: activación en dos pasos, reinicio y revisión del login (RNF-S-1)."""

from __future__ import annotations

import hmac
from datetime import UTC, datetime
from enum import Enum, auto
from typing import Any

from sqlalchemy.orm import Session

from sart.db.cuentas import buscar_por_correo
from sart.db.modelos import Usuario
from sart.dominio.mfa import bloqueado, nuevo_secreto, tras_fallo, uri_aprovisionamiento, verificar_codigo
from sart.dominio.roles import Rol
from sart.parametros import cargar_parametros


class ErrorMfa(ValueError):
    """No se puede activar, confirmar o reiniciar el MFA. El mensaje se puede mostrar al administrador."""


class ResultadoMfa(Enum):
    CORRECTO = auto()
    FALTA_CODIGO = auto()
    NO_ACTIVADO = auto()
    BLOQUEADO = auto()
    INCORRECTO = auto()


def _administrador(sesion: Session, correo: str) -> Usuario:
    usuario = buscar_por_correo(sesion, correo)
    if usuario is None:
        raise ErrorMfa(f"No existe una cuenta con el correo {correo}.")
    if usuario.rol is not Rol.ADMINISTRADOR:
        raise ErrorMfa("El MFA es solo para cuentas de administrador (RNF-S-1).")
    return usuario


def iniciar_activacion(sesion: Session, correo: str, *, emisor: str) -> tuple[str, str]:
    """Paso 1: genera y guarda un secreto nuevo, todavía sin activar. Devuelve el secreto y su URI."""
    usuario = _administrador(sesion, correo)
    if usuario.mfa_activado_en is not None:
        raise ErrorMfa(
            "Esta cuenta ya tiene MFA activado. Para cambiar de teléfono, use primero reiniciar-mfa."
        )
    usuario.mfa_secreto = nuevo_secreto()
    usuario.mfa_ultimo_paso = None
    sesion.commit()
    return usuario.mfa_secreto, uri_aprovisionamiento(usuario.mfa_secreto, usuario.correo, emisor)


def confirmar_activacion(
    sesion: Session, correo: str, codigo: str, *, ahora: datetime, tolerancia: int
) -> None:
    """Paso 2: un código correcto demuestra que el secreto quedó bien guardado en el teléfono."""
    usuario = _administrador(sesion, correo)
    if usuario.mfa_activado_en is not None:
        raise ErrorMfa("Esta cuenta ya tiene MFA activado.")
    if usuario.mfa_secreto is None:
        raise ErrorMfa("Primero hay que generar el secreto con activar-mfa.")
    paso = verificar_codigo(usuario.mfa_secreto, codigo, ahora=ahora, ultimo_paso=None, tolerancia=tolerancia)
    if paso is None:
        raise ErrorMfa(
            "Código incorrecto. Revise que la hora del teléfono esté bien e intente con el siguiente."
        )
    usuario.mfa_activado_en = ahora
    usuario.mfa_ultimo_paso = paso
    usuario.mfa_intentos_fallidos = 0
    usuario.mfa_bloqueado_hasta = None
    sesion.commit()


def reiniciar(sesion: Session, correo: str) -> None:
    """Borra el MFA de la cuenta (teléfono perdido o cambiado). Después hay que activarlo de nuevo."""
    usuario = _administrador(sesion, correo)
    usuario.mfa_secreto = None
    usuario.mfa_activado_en = None
    usuario.mfa_ultimo_paso = None
    usuario.mfa_intentos_fallidos = 0
    usuario.mfa_bloqueado_hasta = None
    sesion.commit()


def revisar_inicio(
    sesion: Session,
    usuario: Usuario,
    codigo: str | None,
    *,
    ahora: datetime | None = None,
    parametros: dict[str, Any] | None = None,
    codigo_fijo: str | None = None,
) -> ResultadoMfa:
    """Revisa el código de un administrador con la clave ya verificada; guarda fallos, bloqueo y paso.

    ``codigo_fijo`` es el código de desarrollo (``configuracion.codigo_mfa_desarrollo``): se acepta además
    del TOTP, pero no salta el bloqueo ni sirve si la cuenta no tiene MFA activado.
    """
    ahora = ahora or datetime.now(UTC)
    mfa = (parametros or cargar_parametros())["mfa"]
    if usuario.mfa_secreto is None or usuario.mfa_activado_en is None:
        return ResultadoMfa.NO_ACTIVADO
    if bloqueado(usuario.mfa_bloqueado_hasta, ahora):
        return ResultadoMfa.BLOQUEADO
    if not (codigo or "").strip():
        return ResultadoMfa.FALTA_CODIGO
    if codigo_fijo and hmac.compare_digest("".join((codigo or "").split()), codigo_fijo):
        usuario.mfa_intentos_fallidos = 0
        usuario.mfa_bloqueado_hasta = None
        sesion.commit()
        return ResultadoMfa.CORRECTO

    paso = verificar_codigo(
        usuario.mfa_secreto,
        codigo,
        ahora=ahora,
        ultimo_paso=usuario.mfa_ultimo_paso,
        tolerancia=int(mfa["tolerancia_pasos"]),
    )
    if paso is None:
        usuario.mfa_intentos_fallidos, hasta = tras_fallo(
            usuario.mfa_intentos_fallidos,
            maximo=int(mfa["intentos_maximos"]),
            minutos=int(mfa["bloqueo_minutos"]),
            ahora=ahora,
        )
        if hasta is not None:
            usuario.mfa_bloqueado_hasta = hasta
        sesion.commit()
        return ResultadoMfa.INCORRECTO

    usuario.mfa_ultimo_paso = paso
    usuario.mfa_intentos_fallidos = 0
    usuario.mfa_bloqueado_hasta = None
    sesion.commit()
    return ResultadoMfa.CORRECTO
