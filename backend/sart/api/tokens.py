"""JWT de sesión (RNF-S-1). Viaja solo en una cookie httpOnly; la página nunca lo lee."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import jwt

from sart.dominio.roles import Rol

NOMBRE_COOKIE = "sart_sesion"
ALGORITMO = "HS256"
# RFC 7518 §3.2: la clave de HS256 debe tener al menos 256 bits; 32 caracteres aleatorios los cubren.
LARGO_MINIMO_SECRETO = 32
SECRETOS_DE_EJEMPLO = {"cambiar-esto"}


class TokenInvalido(Exception):
    """Token ausente, alterado, vencido o firmado con otro secreto."""


def secreto_valido(secreto: str | None) -> bool:
    return bool(secreto) and secreto not in SECRETOS_DE_EJEMPLO and len(secreto) >= LARGO_MINIMO_SECRETO


def emitir_token(
    *, usuario_id: int, rol: Rol, secreto: str, duracion: timedelta, ahora: datetime | None = None
) -> str:
    ahora = ahora or datetime.now(UTC)
    contenido = {"sub": str(usuario_id), "rol": rol.value, "iat": ahora, "exp": ahora + duracion}
    return jwt.encode(contenido, secreto, algorithm=ALGORITMO)


def leer_token(token: str, secreto: str) -> int:
    """Devuelve el id del usuario. El rol del token no se usa para autorizar: manda el de la base."""
    try:
        contenido = jwt.decode(
            token, secreto, algorithms=[ALGORITMO], options={"require": ["sub", "exp", "iat"]}
        )
        return int(contenido["sub"])
    except (jwt.InvalidTokenError, ValueError) as error:
        raise TokenInvalido(str(error)) from None
