"""RF-2: el panel semanal armado desde la base (``consulta_semanal`` + ``medicion``) es el del notebook 5.

Regresión con ``datos/prueba``: se carga en la base y se compara con
``datos/prueba/procesados/panel_semanal.parquet``. Ese parquet sintético se generó con el COVID-19 dentro de
``y`` (en el panel real no: ahí ``y`` son solo las 6 causas J00–J98, como piden RF-1 y pendientes #26). Por
eso la prueba hace dos comparaciones:

1. Con el COVID-19 agregado a las causas, el panel coincide **exacto** con el parquet: la migración es fiel.
2. Con los parámetros vigentes, ``y`` es la del parquet menos el COVID-19 y el resto no cambia.
"""

import copy
from datetime import date

import numpy as np
import pandas as pd
import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from sart.configuracion import RAIZ_REPOSITORIO
from sart.db.modelos import CentroSalud
from sart.parametros import cargar_parametros
from sart.tareas.panel import leer_conteos_semanales, panel_desde_la_base

PANEL_NOTEBOOK = RAIZ_REPOSITORIO / "datos" / "prueba" / "procesados" / "panel_semanal.parquet"
CLAVES = ["estab", "inicio_semana"]
COVID = ["covid_identificado", "covid_no_identificado"]
TEXTOS = {
    "nombre_estab",
    "comuna",
    "tipo",
    "estacion",
}  # se comparan aparte (el tipo cambia de glosa a clave)
DEPENDEN_DE_Y = {"y", "y_menores_5", "y_65_y_mas", "y_l1", "y_l2", "y_l52", "log_y_l1", "log_y_l2"}


def _panel(motor, parametros) -> pd.DataFrame:
    with Session(motor) as sesion:
        panel = panel_desde_la_base(sesion, parametros)
        codigos = {c.id: str(c.codigo_antiguo) for c in sesion.scalars(select(CentroSalud))}
    panel["estab"] = panel["estab"].map(codigos)
    return panel.sort_values(CLAVES).reset_index(drop=True)


def _diferencias(a: pd.DataFrame, b: pd.DataFrame, columnas) -> dict[str, int]:
    salida = {}
    for c in columnas:
        if a[c].dtype == bool or b[c].dtype == bool:
            distintas = int((a[c].astype(bool) != b[c].astype(bool)).sum())
        else:
            x, y = a[c].astype(float), b[c].astype(float)
            iguales = np.isclose(x, y, rtol=1e-9, atol=1e-9) | (x.isna() & y.isna())
            distintas = int((~iguales).sum())
        if distintas:
            salida[c] = distintas
    return salida


@pytest.fixture(scope="module")
def notebook():
    return pd.read_parquet(PANEL_NOTEBOOK).sort_values(CLAVES).reset_index(drop=True)


@pytest.fixture
def motor(archivo_base_prueba):
    from sqlalchemy import create_engine

    motor = create_engine(f"sqlite:///{archivo_base_prueba.as_posix()}")  # solo lectura: no hace falta copia
    yield motor
    motor.dispose()


def test_con_las_causas_del_notebook_el_panel_es_identico(motor, notebook):
    parametros = copy.deepcopy(cargar_parametros())
    parametros["ingesta"]["causas_en_consultas"] = [*parametros["ingesta"]["causas_en_consultas"], *COVID]

    panel = _panel(motor, parametros)

    assert set(panel.columns) == set(notebook.columns)
    assert len(panel) == len(notebook) == 9324
    assert (panel[CLAVES] == notebook[CLAVES]).all().all()
    assert _diferencias(panel, notebook, set(notebook.columns) - TEXTOS - set(CLAVES)) == {}
    assert (panel["estacion"] == notebook["estacion"]).all()  # CI-3: misma estación asignada a cada centro


def test_con_los_parametros_vigentes_y_son_solo_las_6_causas(motor, notebook):
    """RF-1 y pendientes #26: el COVID-19 es señal viral, no suma en ``y``."""
    parametros = cargar_parametros()
    panel = _panel(motor, parametros)

    otras = set(notebook.columns) - TEXTOS - set(CLAVES) - DEPENDEN_DE_Y
    assert _diferencias(panel, notebook, otras) == {}

    with Session(motor) as sesion:
        covid = leer_conteos_semanales(sesion, causas_consulta=COVID, causas_virales=COVID)
        codigos = {c.id: str(c.codigo_antiguo) for c in sesion.scalars(select(CentroSalud))}
    covid["estab"] = covid["estab"].map(codigos)
    por_semana = covid[["estab", "anio", "semana", "y"]].rename(columns={"y": "covid"})
    comparacion = (
        notebook[["estab", "anio", "semana", "y"]].merge(por_semana, how="left").fillna({"covid": 0})
    )
    assert np.allclose(panel["y"], comparacion["y"] - comparacion["covid"])


def test_hasta_la_fecha_de_corte_y_fila_a_pronosticar(motor):
    """RB-4: sin consultas posteriores a la fecha de corte; la semana objetivo trae sus rezagos (RF-2)."""
    corte, objetivo = date(2026, 9, 20), date(2026, 9, 27)
    with Session(motor) as sesion:
        panel = panel_desde_la_base(
            sesion, cargar_parametros(), hasta=corte, semanas_a_pronosticar=[objetivo]
        )

    fila = panel[panel["inicio_semana"] == pd.Timestamp(objetivo)]
    previa = panel[panel["inicio_semana"] == pd.Timestamp(corte)].set_index("estab")
    assert len(fila) == 14 and fila["y"].isna().all()
    assert (fila.set_index("estab")["y_l1"] == previa["y"]).all()
    assert panel["inicio_semana"].max() == pd.Timestamp(objetivo)
