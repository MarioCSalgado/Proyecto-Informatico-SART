"""Configuración de entorno de SART: conexiones y secretos (RNF-P-1, RNF-S-1).

Se lee de las variables de entorno y, si existe, del archivo ``.env`` en la raíz del repositorio, así que la
API funciona sin ``--env-file``. Las variables de entorno tienen prioridad sobre el archivo (Docker y CI
pueden sobrescribirlas). Los supuestos del dominio no van aquí, sino en ``config/parametros.yaml`` (RNF-M-4).
"""

from __future__ import annotations

import re
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

RAIZ_REPOSITORIO = Path(__file__).resolve().parents[2]
ARCHIVO_ENV = RAIZ_REPOSITORIO / ".env"


class Configuracion(BaseSettings):
    """Variables de entorno que usa el backend. Las del contenedor de PostgreSQL se ignoran."""

    model_config = SettingsConfigDict(env_file_encoding="utf-8", extra="ignore")

    database_url: str | None = None
    jwt_secret: str | None = None
    sart_parametros: Path | None = None
    # Correo transaccional RF-5; se carga desde el entorno o el archivo .env.
    smtp_host: str | None = None
    smtp_port: int = 587
    smtp_from: str | None = None
    smtp_user: str | None = None
    smtp_password: str | None = None
    smtp_starttls: bool = True
    sart_url_publica: str | None = None
    # Cookie de sesión solo por HTTPS (RNF-S-3). Poner COOKIE_SEGURA=false solo en desarrollo local.
    cookie_segura: bool = True
    # Código MFA fijo para probar en local (pendientes #49). Solo vale con COOKIE_SEGURA=false: ver
    # codigo_mfa_desarrollo(). Nunca definirlo en producción.
    mfa_codigo_desarrollo: str | None = None


def codigo_mfa_desarrollo(configuracion: Configuracion) -> str | None:
    """El código MFA fijo de desarrollo, o ``None`` si no rige (RNF-S-1, pendientes #49).

    Rige solo si está definido, tiene 6 dígitos y la cookie no es segura (``COOKIE_SEGURA=false``, es decir,
    un entorno local por http). En producción la cookie es segura (RNF-S-3) y el código fijo se ignora.
    """
    codigo = (configuracion.mfa_codigo_desarrollo or "").strip()
    if configuracion.cookie_segura or not re.fullmatch(r"\d{6}", codigo):
        return None
    return codigo


def obtener_configuracion() -> Configuracion:
    """Lee la configuración del entorno y del ``.env`` (si no existe, se usa solo el entorno)."""
    return Configuracion(_env_file=ARCHIVO_ENV)
