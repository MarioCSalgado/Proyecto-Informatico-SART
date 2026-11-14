"""Reglas para leer mediciones ambientales (RF-1, RF-4). Lógica pura."""

from __future__ import annotations

from typing import Any

from sart.dominio.valores import CalidadDato


def _numero(texto: Any) -> float | None:
    if texto is None:
        return None
    limpio = str(texto).strip()
    if limpio == "" or limpio.lower() == "nan":
        return None
    return float(limpio.replace(",", "."))


def valor_sinca(validado: Any, preliminar: Any, no_validado: Any) -> tuple[float, CalidadDato] | None:
    """Valor diario de SINCA con su calidad: validado antes que preliminar, y este antes que no validado.

    ``None`` si no hay dato o el valor es negativo (una concentración no puede serlo).
    """
    for texto, calidad in (
        (validado, CalidadDato.VALIDADO),
        (preliminar, CalidadDato.PRELIMINAR),
        (no_validado, CalidadDato.NO_VALIDADO),
    ):
        valor = _numero(texto)
        if valor is not None:
            return (valor, calidad) if valor >= 0 else None
    return None
