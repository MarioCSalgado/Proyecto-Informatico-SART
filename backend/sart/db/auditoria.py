"""Registro de auditoría (RNF-S-4): quién, cuándo, qué cambió, valor anterior y nuevo, y por qué."""

from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from sart.db.modelos import Auditoria, Usuario

AUTOR_SISTEMA = "sistema"  # tareas programadas, sin usuario


def registrar_auditoria(
    sesion: Session,
    *,
    autor: Usuario | None,
    accion: str,
    entidad: str,
    entidad_id: str | int | None = None,
    anterior: Any = None,
    nuevo: Any = None,
    motivo: str | None = None,
) -> Auditoria:
    """Agrega el registro a la sesión; lo guarda el ``commit`` de quien hace el cambio (misma transacción)."""
    registro = Auditoria(
        autor_id=autor.id if autor else None,
        autor_rol=autor.rol.value if autor else AUTOR_SISTEMA,
        accion=accion,
        entidad=entidad,
        entidad_id=str(entidad_id) if entidad_id is not None else None,
        valor_anterior=anterior,
        valor_nuevo=nuevo,
        motivo=motivo,
    )
    sesion.add(registro)
    return registro
