"""TC-05 · Clasificación del MP2,5 con los bordes de RB-1 (RF-4).

Entrada: 45, 50, 51, 80, 110 y 170 µg/m³ → Normal, Normal, sobre la norma, Alerta, Preemergencia y Emergencia.
Los límites vienen de config/parametros.yaml (mp25_niveles, RNF-M-4).
"""

import pytest

from sart.dominio.mp25 import clasificar_mp25
from sart.parametros import cargar_parametros

UMBRALES = cargar_parametros()["mp25_niveles"]


@pytest.mark.parametrize(
    ("valor", "esperado"),
    [
        (45, "normal"),
        (50, "normal"),
        (51, "sobre_la_norma"),
        (80, "alerta"),
        (110, "preemergencia"),
        (170, "emergencia"),
    ],
)
def test_tc05_bordes_de_rb1(valor, esperado):
    assert clasificar_mp25(valor, UMBRALES).clave == esperado


@pytest.mark.parametrize(
    ("valor", "esperado"),
    [
        (0, "normal"),
        (79.9, "sobre_la_norma"),
        (109.9, "alerta"),
        (169.9, "preemergencia"),
        (400, "emergencia"),
    ],
)
def test_valores_dentro_de_cada_tramo(valor, esperado):
    """RB-1 dice «más de 50 y menos de 80»: los límites se comparan tal cual (pendientes #8: redondeo)."""
    assert clasificar_mp25(valor, UMBRALES).clave == esperado


def test_el_nivel_trae_su_nombre_para_mostrar():
    assert clasificar_mp25(51, UMBRALES).nombre == "Sobre la norma"


def test_valor_negativo_es_un_error():
    with pytest.raises(ValueError, match="negativ"):
        clasificar_mp25(-1, UMBRALES)
