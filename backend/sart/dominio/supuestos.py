"""Supuestos que el administrador ajusta desde la web (RF-9, RNF-M-4; opción a, pendientes #31). Lógica pura.

``config/parametros.yaml`` es el valor de partida. Un ajuste solo puede tocar una clave de
``administracion.parametros_editables`` y debe tener el mismo tipo que el valor del archivo.
"""

from __future__ import annotations

import copy
import math
from typing import Any


class ErrorAjuste(ValueError):
    """El ajuste no se puede guardar. El mensaje se puede mostrar al administrador."""


def valor_en(parametros: dict[str, Any], clave: str) -> Any:
    """Valor en una ruta con puntos, p. ej. ``dotacion.horas_funcionamiento_semana.SAPU``."""
    actual: Any = parametros
    for parte in clave.split("."):
        if not isinstance(actual, dict) or parte not in actual:
            raise KeyError(clave)
        actual = actual[parte]
    return actual


def aplicar_ajustes(base: dict[str, Any], ajustes: dict[str, Any]) -> dict[str, Any]:
    """Copia de ``base`` con los ajustes encima. ``base`` no se modifica."""
    resultado = copy.deepcopy(base)
    for clave, valor in ajustes.items():
        *ruta, ultima = clave.split(".")
        destino = resultado
        for parte in ruta:
            destino = destino[parte]
        destino[ultima] = valor
    return resultado


def _es_numero(valor: Any) -> bool:
    return isinstance(valor, int | float) and not isinstance(valor, bool)


def validar_ajuste(base: dict[str, Any], clave: str, valor: Any, editables: list[str]) -> Any:
    """Devuelve el valor si se puede guardar; si no, lanza ``ErrorAjuste`` con el motivo."""
    if clave not in editables:
        raise ErrorAjuste(f"«{clave}» no se puede ajustar desde la web; se cambia en config/parametros.yaml.")
    try:
        actual = valor_en(base, clave)
    except KeyError:
        raise ErrorAjuste(f"«{clave}» no existe en config/parametros.yaml.") from None

    if actual is None or _es_numero(actual):  # null: supuesto aún sin definir, p. ej. las horas del SUR
        if not _es_numero(valor) or not math.isfinite(valor):
            raise ErrorAjuste(f"«{clave}» debe ser un número.")
        if valor < 0:
            raise ErrorAjuste(f"«{clave}» no puede ser negativo.")
        return valor
    if type(valor) is not type(actual):
        raise ErrorAjuste(f"«{clave}» debe ser del mismo tipo que en config/parametros.yaml.")
    return valor
