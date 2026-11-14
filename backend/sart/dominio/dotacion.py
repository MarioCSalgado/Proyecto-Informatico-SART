"""Dotación sugerida en hora punta con teoría de colas M/M/c y la fórmula de Erlang C (RF-6, CI-2, TC-07).

Migrado del notebook 5 (``erlang_c``, ``espera_media_min``, ``llegadas_hora_punta``, ``dotacion_minima``), con
una diferencia que pide la especificación: las horas de funcionamiento dependen del tipo de centro (123 h
en SAPU y SAR, 168 h en hospitales); el notebook usaba 168 h para todos. Los supuestos vienen de la sección
``dotacion`` de ``config/parametros.yaml`` (RNF-M-4) y se devuelven junto al resultado, como pide RF-6.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any

from sart.dominio.valores import TipoCentro

MAXIMO_PROFESIONALES = 500  # tope de la búsqueda: una cifra mayor indica supuestos mal cargados


class ErrorDotacion(ValueError):
    """Los supuestos no permiten calcular la dotación. El mensaje se puede mostrar."""


@dataclass(frozen=True)
class Dotacion:
    llegadas_por_hora: float  # en hora punta
    profesionales: int
    espera_media_min: float
    supuestos: dict[str, Any] = field(default_factory=dict)  # RF-6 paso 3: a la vista con el resultado


def erlang_c(c: int, carga: float) -> float:
    """Probabilidad de que un paciente espere, con ``c`` profesionales y ``carga`` = λ/μ erlangs."""
    if carga <= 0:
        return 0.0
    if c <= carga:
        return 1.0
    b = 1.0  # Erlang B por recurrencia, numéricamente estable
    for k in range(1, c + 1):
        b = carga * b / (k + carga * b)
    return c * b / (c - carga * (1 - b))


def espera_media_min(c: int, llegadas_por_hora: float, minutos_por_atencion: float) -> float:
    """Espera media en la fila, en minutos. Infinita si la capacidad no alcanza a las llegadas."""
    mu = 60 / minutos_por_atencion  # atenciones por hora de cada profesional
    if c * mu <= llegadas_por_hora:
        return math.inf
    return 60 * erlang_c(c, llegadas_por_hora / mu) / (c * mu - llegadas_por_hora)


def llegadas_hora_punta(consultas_semana: float, horas_semana: float, factor_punta: float) -> float:
    """RF-6 paso 1: pronóstico semanal / horas de funcionamiento × factor de hora punta."""
    return consultas_semana / horas_semana * factor_punta


def dotacion_minima(llegadas_por_hora: float, minutos_por_atencion: float, espera_objetivo_min: float) -> int:
    """RF-6 paso 2: menor número de profesionales que deja la espera media en el objetivo o bajo él."""
    if espera_objetivo_min <= 0:
        raise ErrorDotacion("La espera objetivo debe ser mayor que cero.")
    c = max(1, math.ceil(llegadas_por_hora * minutos_por_atencion / 60))
    while espera_media_min(c, llegadas_por_hora, minutos_por_atencion) > espera_objetivo_min:
        c += 1
        if c > MAXIMO_PROFESIONALES:
            raise ErrorDotacion("Ninguna dotación razonable cumple la espera objetivo: revise los supuestos.")
    return c


def horas_funcionamiento(tipo: TipoCentro, supuestos: dict[str, Any]) -> float:
    horas = supuestos["horas_funcionamiento_semana"].get(tipo.value)
    if horas is None:
        raise ErrorDotacion(
            f"Las horas de funcionamiento de un {tipo.value} no están definidas "
            "(dotacion.horas_funcionamiento_semana en parametros.yaml): no se puede sugerir dotación."
        )
    if horas <= 0:
        raise ErrorDotacion(f"Las horas de funcionamiento de un {tipo.value} deben ser mayores que cero.")
    return float(horas)


def recomendar_dotacion(consultas_semana: float, tipo: TipoCentro, supuestos: dict[str, Any]) -> Dotacion:
    """Profesionales sugeridos en hora punta para un pronóstico semanal (solo demanda respiratoria)."""
    if consultas_semana < 0:
        raise ErrorDotacion("El pronóstico de consultas no puede ser negativo.")
    horas = horas_funcionamiento(tipo, supuestos)
    minutos = float(supuestos["minutos_por_atencion"])
    objetivo = float(supuestos["espera_objetivo_min"])
    factor = float(supuestos["factor_hora_punta"])

    llegadas = llegadas_hora_punta(consultas_semana, horas, factor)
    profesionales = dotacion_minima(llegadas, minutos, objetivo)
    return Dotacion(
        llegadas_por_hora=llegadas,
        profesionales=profesionales,
        espera_media_min=espera_media_min(profesionales, llegadas, minutos),
        supuestos={
            "horas_funcionamiento_semana": supuestos["horas_funcionamiento_semana"][tipo.value],
            "factor_hora_punta": supuestos["factor_hora_punta"],
            "minutos_por_atencion": supuestos["minutos_por_atencion"],
            "espera_objetivo_min": supuestos["espera_objetivo_min"],
        },
    )
