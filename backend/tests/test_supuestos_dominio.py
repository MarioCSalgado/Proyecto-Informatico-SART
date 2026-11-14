"""Supuestos ajustables por el administrador (RF-9, RNF-M-4, opción a). Lógica pura."""

import math

import pytest

from sart.dominio.supuestos import ErrorAjuste, aplicar_ajustes, validar_ajuste, valor_en
from sart.parametros import cargar_parametros

BASE = cargar_parametros()
EDITABLES = BASE["administracion"]["parametros_editables"]


def test_valor_en_ruta_con_puntos():
    assert valor_en(BASE, "regla_alerta.k_margen") == 0.4
    assert valor_en(BASE, "dotacion.horas_funcionamiento_semana.SAPU") == 123


def test_aplicar_ajustes_no_modifica_el_original():
    vigentes = aplicar_ajustes(
        BASE, {"regla_alerta.k_margen": 0.5, "dotacion.horas_funcionamiento_semana.SUR": 168}
    )

    assert vigentes["regla_alerta"]["k_margen"] == 0.5
    assert vigentes["dotacion"]["horas_funcionamiento_semana"]["SUR"] == 168
    assert vigentes["dotacion"]["horas_funcionamiento_semana"]["SAPU"] == 123
    assert BASE["regla_alerta"]["k_margen"] == 0.4


def test_validar_acepta_numero_en_clave_editable():
    assert validar_ajuste(BASE, "regla_alerta.k_margen", 0.3, EDITABLES) == 0.3
    assert validar_ajuste(BASE, "dotacion.minutos_por_atencion", 12, EDITABLES) == 12


def test_las_horas_del_sur_vienen_vacias_y_se_pueden_completar():
    """El informe no define las horas del SUR (null en el YAML): el administrador puede fijarlas."""
    assert validar_ajuste(BASE, "dotacion.horas_funcionamiento_semana.SUR", 168, EDITABLES) == 168


def test_clave_no_editable_se_rechaza():
    with pytest.raises(ErrorAjuste, match="no se puede ajustar"):
        validar_ajuste(BASE, "horarios.ingesta", "04:00", EDITABLES)


@pytest.mark.parametrize("valor", ["0,5", None, True, math.nan, math.inf, -1])
def test_tipo_o_valor_invalido_se_rechaza(valor):
    with pytest.raises(ErrorAjuste):
        validar_ajuste(BASE, "regla_alerta.k_margen", valor, EDITABLES)


def test_editable_que_no_existe_en_el_yaml_se_rechaza():
    with pytest.raises(ErrorAjuste, match="no existe"):
        validar_ajuste(BASE, "regla_alerta.inventada", 1, [*EDITABLES, "regla_alerta.inventada"])
