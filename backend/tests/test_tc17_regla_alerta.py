"""TC-17 · Regla de alerta con margen y cambio del parámetro k (RF-3, RB-3, RF-9).

Umbral 713, pronóstico 700 y límite superior 760: con k = 0,4 → ALERTA (715); con k = 0 → sin ALERTA.
desviación = (límite superior − pronóstico) / z, con z del nivel del intervalo (90 % → 1,645).
"""

import pytest

from sart.dominio.alerta_demanda import (
    clasificar_demanda,
    margen_de_seguridad,
    pronostico_con_margen,
    z_del_intervalo,
)
from sart.parametros import cargar_parametros

PARAMETROS = cargar_parametros()
NIVEL = PARAMETROS["modelo"]["nivel_intervalo"]


def test_z_del_intervalo_de_90():
    assert z_del_intervalo(NIVEL) == pytest.approx(1.645, abs=1e-3)


def test_tc17_con_k_04_el_margen_lleva_a_alerta():
    """Gherkin de RF-3 «Alerta por margen de seguridad»: el pronóstico con margen es 715."""
    assert round(pronostico_con_margen(700, 760, k=0.4, nivel_intervalo=NIVEL)) == 715
    assert (
        clasificar_demanda(700, 760, umbral_atencion=600, umbral_alerta=713, k=0.4, nivel_intervalo=NIVEL)
        == "alerta"
    )


def test_tc17_con_k_0_no_hay_alerta():
    assert margen_de_seguridad(700, 760, k=0, nivel_intervalo=NIVEL) == 0
    assert (
        clasificar_demanda(700, 760, umbral_atencion=600, umbral_alerta=713, k=0, nivel_intervalo=NIVEL)
        == "atencion"
    )


def test_k_de_los_parametros_es_04():
    """RF-9: k se ajusta desde la administración; el valor de partida es el de parametros.yaml."""
    assert PARAMETROS["regla_alerta"]["k_margen"] == 0.4


def test_gherkin_centro_en_alerta():
    """RF-3 «Centro en alerta»: pronóstico 760 sobre un umbral de 713."""
    assert (
        clasificar_demanda(760, 820, umbral_atencion=600, umbral_alerta=713, k=0.4, nivel_intervalo=NIVEL)
        == "alerta"
    )


@pytest.mark.parametrize(
    ("pronostico", "superior", "esperado"),
    [
        (500, 560, "normal"),  # bajo el p75
        (600, 620, "normal"),  # igual al p75: «supera» es estrictamente mayor
        (601, 640, "atencion"),  # sobre el p75; el margen no alcanza el p90
        (713, 713, "atencion"),  # igual al p90 y sin margen: no supera
    ],
)
def test_niveles_y_bordes(pronostico, superior, esperado):
    """RB-3: atención sin margen sobre el p75; el margen solo se aplica al p90 (pendientes #7)."""
    nivel = clasificar_demanda(
        pronostico, superior, umbral_atencion=600, umbral_alerta=713, k=0.4, nivel_intervalo=NIVEL
    )
    assert nivel == esperado


def test_limite_superior_menor_que_el_pronostico_es_un_error():
    with pytest.raises(ValueError, match="límite superior"):
        margen_de_seguridad(700, 650, k=0.4, nivel_intervalo=NIVEL)
