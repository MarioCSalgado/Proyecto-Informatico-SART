"""Configuración de entorno de SART: conexiones y secretos (RNF-P-1, RNF-S-1).

Se lee de las variables de entorno y, si existe, del archivo ``.env`` en la raíz del repositorio, así que la
API funciona sin ``--env-file``. Las variables de entorno tienen prioridad sobre el archivo (Docker y CI
pueden sobrescribirlas). Los supuestos del dominio no van aquí, sino en ``config/parametros.yaml`` (RNF-M-4).
"""

from __future__ import annotations

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


def obtener_configuracion() -> Configuracion:
    """Lee la configuración del entorno y del ``.env`` (si no existe, se usa solo el entorno)."""
    return Configuracion(_env_file=ARCHIVO_ENV)
