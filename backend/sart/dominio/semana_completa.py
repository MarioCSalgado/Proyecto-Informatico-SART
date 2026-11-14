"""Marca de semana incompleta (RB-4, RF-1 paso 4, TC-01). Criterio decidido el 14/11 (pendientes #3).

Una semana reciente está completa si (1) reportan al menos ``cobertura_minima`` de los centros activos de las
últimas ``semanas_centros_activos`` semanas y (2) su total no cae bajo ``factor_caida_total`` × la mediana de
las ``semanas_mediana_previa`` semanas anteriores. El segundo criterio detecta centros que reportan a medias.
Migrado del notebook 5 (``semana_de_referencia``). Las semanas más antiguas que la ventana son datos
cerrados y se dan por completas. Valores en ``config/parametros.yaml`` (sección ``ingesta``, RNF-M-4).
"""

from __future__ import annotations

from datetime import date, timedelta
from statistics import median


def evaluar_semanas(
    reportes: dict[date, dict[int, float]],
    *,
    cobertura_minima: float,
    semanas_centros_activos: int,
    factor_caida_total: float,
    semanas_mediana_previa: int,
) -> dict[date, bool]:
    """{inicio de semana: completa} para cada semana de ``reportes`` ({semana: {centro: consultas}})."""
    if not 0 < cobertura_minima <= 1:
        raise ValueError("La cobertura mínima debe estar entre 0 y 1.")
    if not reportes:
        return {}

    semanas = sorted(reportes)
    desde = semanas[-1] - timedelta(weeks=semanas_centros_activos)
    recientes = [s for s in semanas if s >= desde]
    activos = {centro for s in recientes for centro in reportes[s]}

    evaluacion = {s: True for s in semanas if s < desde}
    totales: list[float] = []
    for semana in recientes:
        total = sum(reportes[semana].values())
        cobertura_ok = len(reportes[semana]) >= cobertura_minima * len(activos)
        previas = totales[-semanas_mediana_previa:]
        caida = bool(previas) and total < factor_caida_total * median(previas)
        evaluacion[semana] = cobertura_ok and not caida
        totales.append(total)
    return evaluacion


def ultima_semana_completa(evaluacion: dict[date, bool]) -> date | None:
    """RB-4: el pronóstico parte de esta semana (la más reciente marcada completa)."""
    completas = [s for s, completa in evaluacion.items() if completa]
    return max(completas) if completas else None
