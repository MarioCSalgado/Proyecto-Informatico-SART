"""RB-3 · Umbrales de atención (p75) y alerta (p90) de cada centro (RF-3), criterio decidido el 14/11 (#6).

Se recalculan una vez al año con las últimas 52 × anios_umbral = 156 semanas válidas de cada centro hasta la
fecha del recálculo: sin 2020 ni 2021 (modelo.anios_excluidos) y sin semanas marcadas incompletas (RB-4).
Un centro con menos de modelo.min_semanas_historia semanas válidas no tiene umbral (RF-3 E1).
"""

from datetime import date, timedelta

import numpy as np
import pytest

from sart.dominio.umbrales import calcular_umbrales, semanas_de_la_ventana
from sart.parametros import cargar_parametros

PARAMETROS = cargar_parametros()
CRITERIO = {
    "semanas": semanas_de_la_ventana(PARAMETROS["umbrales"]["anios_umbral"]),
    "anios_excluidos": PARAMETROS["modelo"]["anios_excluidos"],
    "cuantil_atencion": PARAMETROS["umbrales"]["cuantil_atencion"],
    "cuantil_alerta": PARAMETROS["umbrales"]["cuantil_alerta"],
    "minimo_semanas": PARAMETROS["modelo"]["min_semanas_historia"],
}
HASTA = date(2026, 3, 1)  # domingo


def _serie(valores, hasta=HASTA) -> dict[date, float]:
    """Una semana por valor, la última empieza el domingo ``hasta``."""
    return {hasta - timedelta(weeks=len(valores) - 1 - i): float(v) for i, v in enumerate(valores)}


def test_la_ventana_es_de_156_semanas():
    assert CRITERIO["semanas"] == 156


def test_cuantiles_de_las_ultimas_156_semanas():
    umbrales = calcular_umbrales({1: _serie(range(1, 201))}, hasta=HASTA, **CRITERIO)

    ultimas = np.arange(45, 201)  # las 156 más recientes
    assert umbrales[1].atencion == pytest.approx(np.quantile(ultimas, 0.75))
    assert umbrales[1].alerta == pytest.approx(np.quantile(ultimas, 0.90))
    assert umbrales[1].semanas == 156


def test_2020_y_2021_no_cuentan_y_la_ventana_busca_mas_atras():
    serie = _serie([100] * 400, hasta=date(2023, 6, 4))
    for inicio in serie:
        if date(2019, 12, 29) <= inicio <= date(2021, 12, 26):  # semanas epidemiológicas de 2020 y 2021
            serie[inicio] = 5000.0

    umbrales = calcular_umbrales({1: serie}, hasta=date(2023, 6, 4), **CRITERIO)

    assert umbrales[1].alerta == pytest.approx(100)
    assert umbrales[1].desde < date(2019, 12, 29)  # tuvo que tomar semanas de 2019


def test_semanas_incompletas_no_cuentan():
    serie = _serie([100] * 200)
    incompleta = HASTA - timedelta(weeks=3)
    serie[incompleta] = 1.0

    umbrales = calcular_umbrales({1: serie}, hasta=HASTA, semanas_invalidas={incompleta}, **CRITERIO)

    assert umbrales[1].atencion == pytest.approx(100)


def test_semanas_posteriores_al_recalculo_no_cuentan():
    serie = _serie([100] * 200, hasta=HASTA + timedelta(weeks=10))
    for i in range(1, 11):
        serie[HASTA + timedelta(weeks=i)] = 9999.0

    assert calcular_umbrales({1: serie}, hasta=HASTA, **CRITERIO)[1].alerta == pytest.approx(100)


def test_centro_con_poca_historia_no_tiene_umbral():
    """RF-3 E1: menos de 52 semanas válidas."""
    umbrales = calcular_umbrales({1: _serie([100] * 51), 2: _serie([100] * 52)}, hasta=HASTA, **CRITERIO)

    assert set(umbrales) == {2}
    assert umbrales[2].semanas == 52  # con menos de 156, usa las que hay


def test_descripcion_de_la_ventana_para_guardar():
    umbrales = calcular_umbrales({1: _serie(range(1, 201))}, hasta=HASTA, **CRITERIO)

    # 2023-03-12 es SE 11 (el 1 de enero de 2023 fue domingo: SE 1); 2026-03-01 es SE 09
    assert umbrales[1].descripcion == "2023-SE11 a 2026-SE09 (156 semanas)"
