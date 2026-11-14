"""Regla de alerta de demanda con margen de seguridad (RF-3, RB-3, TC-17).

ALERTA si pronóstico + k·desviación supera el umbral de alerta (p90), con desviación = (límite superior −
pronóstico) / z; atención si el pronóstico, sin margen, supera el umbral de atención (p75); normal en
otro caso.
«Supera» es estrictamente mayor. z sale del nivel del intervalo (``modelo.nivel_intervalo``: 90 % → 1,645) y
k de ``regla_alerta.k_margen`` (RNF-M-4; ajustable por el administrador, RF-9).
"""

from __future__ import annotations

from typing import Literal

from scipy.stats import norm

NivelDemanda = Literal["normal", "atencion", "alerta"]


def z_del_intervalo(nivel_intervalo: float) -> float:
    """Cuantil normal de un intervalo bilateral: 0,90 → 1,645."""
    if not 0 < nivel_intervalo < 1:
        raise ValueError("El nivel del intervalo debe estar entre 0 y 1.")
    return float(norm.ppf(1 - (1 - nivel_intervalo) / 2))


def margen_de_seguridad(
    pronostico: float, limite_superior: float, *, k: float, nivel_intervalo: float
) -> float:
    if limite_superior < pronostico:
        raise ValueError("El límite superior del intervalo no puede ser menor que el pronóstico.")
    if k < 0:
        raise ValueError("k no puede ser negativo.")
    desviacion = (limite_superior - pronostico) / z_del_intervalo(nivel_intervalo)
    return k * desviacion


def pronostico_con_margen(
    pronostico: float, limite_superior: float, *, k: float, nivel_intervalo: float
) -> float:
    return pronostico + margen_de_seguridad(pronostico, limite_superior, k=k, nivel_intervalo=nivel_intervalo)


def clasificar_demanda(
    pronostico: float,
    limite_superior: float,
    *,
    umbral_atencion: float,
    umbral_alerta: float,
    k: float,
    nivel_intervalo: float,
) -> NivelDemanda:
    """Nivel de un centro para la semana pronosticada (RF-3 paso 3). El margen solo se aplica al p90."""
    if (
        pronostico_con_margen(pronostico, limite_superior, k=k, nivel_intervalo=nivel_intervalo)
        > umbral_alerta
    ):
        return "alerta"
    if pronostico > umbral_atencion:
        return "atencion"
    return "normal"
