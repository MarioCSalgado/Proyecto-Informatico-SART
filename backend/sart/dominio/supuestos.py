"""Supuestos que el administrador ajusta desde la web (RF-9, RNF-M-4; opción a, pendientes #31). Lógica pura.

``config/parametros.yaml`` es el valor de partida. Un ajuste solo puede tocar una clave de
``administracion.parametros_editables`` y debe tener el mismo tipo que el valor del archivo.
"""

from __future__ import annotations

import copy
import math
from typing import Any

from sart.dominio.alerta_demanda import pronostico_con_margen
from sart.dominio.umbrales import validar_cuantiles

# PostgreSQL devuelve un bigint al sumar las cantidades enteras de consulta_semanal.
MAX_CONTEO_SEMANAL = 2**63 - 1


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


def _validar_numero(vigentes: dict[str, Any], clave: str, valor: int | float) -> int | float:
    if clave == "regla_alerta.k_margen":
        try:
            pronostico_con_margen(
                0, MAX_CONTEO_SEMANAL, k=valor, nivel_intervalo=vigentes["modelo"]["nivel_intervalo"]
            )
        except ValueError as error:
            raise ErrorAjuste("k debe permitir calcular un pronóstico con margen finito.") from error

    if clave == "umbrales.anios_umbral":
        if valor < 1 or valor != int(valor):
            raise ErrorAjuste("La ventana de umbrales debe ser un número entero de años mayor que cero.")
        return int(valor)

    if clave.startswith("umbrales.cuantil_"):
        umbrales = {**vigentes["umbrales"], clave.rsplit(".", 1)[-1]: valor}
        try:
            validar_cuantiles(umbrales["cuantil_atencion"], umbrales["cuantil_alerta"])
        except ValueError as error:
            raise ErrorAjuste(str(error)) from None

    if clave.startswith("dotacion.") and valor == 0:
        raise ErrorAjuste(f"«{clave}» debe ser mayor que cero.")

    if clave in {"notificaciones.reenvio_horas", "notificaciones.escalamiento_horas"}:
        plazos = {**vigentes["notificaciones"], clave.rsplit(".", 1)[-1]: valor}
        if not 0 < plazos["reenvio_horas"] < plazos["escalamiento_horas"]:
            raise ErrorAjuste("El reenvío debe ser posterior al envío y anterior al escalamiento.")
    return valor


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
        return _validar_numero(base, clave, valor)
    if type(valor) is not type(actual):
        raise ErrorAjuste(f"«{clave}» debe ser del mismo tipo que en config/parametros.yaml.")
    return valor
