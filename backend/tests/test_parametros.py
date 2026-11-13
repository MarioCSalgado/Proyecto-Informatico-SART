"""Lector de config/parametros.yaml (RNF-M-4)."""

import pytest

from sart.parametros import ErrorParametros, cargar_parametros


def test_lee_el_archivo_real_del_repositorio():
    parametros = cargar_parametros()

    assert parametros["regla_alerta"]["k_margen"] == 0.4  # RF-3, TC-17
    assert parametros["umbrales"]["cuantil_alerta"] == 0.90  # RB-3


def test_respeta_la_variable_de_entorno(tmp_path, monkeypatch):
    otro = tmp_path / "otro.yaml"
    otro.write_text("zona_horaria: UTC\n", encoding="utf-8")
    monkeypatch.setenv("SART_PARAMETROS", str(otro))

    with pytest.raises(ErrorParametros, match="Faltan secciones"):
        cargar_parametros()


def test_archivo_inexistente_da_error_claro(tmp_path):
    with pytest.raises(ErrorParametros, match="No existe"):
        cargar_parametros(tmp_path / "no_esta.yaml")
