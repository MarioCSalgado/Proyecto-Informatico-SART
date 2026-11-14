"""Modelo GLM quasi-Poisson (RF-2, CI-1) con el panel sintético de datos/prueba: corre en CI.

El panel sintético se generó (notebook 5) con un efecto conocido del MP2,5 de la misma semana: +0,4 % por
µg/m³, o sea +4,08 % por cada 10 µg/m³. El modelo con_pronostico debe recuperarlo.
"""

import math

import numpy as np
import pandas as pd
import pytest

from sart.configuracion import RAIZ_REPOSITORIO
from sart.dominio.alerta_demanda import clasificar_demanda, z_del_intervalo
from sart.dominio.modelo import (
    ajustar,
    con_margen,
    dividir,
    evaluar_alertas,
    metricas,
    predecir,
    terminos_del_modelo,
    terminos_disponibles,
    terminos_estacionales,
    variables,
)
from sart.parametros import cargar_parametros

PANEL_PRUEBA = RAIZ_REPOSITORIO / "datos" / "prueba" / "procesados" / "panel_semanal.parquet"
MODELO = cargar_parametros()["modelo"]
EFECTO_REAL_POR_10UG = 100 * (math.exp(10 * 0.004) - 1)  # 4,08 %


@pytest.fixture(scope="module")
def panel():
    return pd.read_parquet(PANEL_PRUEBA)


@pytest.fixture(scope="module")
def entrenamiento_y_prueba(panel):
    return dividir(
        panel,
        anio_inicio_prueba=MODELO["anio_inicio_prueba"],
        anios_excluidos=MODELO["anios_excluidos"],
        min_semanas=MODELO["min_semanas_historia"],
        hasta=panel["inicio_semana"].max(),
    )


def _ajustar_y_predecir(panel, entrenamiento, prueba, especificacion):
    terminos = terminos_disponibles(panel, terminos_del_modelo(especificacion, MODELO["armonicos"]))
    resultado = ajustar(entrenamiento, terminos)
    return resultado, predecir(resultado, prueba, terminos, MODELO["nivel_intervalo"])


# --- Términos
# ---------------------------------------------------------------------------------------------------
def test_las_dos_especificaciones():
    solo = terminos_del_modelo("solo_rezagos", 3)
    con = terminos_del_modelo("con_pronostico", 3)

    assert solo[0] == "C(estab)" and {"s3", "c3", "log_y_l1", "mp25_l1", "temp_l1"} <= set(solo)
    assert set(con) - set(solo) == {"mp25", "temp"}


def test_especificacion_del_sistema_viene_de_los_parametros():
    """Opción C del pendiente #1: el código tiene las dos y el parámetro elige."""
    assert MODELO["especificacion"] == "solo_rezagos"
    with pytest.raises(ValueError, match="desconocida"):
        terminos_del_modelo("otra", 3)


def test_variables_y_estacionalidad():
    assert variables(["C(estab)", "log_y_l1"]) == ["estab", "log_y_l1"]
    estacional = terminos_estacionales([13], 2)
    assert set(estacional) == {"s1", "c1", "s2", "c2"}
    assert estacional["s1"][0] == pytest.approx(math.sin(2 * math.pi * 13 / 52.18))


def test_terminos_sin_datos_suficientes_se_omiten():
    datos = pd.DataFrame({"estab": [1, 2, 3], "mp25": [np.nan, np.nan, 10.0], "temp": [1.0, 2.0, 3.0]})

    assert terminos_disponibles(datos, ["C(estab)", "mp25", "temp", "no_existe"]) == ["C(estab)", "temp"]


# --- División
# -------------------------------------------------------------------------------------------------
def test_division_sin_pandemia_y_hasta_la_semana_completa(panel, entrenamiento_y_prueba):
    entrenamiento, prueba = entrenamiento_y_prueba

    assert not set(entrenamiento["anio"]) & {2020, 2021}
    assert entrenamiento["anio"].max() < MODELO["anio_inicio_prueba"] <= prueba["anio"].min()
    hasta = panel["inicio_semana"].max() - pd.Timedelta(weeks=5)
    _, recortada = dividir(
        panel, anio_inicio_prueba=2024, anios_excluidos=[2020, 2021], min_semanas=52, hasta=hasta
    )
    assert recortada["inicio_semana"].max() == hasta


# --- Ajuste y predicción
# ----------------------------------------------------------------------------------------
def test_recupera_el_efecto_conocido_del_mp25(panel, entrenamiento_y_prueba):
    resultado, _ = _ajustar_y_predecir(panel, *entrenamiento_y_prueba, "con_pronostico")
    inferior, superior = (100 * (math.exp(10 * b) - 1) for b in resultado.conf_int().loc["mp25"])

    assert inferior < EFECTO_REAL_POR_10UG < superior
    assert resultado.scale > 1  # hay sobredispersión: por eso quasi-Poisson


def test_intervalo_ordenado_y_desviacion_coherente_con_rb3(panel, entrenamiento_y_prueba):
    """(límite superior − pronóstico) / z = √(escala × pronóstico): la desviación de la regla de alerta."""
    resultado, d = _ajustar_y_predecir(panel, *entrenamiento_y_prueba, "solo_rezagos")

    assert (d["pred_inf"] >= 0).all()
    assert ((d["pred_inf"] <= d["pred"]) & (d["pred"] <= d["pred_sup"])).all()
    desviacion = (d["pred_sup"] - d["pred"]) / z_del_intervalo(MODELO["nivel_intervalo"])
    assert np.allclose(desviacion, np.sqrt(resultado.scale * d["pred"]))


def test_cobertura_del_intervalo_de_90(panel, entrenamiento_y_prueba):
    """RNF-Q-3: el intervalo de 90 % debe cubrir entre 85 % y 95 % de las semanas observadas."""
    _, d = _ajustar_y_predecir(panel, *entrenamiento_y_prueba, "solo_rezagos")
    cobertura = ((d["y"] >= d["pred_inf"]) & (d["y"] <= d["pred_sup"])).mean()

    assert 0.85 <= cobertura <= 0.95


# --- Métricas y alertas
# -----------------------------------------------------------------------------------------
def test_metricas():
    resultado = metricas(pd.Series([100.0, 200.0]), pd.Series([110.0, 180.0]))

    assert resultado["WAPE_%"] == pytest.approx(100 * 30 / 300)
    assert resultado["MAE"] == 15
    assert resultado["sesgo_%"] == pytest.approx(100 * -10 / 300)


def test_evaluar_alertas():
    d = pd.DataFrame({"y": [120, 80, 130, 90], "pred": [115, 110, 90, 70], "umbral_alerta": [100] * 4})
    resultado = evaluar_alertas(d)

    assert (resultado["aciertos"], resultado["alertas_emitidas"], resultado["semanas_altas_reales"]) == (
        1,
        2,
        2,
    )
    assert resultado["precision"] == resultado["sensibilidad"] == 0.5


def test_con_margen_coincide_con_la_regla_de_tc17():
    d = pd.DataFrame({"pred": [700.0], "pred_sup": [760.0]})
    con = con_margen(d, 0.4, MODELO["nivel_intervalo"]).iloc[0]

    assert round(con) == 715
    nivel = clasificar_demanda(
        700, 760, umbral_atencion=600, umbral_alerta=713, k=0.4, nivel_intervalo=MODELO["nivel_intervalo"]
    )
    assert (con > 713) == (nivel == "alerta")
