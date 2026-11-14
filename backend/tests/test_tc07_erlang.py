"""TC-07 · Cálculo de Erlang C y dotación mínima en hora punta (RF-6, CI-2).

Gherkin de RF-6: 545 consultas semanales en un SAR que atiende 123 h → 7,1 llegadas por hora en hora punta;
3 profesionales con 4,2 minutos de espera media; con 2 profesionales la espera sería de 55 minutos.
Los supuestos (15 min, factor 1,6, espera objetivo 30 min, horas por tipo) vienen de parametros.yaml
(RNF-M-4).
"""

import math

import pytest

from sart.dominio.dotacion import (
    ErrorDotacion,
    dotacion_minima,
    erlang_c,
    espera_media_min,
    horas_funcionamiento,
    llegadas_hora_punta,
    recomendar_dotacion,
)
from sart.dominio.valores import TipoCentro
from sart.parametros import cargar_parametros

PARAMETROS = cargar_parametros()


def test_tc07_gherkin_de_rf6():
    dotacion = recomendar_dotacion(545, TipoCentro.SAR, PARAMETROS["dotacion"])

    assert round(dotacion.llegadas_por_hora, 1) == 7.1
    assert dotacion.profesionales == 3
    assert round(dotacion.espera_media_min, 1) == 4.2
    assert round(espera_media_min(2, dotacion.llegadas_por_hora, 15)) == 55


def test_la_recomendacion_muestra_sus_supuestos():
    """RF-6 paso 3: «publica el resultado con los supuestos a la vista»."""
    dotacion = recomendar_dotacion(545, TipoCentro.SAR, PARAMETROS["dotacion"])

    assert dotacion.supuestos == {
        "horas_funcionamiento_semana": 123,
        "factor_hora_punta": 1.6,
        "minutos_por_atencion": 15,
        "espera_objetivo_min": 30,
    }


def test_llegadas_en_hora_punta():
    assert llegadas_hora_punta(545, 123, 1.6) == pytest.approx(7.0894, abs=1e-4)


def test_erlang_c_casos_limite():
    assert erlang_c(3, 0) == 0.0  # sin llegadas nadie espera
    assert erlang_c(2, 2.5) == 1.0  # más carga que profesionales: siempre se espera
    assert 0 < erlang_c(3, 1.77) < 1


def test_sin_capacidad_suficiente_la_espera_es_infinita():
    assert espera_media_min(1, 10, 15) == math.inf


def test_dotacion_minima_es_la_menor_que_cumple_el_objetivo():
    llegadas = llegadas_hora_punta(545, 123, 1.6)

    assert dotacion_minima(llegadas, 15, 30) == 3
    assert espera_media_min(3, llegadas, 15) <= 30 < espera_media_min(2, llegadas, 15)


def test_sin_demanda_basta_un_profesional():
    assert dotacion_minima(0, 15, 30) == 1


@pytest.mark.parametrize(
    ("tipo", "horas"), [(TipoCentro.SAPU, 123), (TipoCentro.SAR, 123), (TipoCentro.HOSPITAL, 168)]
)
def test_horas_de_funcionamiento_por_tipo(tipo, horas):
    """Especificación: 123 h en SAPU y SAR, 168 h en hospitales (el notebook usaba 168 h para todos)."""
    assert horas_funcionamiento(tipo, PARAMETROS["dotacion"]) == horas


def test_sur_sin_horas_definidas_da_error_claro():
    """PASOS.md parte 5: las horas del SUR no están definidas; error claro si aparece un SUR."""
    with pytest.raises(ErrorDotacion, match="SUR"):
        recomendar_dotacion(100, TipoCentro.SUR, PARAMETROS["dotacion"])
