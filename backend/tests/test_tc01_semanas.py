"""TC-01 (parte del calendario) · Semanas epidemiológicas del MINSAL y semanas que cruzan el año (RF-1).

Regla: semanas de domingo a sábado; la SE 1 es la primera semana con 4 o más días del año nuevo.
La marca de semana incompleta (la otra mitad de TC-01) depende del criterio de RB-4 (pendientes #3).
"""

from datetime import date, timedelta

import pandas as pd
import pytest

from sart.configuracion import RAIZ_REPOSITORIO
from sart.dominio.semanas import (
    fracciones_de_etiqueta,
    inicio_semana,
    semana_epidemiologica,
    semanas_del_anio,
)

PANEL = RAIZ_REPOSITORIO / "datos" / "prueba" / "procesados" / "panel_semanal.parquet"


@pytest.mark.parametrize(
    ("fecha", "esperado"),
    [
        (date(2026, 1, 1), (2025, 53)),  # su semana (28 dic–3 ene) tiene solo 3 días de 2026
        (date(2026, 1, 3), (2025, 53)),
        (date(2026, 1, 4), (2026, 1)),
        (date(2024, 12, 29), (2025, 1)),  # su semana (29 dic–4 ene) tiene 4 días de 2025
        (date(2020, 12, 31), (2020, 53)),
        (date(2021, 1, 2), (2020, 53)),
        (date(2021, 1, 3), (2021, 1)),
        (date(2026, 9, 27), (2026, 39)),  # Gherkin de RF-1: el pronóstico parte de esta semana
        (date(2026, 10, 4), (2026, 40)),
        (date(2026, 10, 10), (2026, 40)),  # sábado: misma semana
    ],
)
def test_semana_de_una_fecha(fecha, esperado):
    assert semana_epidemiologica(fecha) == esperado


def test_la_semana_empieza_en_domingo():
    assert inicio_semana(2026, 1) == date(2026, 1, 4)
    assert inicio_semana(2026, 1).weekday() == 6  # domingo
    assert inicio_semana(2020, 53) == date(2020, 12, 27)


@pytest.mark.parametrize(("anio", "semanas"), [(2020, 53), (2021, 52), (2025, 53), (2026, 52)])
def test_semanas_por_anio(anio, semanas):
    assert semanas_del_anio(anio) == semanas


def test_semana_fuera_de_rango_es_un_error():
    with pytest.raises(ValueError, match="semana"):
        inicio_semana(2026, 53)


def test_ida_y_vuelta_en_todos_los_dias_de_2014_a_2027():
    dia = date(2014, 1, 1)
    while dia <= date(2027, 12, 31):
        anio, semana = semana_epidemiologica(dia)
        assert inicio_semana(anio, semana) <= dia < inicio_semana(anio, semana) + timedelta(days=7)
        dia += timedelta(days=1)


def test_coincide_con_el_calendario_del_notebook():
    """El panel de prueba lo armó el notebook 5 con la librería epiweeks (CDC = calendario del MINSAL):
    666 semanas de 2014 a 2026 sirven de referencia independiente."""
    panel = pd.read_parquet(PANEL)[["anio", "semana", "inicio_semana"]].drop_duplicates()

    for fila in panel.itertuples():
        assert inicio_semana(fila.anio, fila.semana) == fila.inicio_semana.date()
    assert len(panel) == 666


def test_etiqueta_que_cruza_el_anio_se_reparte_por_dias():
    """El DEIS rotula con (año calendario, número de semana): la etiqueta junta los días de ese año calendario
    que tienen ese número de semana. «2016-52» = 1–2 de enero de 2016 (SE 52 de 2015) más 25–31 de diciembre
    de 2016 (SE 52 de 2016). Se reparte según los días de cada semana (notebook 5, _reasignar_por_dias)."""
    assert fracciones_de_etiqueta(2016, 52) == {
        (2015, 52): pytest.approx(2 / 9),
        (2016, 52): pytest.approx(7 / 9),
    }
    # 1 y 2 de enero de 2021 tienen número 53, pero son de la SE 53 de 2020
    assert fracciones_de_etiqueta(2021, 53) == {(2020, 53): 1.0}
    # 1–3 de enero de 2026 son de la SE 53 de 2025; la SE 1 de 2026 es entera de 2026
    assert fracciones_de_etiqueta(2026, 53) == {(2025, 53): 1.0}
    assert fracciones_de_etiqueta(2026, 1) == {(2026, 1): 1.0}
    assert fracciones_de_etiqueta(2026, 20) == {(2026, 20): 1.0}


def test_etiqueta_sin_dias_es_un_error():
    with pytest.raises(ValueError, match="ningún día"):
        fracciones_de_etiqueta(2026, 54)


def test_tc01_reparto_entero_por_mayor_resto():
    from sart.dominio.ingesta_deis import repartir_entero

    partes = fracciones_de_etiqueta(2016, 52)
    assert repartir_entero(10, partes) == {(2015, 52): 2, (2016, 52): 8}
    for cantidad in range(100):
        resultado = repartir_entero(cantidad, partes)
        assert sum(resultado.values()) == cantidad
        assert resultado == repartir_entero(cantidad, dict(reversed(list(partes.items()))))
    assert repartir_entero(1, {(2025, 1): 0.5, (2024, 1): 0.5}) == {(2025, 1): 0, (2024, 1): 1}
    assert repartir_entero(7, fracciones_de_etiqueta(2026, 53)) == {(2025, 53): 7}