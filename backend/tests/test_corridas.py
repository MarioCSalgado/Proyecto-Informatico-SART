"""Registro de corridas y aviso cuando una fuente falla varias veces seguidas (RNF-M-3)."""

import pytest
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session

from sart.db.modelos import Base, Corrida, Zona
from sart.dominio.valores import EstadoCorrida
from sart.tareas.corridas import fallas_seguidas, hay_que_avisar, registrar_corrida


@pytest.fixture
def sesion():
    motor = create_engine("sqlite://")
    Base.metadata.create_all(motor)
    with Session(motor) as sesion:
        yield sesion
    motor.dispose()


def _fallar(sesion, fuente="SINCA"):
    with pytest.raises(RuntimeError), registrar_corrida(sesion, "ingesta", fuente):
        raise RuntimeError("la fuente no respondió")


def _lograr(sesion, fuente="SINCA"):
    with registrar_corrida(sesion, "ingesta", fuente) as corrida:
        corrida.filas = 10


def test_corrida_exitosa_queda_con_fin_y_filas(sesion):
    _lograr(sesion)

    corrida = sesion.scalars(select(Corrida)).one()
    assert corrida.estado is EstadoCorrida.EXITOSA
    assert corrida.fin is not None and corrida.fin >= corrida.inicio
    assert corrida.filas == 10


def test_corrida_fallida_queda_registrada_y_deshace_lo_que_alcanzo_a_hacer(sesion):
    with pytest.raises(ValueError), registrar_corrida(sesion, "ingesta", "DEIS"):
        sesion.add(Zona(nombre="No debería quedar"))
        sesion.flush()
        raise ValueError("archivo con columnas distintas")

    corrida = sesion.scalars(select(Corrida)).one()
    assert corrida.estado is EstadoCorrida.FALLIDA
    assert "ValueError: archivo con columnas distintas" in corrida.mensaje
    assert sesion.scalar(select(func.count()).select_from(Zona)) == 0


def test_fallas_seguidas_por_fuente(sesion):
    _lograr(sesion)
    _fallar(sesion)
    _fallar(sesion)
    _fallar(sesion, fuente="Open-Meteo")

    assert fallas_seguidas(sesion, "SINCA") == 2
    assert fallas_seguidas(sesion, "Open-Meteo") == 1
    assert fallas_seguidas(sesion, "DEIS") == 0


def test_un_exito_corta_la_racha(sesion):
    _fallar(sesion)
    _fallar(sesion)
    _lograr(sesion)

    assert fallas_seguidas(sesion, "SINCA") == 0


def test_avisar_desde_la_segunda_falla_seguida(sesion):
    """parametros.yaml: ingesta.avisar_tras_fallas_seguidas = 2."""
    _fallar(sesion)
    assert hay_que_avisar(sesion, "SINCA") is False
    _fallar(sesion)
    assert hay_que_avisar(sesion, "SINCA") is True
