"""Roles de SART con mínimo privilegio (RNF-S-2, §2.4)."""

from enum import StrEnum


class Rol(StrEnum):
    """Los tres roles de RNF-S-2. Los permisos de cada uno están en ``web/src/auth/permissions.ts`` y la API
    los vuelve a revisar."""

    JEFATURA = "jefatura"
    SUBDIRECTOR = "subdirector"
    ADMINISTRADOR = "administrador"
