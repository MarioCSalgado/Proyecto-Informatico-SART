"""Validación del alta de cuentas (RF-16, §5.1, RNF-S-1, RNF-S-2). Lógica pura, sin base de datos."""

from datetime import UTC, datetime

import pytest

from sart.dominio.cuentas import Aceptacion, ErrorAltaCuenta, SinAceptacion, validar_alta
from sart.dominio.roles import Rol

VIGENTE = "2026-1"
ACEPTA = Aceptacion(version_texto=VIGENTE, aceptada_en=datetime(2026, 11, 13, 12, tzinfo=UTC))


def _validar(**cambios):
    datos = {
        "nombre": "Jefatura de prueba",
        "correo": "jefatura@demo.sart",
        "rol": "jefatura",
        "contrasena": "una clave suficientemente larga",
        "aceptacion": ACEPTA,
        "version_vigente": VIGENTE,
        "largo_minimo": 12,
    }
    datos.update(cambios)
    return validar_alta(**datos)


def test_alta_valida_normaliza_correo_y_nombre():
    alta = _validar(correo="  Jefatura@Demo.SART ", nombre="  Jefatura de prueba  ")

    assert alta.correo == "jefatura@demo.sart"
    assert alta.nombre == "Jefatura de prueba"
    assert alta.rol is Rol.JEFATURA
    assert alta.aceptacion == ACEPTA


def test_sin_aceptacion_se_rechaza_antes_que_cualquier_otro_error():
    """RF-16 E1: aunque los demás datos también estén mal, lo primero es la aceptación."""
    with pytest.raises(SinAceptacion):
        _validar(aceptacion=None, correo="malo", contrasena="corta")


def test_aceptacion_de_otra_version_del_texto_se_rechaza():
    """RF-16: la aceptación queda registrada con la versión del texto; debe ser la vigente."""
    antigua = Aceptacion(version_texto="2025-1", aceptada_en=ACEPTA.aceptada_en)

    with pytest.raises(SinAceptacion, match="2026-1"):
        _validar(aceptacion=antigua)


@pytest.mark.parametrize("correo", ["", "sin-arroba", "dos@@demo.sart", "a@b", "con espacio@demo.sart"])
def test_correo_invalido(correo):
    """§5.1: correo válido."""
    with pytest.raises(ErrorAltaCuenta, match="correo"):
        _validar(correo=correo)


def test_rol_fuera_de_rnf_s2():
    with pytest.raises(ErrorAltaCuenta, match="rol"):
        _validar(rol="paciente")


def test_nombre_vacio():
    with pytest.raises(ErrorAltaCuenta, match="nombre"):
        _validar(nombre="   ")


def test_contrasena_mas_corta_que_el_minimo_de_los_parametros():
    """RNF-S-1, RNF-M-4: el largo mínimo viene de parametros.yaml."""
    with pytest.raises(ErrorAltaCuenta, match="12"):
        _validar(contrasena="corta")
    assert _validar(contrasena="corta", largo_minimo=5).rol is Rol.JEFATURA
