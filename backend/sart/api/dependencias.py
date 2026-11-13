"""Dependencias de FastAPI: sesión de base de datos, usuario de la sesión y control por rol (RNF-S-1, S-2).

Toda ruta que muestre datos de un centro o permita cambios debe declarar ``requiere_rol(...)``; la web solo
decide qué se muestra (``web/src/auth/permissions.ts``), la API es la que niega el acceso.
"""

from __future__ import annotations

from collections.abc import Callable, Iterator
from functools import lru_cache
from typing import Annotated

from fastapi import Cookie, Depends, HTTPException, status
from sqlalchemy import Engine
from sqlalchemy.orm import Session

from sart.api.tokens import NOMBRE_COOKIE, TokenInvalido, leer_token, secreto_valido
from sart.configuracion import obtener_configuracion
from sart.db.modelos import Usuario
from sart.db.sesion import SinBaseDeDatos, crear_motor, url_base_de_datos
from sart.dominio.roles import Rol

SIN_SESION = HTTPException(status.HTTP_401_UNAUTHORIZED, "Sesión no iniciada o vencida.")


@lru_cache
def _motor(url: str) -> Engine:
    return crear_motor(url)


def obtener_sesion_db() -> Iterator[Session]:
    try:
        motor = _motor(url_base_de_datos())
    except SinBaseDeDatos as error:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, str(error)) from None
    with Session(motor) as sesion:
        yield sesion


SesionDB = Annotated[Session, Depends(obtener_sesion_db)]


def secreto_jwt() -> str:
    """JWT_SECRET de la configuración; si falta, es corto o es el de ejemplo, la API no firma sesiones."""
    secreto = obtener_configuracion().jwt_secret
    if not secreto_valido(secreto):
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "Falta configurar JWT_SECRET (al menos 32 caracteres aleatorios; ver .env.example).",
        )
    return secreto


def usuario_actual(
    sesion: SesionDB,
    token: Annotated[str | None, Cookie(alias=NOMBRE_COOKIE)] = None,
) -> Usuario:
    if not token:
        raise SIN_SESION
    try:
        usuario_id = leer_token(token, secreto_jwt())
    except TokenInvalido:
        raise SIN_SESION from None
    usuario = sesion.get(Usuario, usuario_id)
    if usuario is None:  # cuenta dada de baja (RF-16 E2)
        raise SIN_SESION
    return usuario


UsuarioActual = Annotated[Usuario, Depends(usuario_actual)]


def requiere_rol(*roles: Rol) -> Callable[[Usuario], Usuario]:
    """Dependencia que deja pasar solo a los roles indicados (RNF-S-2); a los demás les responde 403."""

    def _revisar(usuario: UsuarioActual) -> Usuario:
        if usuario.rol not in roles:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Su rol no tiene acceso a este recurso.")
        return usuario

    return _revisar
