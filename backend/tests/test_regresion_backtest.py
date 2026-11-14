"""Regresión del backtest 2024–2026 del notebook 5 con los datos reales (RF-2, RF-3, RNF-Q-1, RNF-Q-2,
TC-03, TC-04).

Debe reproducir (CLAUDE.md, PASOS.md parte 6), con la especificación ``solo_rezagos``:
- WAPE 14,9 %;
- con k = 0: precisión 0,85 y sensibilidad 0,48;
- con k = 0,4: precisión 0,73 y sensibilidad 0,66;
- línea base «semana anterior»: precisión 0,69 y sensibilidad 0,68.

Usa el panel real que armó el notebook (``datos/procesados/panel_semanal.parquet``, fuera de git) y se
salta si no está, como en CI, donde solo hay ``datos/prueba``. Corre con las reglas del sistema decididas el
14/11: semana de referencia con cobertura de 90 % (RB-4) y umbrales con las últimas 156 semanas válidas del
entrenamiento (RB-3). Con las condiciones del notebook (80 % y los últimos 3 años: 2019, 2022 y 2023) da
exactamente lo mismo: la semana de referencia es la misma (27/09/2026) y esos 3 años suman justo 156 semanas.
Se evalúa, como el notebook, sobre las filas que ambas especificaciones pueden pronosticar.
"""

import pandas as pd
import pytest

from sart.configuracion import RAIZ_REPOSITORIO
from sart.dominio.modelo import (
    ajustar,
    con_margen,
    dividir,
    evaluar_alertas,
    metricas,
    predecir,
    terminos_del_modelo,
    terminos_disponibles,
)
from sart.dominio.semana_completa import evaluar_semanas, ultima_semana_completa
from sart.dominio.umbrales import calcular_umbrales, semanas_de_la_ventana
from sart.parametros import cargar_parametros

PANEL_REAL = RAIZ_REPOSITORIO / "datos" / "procesados" / "panel_semanal.parquet"
PARAMETROS = cargar_parametros()
MODELO, UMBRALES = PARAMETROS["modelo"], PARAMETROS["umbrales"]

pytestmark = pytest.mark.skipif(
    not PANEL_REAL.exists(), reason="sin los datos reales de datos/ (no van a git)"
)


def _semana_de_referencia(panel: pd.DataFrame) -> pd.Timestamp:
    """RB-4 con los parámetros del sistema (cobertura de 90 %)."""
    reportes: dict = {}
    for fila in panel.itertuples():
        reportes.setdefault(fila.inicio_semana.date(), {})[fila.estab] = fila.y
    ingesta = PARAMETROS["ingesta"]
    evaluacion = evaluar_semanas(
        reportes,
        cobertura_minima=ingesta["cobertura_minima_semana"],
        semanas_centros_activos=ingesta["semanas_centros_activos"],
        factor_caida_total=ingesta["factor_caida_total"],
        semanas_mediana_previa=ingesta["semanas_mediana_previa"],
    )
    return pd.Timestamp(ultima_semana_completa(evaluacion))


def _umbrales_del_backtest(entrenamiento: pd.DataFrame) -> pd.DataFrame:
    """RB-3 del sistema: últimas 156 semanas válidas de cada centro hasta el fin del entrenamiento."""
    series = {
        e: dict(zip(g["inicio_semana"].dt.date, g["y"], strict=True))
        for e, g in entrenamiento.groupby("estab")
    }
    umbrales = calcular_umbrales(
        series,
        hasta=entrenamiento["inicio_semana"].max().date(),
        semanas=semanas_de_la_ventana(UMBRALES["anios_umbral"]),
        anios_excluidos=MODELO["anios_excluidos"],
        cuantil_atencion=UMBRALES["cuantil_atencion"],
        cuantil_alerta=UMBRALES["cuantil_alerta"],
        minimo_semanas=MODELO["min_semanas_historia"],
    )
    return pd.DataFrame(
        [{"estab": e, "umbral_atencion": u.atencion, "umbral_alerta": u.alerta} for e, u in umbrales.items()]
    )


@pytest.fixture(scope="module")
def backtest() -> pd.DataFrame:
    """Pronósticos de solo_rezagos 2024–2026 sobre las filas que ambas especificaciones pronostican."""
    panel = pd.read_parquet(PANEL_REAL)
    entrenamiento, prueba = dividir(
        panel,
        anio_inicio_prueba=MODELO["anio_inicio_prueba"],
        anios_excluidos=MODELO["anios_excluidos"],
        min_semanas=MODELO["min_semanas_historia"],
        hasta=_semana_de_referencia(panel),
    )
    prueba = prueba.assign(fila=prueba.index)
    umbrales = _umbrales_del_backtest(entrenamiento)
    predicciones = {}
    for especificacion in ("solo_rezagos", "con_pronostico"):
        terminos = terminos_disponibles(panel, terminos_del_modelo(especificacion, MODELO["armonicos"]))
        resultado = ajustar(entrenamiento, terminos)
        predicciones[especificacion] = predecir(resultado, prueba, terminos, MODELO["nivel_intervalo"]).merge(
            umbrales, on="estab"
        )
    comunes = set.intersection(*(set(d["fila"]) for d in predicciones.values()))
    return predicciones["solo_rezagos"][lambda d: d["fila"].isin(comunes)]


def test_tc03_wape_14_9(backtest):
    """RNF-Q-1 y TC-03: WAPE ≤ 15 % y bajo la línea base."""
    wape = metricas(backtest["y"], backtest["pred"])["WAPE_%"]
    base = backtest.dropna(subset=["y_l1"])

    assert round(wape, 1) == 14.9
    assert wape <= metricas(base["y"], base["y_l1"])["WAPE_%"]


@pytest.mark.parametrize(("k", "precision", "sensibilidad"), [(0, 0.85, 0.48), (0.4, 0.73, 0.66)])
def test_tc04_precision_y_sensibilidad_segun_k(backtest, k, precision, sensibilidad):
    """RNF-Q-2 y TC-04: la regla con margen k (RB-3) en el backtest."""
    d = backtest.assign(con_margen=con_margen(backtest, k, MODELO["nivel_intervalo"]))
    resultado = evaluar_alertas(d, "con_margen")

    assert round(resultado["precision"], 2) == precision
    assert round(resultado["sensibilidad"], 2) == sensibilidad


def test_linea_base_semana_anterior(backtest):
    d = backtest.assign(pred=backtest["y_l1"]).dropna(subset=["pred"])
    resultado = evaluar_alertas(d)

    assert (round(resultado["precision"], 2), round(resultado["sensibilidad"], 2)) == (0.69, 0.68)


def test_tc11_cobertura_del_intervalo(backtest):
    """TC-11, RNF-Q-3: el intervalo de 90 % cubre entre 85 % y 95 % de las semanas (datos reales: 91,1 %)."""
    cobertura = ((backtest["y"] >= backtest["pred_inf"]) & (backtest["y"] <= backtest["pred_sup"])).mean()

    assert 0.85 <= cobertura <= 0.95
    assert round(cobertura, 3) == pytest.approx(0.911, abs=0.002)
