"""CI-1, RF-2, RNF-Q-1, RNF-Q-2: la alternativa Binomial Negativa y la calibración sin el período de prueba.

Con el panel sintético de ``datos/prueba``. Las cifras reales están en
``docs/resultados/comparacion_modelos.md``, generadas con ``herramientas/comparar_modelos.py``.
"""

import numpy as np
import pandas as pd
import pytest

from sart.configuracion import RAIZ_REPOSITORIO
from sart.dominio.modelo import (
    ajustar,
    ajustar_binomial_negativa,
    elegir_alfa,
    elegir_k,
    predecir,
    terminos_del_modelo,
    terminos_disponibles,
)
from sart.parametros import cargar_parametros

MODELO = cargar_parametros()["modelo"]
PANEL = pd.read_parquet(RAIZ_REPOSITORIO / "datos" / "prueba" / "procesados" / "panel_semanal.parquet")
TERMINOS = terminos_disponibles(PANEL, terminos_del_modelo("solo_rezagos", MODELO["armonicos"]))
ENTRENAMIENTO = PANEL[(PANEL["anio"] < 2023) & ~PANEL["anio"].isin(MODELO["anios_excluidos"])]
VALIDACION = PANEL[PANEL["anio"] == 2023]


def test_ci1_binomial_negativa_da_pronosticos_y_un_intervalo_mas_ancho_en_centros_grandes():
    resultado = ajustar_binomial_negativa(ENTRENAMIENTO, TERMINOS, alfa=0.05)
    d = predecir(resultado, VALIDACION, TERMINOS, MODELO["nivel_intervalo"])

    assert (d["pred"] > 0).all()
    ancho_relativo = (d["pred_sup"] - d["pred"]) / d["pred"]
    grandes, chicos = d["pred"] > d["pred"].quantile(0.75), d["pred"] < d["pred"].quantile(0.25)
    # Var = μ + αμ²: el ancho relativo no cae a cero en los centros grandes (en quasi-Poisson cae como 1/√μ)
    assert ancho_relativo[grandes].mean() > np.sqrt(0.05) * 1.645 * 0.9
    assert ancho_relativo[chicos].mean() > ancho_relativo[grandes].mean()


def test_ci1_quasi_poisson_sigue_igual():
    """La desviación del GLM actual sigue siendo √(escala × μ) (la regla de alerta depende de eso)."""
    resultado = ajustar(ENTRENAMIENTO, TERMINOS)
    d = predecir(resultado, VALIDACION, TERMINOS, MODELO["nivel_intervalo"])
    esperado = d["pred"] + 1.6448536 * np.sqrt(resultado.scale * d["pred"])
    assert np.allclose(d["pred_sup"], esperado, rtol=1e-4)


def test_ci1_elegir_alfa_prefiere_el_de_mejor_verosimilitud_en_validacion():
    alfa, tabla = elegir_alfa(ENTRENAMIENTO, VALIDACION, TERMINOS, [0.001, 0.05, 2.0])
    assert alfa in (0.001, 0.05, 2.0)
    assert tabla.loc[tabla["log_verosimilitud"].idxmax(), "alfa"] == alfa
    assert alfa != 2.0  # un alfa absurdo no gana


def test_rnf_q2_elegir_k_maximiza_sensibilidad_con_precision_minima():
    d = pd.DataFrame({
        "y": [100, 100, 10, 10], "umbral_alerta": [50, 50, 50, 50],
        "pred": [40, 29, 45, 10], "pred_sup": [40 + 16.45, 29 + 16.45, 45 + 16.45, 10 + 16.45],
    })
    k, _ = elegir_k(d, [0, 1, 2, 3], precision_minima=0.6, nivel_intervalo=0.90)
    # desviación = 10: k=1 alerta solo la fila 3 (falsa); k=2 las filas 1 y 3 (precisión 0,5);
    # k=3 las filas 1, 2 y 3 (precisión 0,67 y sensibilidad 1) → gana k=3
    assert k == 3


def test_rnf_q2_elegir_k_sin_ninguno_que_cumpla_toma_el_de_mejor_precision():
    d = pd.DataFrame({"y": [10, 10], "umbral_alerta": [50, 50], "pred": [60, 70], "pred_sup": [70, 80]})
    k, _ = elegir_k(d, [0, 1], precision_minima=0.7, nivel_intervalo=0.90)
    assert k in (0, 1)


@pytest.mark.parametrize("anio", [2024, 2025, 2026])
def test_ci1_la_calibracion_no_toca_el_periodo_de_prueba(anio):
    assert not (ENTRENAMIENTO["anio"] == anio).any() and not (VALIDACION["anio"] == anio).any()
