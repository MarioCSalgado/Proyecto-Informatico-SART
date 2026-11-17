"""TC-01 (marca de semana incompleta) · RB-4 y RF-1 paso 4, criterio decidido el 14/11 (pendientes #3).

Una semana está completa si reportan al menos el 90 % de los centros activos de las últimas 12 semanas y su
total no cae bajo 0,6 × la mediana de las 4 semanas anteriores. Valores de config/parametros.yaml (ingesta).

Gherkin de RF-1: la semana del 4 de octubre de 2026 trae datos de 29 de los 33 centros → queda incompleta y el
pronóstico parte de la semana del 27 de septiembre.
"""

from datetime import date, timedelta

import pytest

from sart.dominio.semana_completa import evaluar_semanas, ultima_semana_completa
from sart.parametros import cargar_parametros

INGESTA = cargar_parametros()["ingesta"]
CRITERIO = {
    "cobertura_minima": INGESTA["cobertura_minima_semana"],
    "semanas_centros_activos": INGESTA["semanas_centros_activos"],
    "factor_caida_total": INGESTA["factor_caida_total"],
    "semanas_mediana_previa": INGESTA["semanas_mediana_previa"],
}
ULTIMA_NORMAL = date(2026, 9, 27)


def _historia(semanas=13, centros=33, por_centro=30) -> dict[date, dict[int, float]]:
    """Semanas normales hasta el 27/09/2026: todos los centros, 30 consultas cada uno."""
    return {
        ULTIMA_NORMAL - timedelta(weeks=i): {c: por_centro for c in range(centros)} for i in range(semanas)
    }


def test_tc01_gherkin_29_de_33_centros():
    reportes = _historia()
    reportes[date(2026, 10, 4)] = {c: 30 for c in range(29)}

    evaluacion = evaluar_semanas(reportes, **CRITERIO)

    assert evaluacion[date(2026, 10, 4)] is False
    assert ultima_semana_completa(evaluacion) == ULTIMA_NORMAL


def test_30_de_33_centros_alcanza_el_90_por_ciento():
    reportes = _historia()
    reportes[date(2026, 10, 4)] = {c: 30 for c in range(30)}

    assert evaluar_semanas(reportes, **CRITERIO)[date(2026, 10, 4)] is True


def test_todos_los_centros_pero_cargados_a_medias():
    """El segundo criterio: reportan los 33, pero el total cae a un tercio de lo habitual."""
    reportes = _historia()
    reportes[date(2026, 10, 4)] = {c: 10 for c in range(33)}

    evaluacion = evaluar_semanas(reportes, **CRITERIO)

    assert evaluacion[date(2026, 10, 4)] is False
    assert ultima_semana_completa(evaluacion) == ULTIMA_NORMAL


def test_una_baja_moderada_no_es_incompleta():
    reportes = _historia()
    reportes[date(2026, 10, 4)] = {c: 20 for c in range(33)}  # 660 > 0,6 × 990 = 594

    assert evaluar_semanas(reportes, **CRITERIO)[date(2026, 10, 4)] is True


def test_solo_se_evaluan_las_semanas_recientes():
    """Las semanas viejas son datos ya cerrados: se dan por completas aunque hayan sido bajas."""
    reportes = _historia(semanas=30)
    vieja = ULTIMA_NORMAL - timedelta(weeks=25)
    reportes[vieja] = {c: 5 for c in range(20)}

    evaluacion = evaluar_semanas(reportes, **CRITERIO)

    assert evaluacion[vieja] is True
    assert ultima_semana_completa(evaluacion) == ULTIMA_NORMAL


def test_sin_semanas():
    assert evaluar_semanas({}, **CRITERIO) == {}
    assert ultima_semana_completa({}) is None


def test_cobertura_invalida_es_un_error():
    with pytest.raises(ValueError, match="cobertura"):
        evaluar_semanas(_historia(), **{**CRITERIO, "cobertura_minima": 1.5})


def test_tc01_bordes_exactos_de_cobertura_y_caida():
    reportes = _historia(centros=10, por_centro=30)
    reportes[date(2026, 10, 4)] = {c: 20 for c in range(9)}  # 90 %, total 180 = 0,6 × 300
    assert evaluar_semanas(reportes, **CRITERIO)[date(2026, 10, 4)] is True
    reportes[date(2026, 10, 4)][0] = 19
    assert evaluar_semanas(reportes, **CRITERIO)[date(2026, 10, 4)] is False