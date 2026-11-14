"""Modelo de pronóstico semanal por centro: GLM de Poisson con escala estimada, o quasi-Poisson (RF-2, CI-1).

Migrado del notebook 5 (``ajustar``, ``predecir``, ``metricas``, ``evaluar_alertas``, ``dividir`` y
``terminos_estacionales``). Tiene dos especificaciones y ``modelo.especificacion`` elige cuál usa el sistema
(opción C del pendiente #1, decidida el 14/11):

- ``solo_rezagos``: solo información disponible al cierre de la semana anterior. Es la del backtest honesto y
  la de las cifras de referencia del informe (WAPE 14,9 %). Es la que usa el sistema por ahora.
- ``con_pronostico``: agrega el MP2,5 y la temperatura de la semana pronosticada (CI-1 y RB-4). Su backtest
  usó los valores observados como pronóstico perfecto: es optimista hasta validarlo con pronósticos reales.

El intervalo es de ``modelo.nivel_intervalo`` (90 %) con la varianza quasi-Poisson (escala × media). La
desviación que usa la regla de alerta, (límite superior − pronóstico) / z, es exactamente √(escala × media).
"""

from __future__ import annotations

import re
from typing import Any

import numpy as np
import pandas as pd
import statsmodels.api as sm
import statsmodels.formula.api as smf

from sart.dominio.alerta_demanda import z_del_intervalo

PERIODO_ANUAL = 52.18  # semanas por año en promedio (definición, no supuesto)
DATOS_MINIMOS = 0.5  # una variable entra al modelo si tiene dato en más de la mitad de las filas


def terminos_estacionales(semana: Any, armonicos: int) -> dict[str, np.ndarray]:
    """Pares seno/coseno de la semana epidemiológica: s1, c1, s2, c2, …"""
    angulo = 2 * np.pi * np.asarray(semana, dtype=float) / PERIODO_ANUAL
    salida: dict[str, np.ndarray] = {}
    for k in range(1, armonicos + 1):
        salida[f"s{k}"], salida[f"c{k}"] = np.sin(k * angulo), np.cos(k * angulo)
    return salida


def terminos_del_modelo(especificacion: str, armonicos: int) -> list[str]:
    estacionalidad = [f"{t}{k}" for k in range(1, armonicos + 1) for t in ("s", "c")]
    base = ["C(estab)", *estacionalidad, "tendencia", "log_y_l1", "log_y_l2", "log_viral_l1"]
    especificaciones = {
        "solo_rezagos": [*base, "mp25_l1", "temp_l1"],
        "con_pronostico": [*base, "mp25_l1", "temp_l1", "mp25", "temp"],
    }
    if especificacion not in especificaciones:
        raise ValueError(f"Especificación desconocida «{especificacion}»: use {', '.join(especificaciones)}.")
    return especificaciones[especificacion]


def variables(terminos: list[str]) -> list[str]:
    """Columnas que usan los términos de la fórmula (``C(estab)`` → ``estab``)."""
    salida = []
    for termino in terminos:
        categorica = re.fullmatch(r"C\((\w+)\)", termino)
        salida.append(categorica.group(1) if categorica else termino)
    return salida


def terminos_disponibles(panel: pd.DataFrame, terminos: list[str]) -> list[str]:
    """Quita los términos sin datos suficientes (p. ej., una estación de SINCA sin mediciones)."""
    return [
        termino
        for termino, columna in zip(terminos, variables(terminos), strict=True)
        if columna in panel.columns and panel[columna].notna().mean() > DATOS_MINIMOS
    ]


def dividir(
    panel: pd.DataFrame,
    *,
    anio_inicio_prueba: int,
    anios_excluidos: list[int],
    min_semanas: int,
    hasta: pd.Timestamp,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Entrenamiento: años anteriores a ``anio_inicio_prueba`` sin los excluidos. Prueba: desde ese año hasta
    la última semana completa ``hasta`` (RB-4). Solo centros con ``min_semanas`` de entrenamiento (RF-2)."""
    validos = panel[~panel["anio"].isin(anios_excluidos)]
    entrenamiento = validos[validos["anio"] < anio_inicio_prueba]
    prueba = panel[(panel["anio"] >= anio_inicio_prueba) & (panel["inicio_semana"] <= hasta)]
    semanas = entrenamiento.groupby("estab").size()
    con_historia = semanas[semanas >= min_semanas].index
    return (
        entrenamiento[entrenamiento["estab"].isin(con_historia)],
        prueba[prueba["estab"].isin(con_historia)],
    )


def ajustar(datos: pd.DataFrame, terminos: list[str]):
    """GLM de Poisson con la escala estimada por chi-cuadrado de Pearson (quasi-Poisson)."""
    d = datos.dropna(subset=[*variables(terminos), "y"])
    formula = "y ~ " + " + ".join(terminos)
    return smf.glm(formula, data=d, family=sm.families.Poisson()).fit(scale="X2")


def predecir(resultado, datos: pd.DataFrame, terminos: list[str], nivel_intervalo: float) -> pd.DataFrame:
    """Pronóstico y su intervalo (``pred``, ``pred_inf``, ``pred_sup``) para las filas con datos completos."""
    d = datos.dropna(subset=variables(terminos)).copy()
    d["pred"] = resultado.predict(d)
    desviacion = np.sqrt(resultado.scale * d["pred"])
    z = z_del_intervalo(nivel_intervalo)
    d["pred_inf"] = (d["pred"] - z * desviacion).clip(lower=0)
    d["pred_sup"] = d["pred"] + z * desviacion
    return d


def metricas(y: pd.Series, pred: pd.Series) -> dict[str, float]:
    """WAPE (RNF-Q-1), MAE, MAPE y sesgo del pronóstico."""
    error = pred - y
    positivos = y > 0
    return {
        "MAE": float(error.abs().mean()),
        "WAPE_%": float(100 * error.abs().sum() / y.sum()),
        "MAPE_%": float(100 * (error[positivos].abs() / y[positivos]).mean()),
        "sesgo_%": float(100 * error.sum() / y.sum()),
        "semanas": int(len(y)),
    }


def evaluar_alertas(d: pd.DataFrame, columna_pred: str = "pred") -> dict[str, float]:
    """Precisión y sensibilidad de las alertas (RNF-Q-2): semana alta = consultas observadas sobre el umbral
    de alerta del centro; alerta = valor de ``columna_pred`` sobre ese umbral."""
    alerta = d[columna_pred] > d["umbral_alerta"]
    evento = d["y"] > d["umbral_alerta"]
    aciertos = int((alerta & evento).sum())
    precision = aciertos / alerta.sum() if alerta.sum() else np.nan
    sensibilidad = aciertos / evento.sum() if evento.sum() else np.nan
    f1 = 2 * precision * sensibilidad / (precision + sensibilidad) if precision and sensibilidad else np.nan
    return {
        "alertas_emitidas": int(alerta.sum()),
        "semanas_altas_reales": int(evento.sum()),
        "aciertos": aciertos,
        "precision": precision,
        "sensibilidad": sensibilidad,
        "F1": f1,
    }


def con_margen(d: pd.DataFrame, k: float, nivel_intervalo: float) -> pd.Series:
    """Pronóstico más el margen de seguridad de RB-3, en forma vectorial: pred + k·(pred_sup − pred)/z."""
    return d["pred"] + k * (d["pred_sup"] - d["pred"]) / z_del_intervalo(nivel_intervalo)
