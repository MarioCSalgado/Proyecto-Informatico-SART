"""Regla de alerta de demanda con margen de seguridad (RF-3, RB-3, TC-17).

ALERTA si pronóstico + k·desviación supera el umbral de alerta (p90), con desviación = (límite superior −
pronóstico) / z; atención si el pronóstico, sin margen, supera el umbral de atención (p75); normal en
otro caso.
«Supera» es estrictamente mayor. z sale del nivel del intervalo (``modelo.nivel_intervalo``: 90 % → 1,645) y
k de ``regla_alerta.k_margen`` (RNF-M-4; ajustable por el administrador, RF-9).
"""

from __future__ import annotations

import math
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
    margen = k * desviacion
    if not math.isfinite(margen):
        raise ValueError("El margen de seguridad debe ser finito.")
    return margen


def pronostico_con_margen(
    pronostico: float, limite_superior: float, *, k: float, nivel_intervalo: float
) -> float:
    total = pronostico + margen_de_seguridad(
        pronostico, limite_superior, k=k, nivel_intervalo=nivel_intervalo
    )
    if not math.isfinite(total):
        raise ValueError("El pronóstico con margen debe ser finito.")
    return total


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


ORDEN_NIVELES: dict[str, int] = {"normal": 0, "atencion": 1, "alerta": 2}
NIVEL_QUE_NOTIFICA: NivelDemanda = "alerta"
ETIQUETAS_NIVEL = {"normal": "normal", "atencion": "atención", "alerta": "ALERTA"}  # RNF-U-1: con texto


def debe_notificarse(nivel: NivelDemanda, ya_notificado: NivelDemanda | None) -> bool:
    """RF-3 paso 4 y RF-5 E2 (pendientes #29, decidido el 14/11). Se mira por centro y semana.

    Solo «ALERTA» genera notificación; «atención» se guarda y se muestra en la web (RF-7). ``ya_notificado``
    es el nivel más alto ya notificado de ese centro y esa semana (``None`` si nada): si la corrida se
    repite, se notifica solo si el nivel sube (atención → ALERTA). Otra semana con ALERTA es una alerta nueva.
    """
    if ORDEN_NIVELES[nivel] < ORDEN_NIVELES[NIVEL_QUE_NOTIFICA]:
        return False
    return ya_notificado is None or ORDEN_NIVELES[nivel] > ORDEN_NIVELES[ya_notificado]


def _cifra(valor: float, decimales: int = 0) -> str:
    """Número en formato chileno: punto de miles y coma decimal."""
    texto = f"{valor:,.{decimales}f}"
    return texto.replace(",", "\0").replace(".", ",").replace("\0", ".")


def mensaje_alerta_demanda(
    *,
    nivel: NivelDemanda,
    anio: int,
    semana: int,
    pronostico: float,
    limite_inferior: float,
    limite_superior: float,
    umbral_atencion: float,
    umbral_alerta: float,
    k: float,
    valor_con_margen: float,
) -> str:
    """Texto fijo de la alerta (§5.1: mensaje obligatorio). No lo redacta el LLM (RF-8): solo cifras
    agregadas."""
    base = (
        f"Nivel {ETIQUETAS_NIVEL[nivel]} para la SE {semana} de {anio}: se pronostican {_cifra(pronostico)} "
        f"consultas respiratorias (intervalo de 90 %: {_cifra(limite_inferior)} a {_cifra(limite_superior)})."
    )
    if nivel == "alerta":
        return (
            f"{base} Con el margen de seguridad (k = {_cifra(k, 1)}) son {_cifra(valor_con_margen)}, "
            f"sobre el umbral de alerta de {_cifra(umbral_alerta)} (percentil 90)."
        )
    return f"{base} Supera el umbral de atención de {_cifra(umbral_atencion)} (percentil 75)."
