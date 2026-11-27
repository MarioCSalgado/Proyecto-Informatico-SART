"""TC-19, RF-10: la corrida semanal puede reproducir una semana pasada sin usar información futura.

Con ``fecha_corte`` se pronostica la semana siguiente a esa fecha usando solo las consultas hasta ella, y la
alerta queda con la fecha de emisión de ese lunes (para el historial). Las cifras del invierno 2025 con los
datos reales están en ``docs/resultados/tc19_invierno_2025.md`` (``herramientas/reproducir_invierno.py``).
"""

from datetime import UTC, date, datetime, timedelta

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from sart.db.modelos import Alerta, Pronostico
from sart.dominio.semanas import semana_epidemiologica
from sart.tareas.semanal import ErrorCorridaSemanal, correr_semanal
from sart.tareas.semanas_y_umbrales import recalcular_umbrales

CORTE = date(2025, 6, 1)  # domingo de la SE 23 de 2025 (datos/prueba llega a 2026)
EMISION = datetime(2025, 6, 9, 10, tzinfo=UTC)  # lunes 06:00 en Santiago


@pytest.fixture
def sesion(base_prueba):
    with Session(base_prueba) as sesion:
        recalcular_umbrales(sesion, hasta=date(2025, 2, 23))  # RB-3 de marzo de 2025: sin datos posteriores
        yield sesion


def test_tc19_pronostica_la_semana_siguiente_al_corte(sesion):
    resumen = correr_semanal(sesion, fecha_corte=CORTE, emision=EMISION)

    objetivo = CORTE + timedelta(weeks=1)
    assert (resumen.anio, resumen.semana) == semana_epidemiologica(objetivo)
    assert resumen.fecha_corte == CORTE and not resumen.desactualizado
    pronosticos = sesion.scalars(select(Pronostico).where(Pronostico.vigente.is_(True))).all()
    assert pronosticos and all(p.fecha_corte == CORTE for p in pronosticos)


def test_tc19_las_alertas_quedan_con_la_emision_de_ese_lunes(sesion):
    correr_semanal(sesion, fecha_corte=CORTE, emision=EMISION)

    alertas = sesion.scalars(select(Alerta)).all()
    assert all(a.fecha_emision.replace(tzinfo=UTC) == EMISION for a in alertas)


def test_tc19_no_usa_consultas_posteriores_al_corte(sesion, monkeypatch):
    """El panel se arma con ``hasta = fecha_corte``: lo posterior no entra al entrenamiento."""
    import sart.tareas.semanal as semanal

    vistos = {}
    original = semanal.panel_desde_la_base

    def espia(sesion, parametros, *, hasta=None, semanas_a_pronosticar=()):
        vistos["hasta"] = hasta
        panel = original(sesion, parametros, hasta=hasta, semanas_a_pronosticar=semanas_a_pronosticar)
        vistos["max_con_y"] = panel.dropna(subset=["y"])["inicio_semana"].max()
        return panel

    monkeypatch.setattr(semanal, "panel_desde_la_base", espia)
    correr_semanal(sesion, fecha_corte=CORTE, emision=EMISION)

    assert vistos["hasta"] == CORTE
    assert vistos["max_con_y"].date() <= CORTE


def test_tc19_un_corte_posterior_a_la_ultima_semana_completa_se_rechaza(sesion):
    with pytest.raises(ErrorCorridaSemanal, match="última semana completa"):
        correr_semanal(sesion, fecha_corte=date(2030, 1, 6), emision=EMISION)
