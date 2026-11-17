"""Parámetros vigentes = ``config/parametros.yaml`` + ajustes del administrador (RF-9, opción a, RNF-S-4).

Las corridas deben leer ``parametros_vigentes(sesion)``, no ``cargar_parametros()``, para que un ajuste
rija en la corrida siguiente.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import select, text, update
from sqlalchemy.orm import Session

from sart.db.auditoria import registrar_auditoria
from sart.db.modelos import ParametroAjustado, Usuario
from sart.dominio.supuestos import ErrorAjuste, aplicar_ajustes, validar_ajuste, valor_en
from sart.parametros import cargar_parametros


def _ajustes_vigentes(sesion: Session) -> dict[str, Any]:
    filas = sesion.scalars(select(ParametroAjustado).where(ParametroAjustado.vigente.is_(True)))
    return {f.clave: f.valor for f in filas}


def parametros_vigentes(sesion: Session, base: dict[str, Any] | None = None) -> dict[str, Any]:
    return aplicar_ajustes(base or cargar_parametros(), _ajustes_vigentes(sesion))


def ajustar_parametro(
    sesion: Session, clave: str, valor: Any, *, autor: Usuario, motivo: str
) -> ParametroAjustado:
    """Guarda el ajuste (reemplaza al anterior de la misma clave) y lo deja en la auditoría."""
    motivo = (motivo or "").strip()
    if not motivo:
        raise ErrorAjuste("El motivo del cambio es obligatorio.")
    base = cargar_parametros()
    # Serializar escrituras para validar cuantiles y plazos con el último ajuste confirmado.
    if sesion.get_bind().dialect.name == "postgresql":
        sesion.execute(text("LOCK TABLE parametro_ajustado IN SHARE ROW EXCLUSIVE MODE"))
    vigentes = parametros_vigentes(sesion, base)
    valor = validar_ajuste(vigentes, clave, valor, base["administracion"]["parametros_editables"])
    anterior = valor_en(vigentes, clave)

    sesion.execute(
        update(ParametroAjustado)
        .where(ParametroAjustado.clave == clave, ParametroAjustado.vigente.is_(True))
        .values(vigente=False)
    )
    ajuste = ParametroAjustado(clave=clave, valor=valor, motivo=motivo, autor_id=autor.id)
    sesion.add(ajuste)
    registrar_auditoria(
        sesion,
        autor=autor,
        accion="cambio_parametro",
        entidad="parametro",
        entidad_id=clave,
        anterior=anterior,
        nuevo=valor,
        motivo=motivo,
    )
    sesion.commit()
    return ajuste
