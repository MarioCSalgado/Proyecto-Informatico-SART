"""Pronóstico de la semana para cada centro con historia (RF-2, RB-4, RF-3 E2). Lógica pura.

- La **semana objetivo** es la siguiente a la fecha de corte (la última semana completa, RB-4), como en el
  Gherkin de RF-2: corte el 27/09/2026 → SE 40.
- El modelo se **reentrena** con todas las semanas completas hasta la fecha de corte, sin los años excluidos
  (RF-2 paso 1); no usa el corte del backtest (``modelo.anio_inicio_prueba``).
- Un centro tiene historia si suma ``modelo.min_semanas_historia`` semanas válidas (RF-2 E1).
- El pronóstico está **desactualizado** si la semana objetivo no es la semana en curso el día de la corrida
  (RF-3 E2, decidido el 14/11): se guarda, pero no emite alertas nuevas.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import date, timedelta

import pandas as pd

from sart.dominio.modelo import ajustar, predecir, terminos_del_modelo, terminos_disponibles
from sart.dominio.semanas import inicio_semana, semana_epidemiologica

ESPECIFICACIONES_DISPONIBLES = ("solo_rezagos",)  # con_pronostico necesita RF-2 E2 (pendientes #40)


@dataclass(frozen=True)
class PronosticoCentro:
    estab: int
    valor: float
    limite_inferior: float
    limite_superior: float


@dataclass
class ResultadoPronostico:
    pronosticos: list[PronosticoCentro]
    sin_historia: list[int] = field(default_factory=list)  # RF-2 E1
    sin_datos_recientes: list[int] = field(default_factory=list)  # con historia, pero sin la semana previa
    terminos: list[str] = field(default_factory=list)


def semana_objetivo(fecha_corte: date) -> date:
    return fecha_corte + timedelta(weeks=1)


def semana_en_curso(dia: date) -> date:
    """Domingo en que empieza la semana epidemiológica de ``dia``."""
    return inicio_semana(*semana_epidemiologica(dia))


def esta_desactualizado(objetivo: date, dia_corrida: date) -> bool:
    return objetivo != semana_en_curso(dia_corrida)


def version_modelo(especificacion: str, version: str) -> str:
    return f"glm-quasipoisson/{especificacion}/v{version}"


def pronosticar_semana(
    panel: pd.DataFrame,
    *,
    fecha_corte: date,
    objetivo: date,
    semanas_invalidas: Iterable[date],
    especificacion: str,
    armonicos: int,
    min_semanas: int,
    nivel_intervalo: float,
) -> ResultadoPronostico:
    """Ajusta el GLM quasi-Poisson y pronostica la fila ``objetivo`` de cada centro con historia.

    ``panel`` viene de ``sart.dominio.panel.construir_panel`` con ``semanas_a_pronosticar=[objetivo]``;
    ``semanas_invalidas`` son las marcadas incompletas (RB-4), que no entran al ajuste.
    """
    if especificacion not in ESPECIFICACIONES_DISPONIBLES:
        raise ValueError(
            f"La corrida semanal solo está disponible con la especificación solo_rezagos (pedida: "
            f"«{especificacion}»): con_pronostico necesita el MP2,5 pronosticado de la semana (RF-2 E2)."
        )
    invalidas = {pd.Timestamp(d) for d in semanas_invalidas}
    validas = panel[
        (panel["inicio_semana"] <= pd.Timestamp(fecha_corte))
        & ~panel["excluido"]
        & panel["y"].notna()
        & ~panel["inicio_semana"].isin(invalidas)
    ]
    semanas = validas.groupby("estab").size()
    con_historia = set(semanas[semanas >= min_semanas].index)
    todos = set(panel["estab"])
    if not con_historia:
        return ResultadoPronostico([], sin_historia=sorted(todos))

    entrenamiento = validas[validas["estab"].isin(con_historia)]
    terminos = terminos_disponibles(entrenamiento, terminos_del_modelo(especificacion, armonicos))
    ajuste = ajustar(entrenamiento, terminos)
    filas = panel[(panel["inicio_semana"] == pd.Timestamp(objetivo)) & panel["estab"].isin(con_historia)]
    estimados = predecir(ajuste, filas, terminos, nivel_intervalo)

    pronosticos = [
        PronosticoCentro(int(f.estab), float(f.pred), float(f.pred_inf), float(f.pred_sup))
        for f in estimados.sort_values("estab").itertuples()
    ]
    return ResultadoPronostico(
        pronosticos,
        sin_historia=sorted(todos - con_historia),
        sin_datos_recientes=sorted(con_historia - {p.estab for p in pronosticos}),
        terminos=terminos,
    )
