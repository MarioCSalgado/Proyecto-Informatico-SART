"""MFA con TOTP (RFC 6238) para administradores (RNF-S-1). Lógica pura, con la hora fija."""

from datetime import UTC, datetime, timedelta

import pyotp

from sart.dominio.mfa import (
    PASO_SEGUNDOS,
    bloqueado,
    nuevo_secreto,
    secreto_legible,
    tras_fallo,
    uri_aprovisionamiento,
    verificar_codigo,
)

SECRETO = "JBSWY3DPEHPK3PXPJBSWY3DPEHPK3PXP"
AHORA = datetime(2026, 11, 13, 12, 0, 15, tzinfo=UTC)
PASO_AHORA = int(AHORA.timestamp()) // PASO_SEGUNDOS


def _codigo(momento: datetime) -> str:
    return pyotp.TOTP(SECRETO).at(momento)


def test_secreto_nuevo_es_base32_de_160_bits_y_distinto_cada_vez():
    secreto = nuevo_secreto()

    assert len(secreto) == 32
    assert set(secreto) <= set("ABCDEFGHIJKLMNOPQRSTUVWXYZ234567")
    assert secreto != nuevo_secreto()


def test_secreto_legible_en_grupos_de_cuatro():
    assert secreto_legible("ABCDEFGHIJKL") == "ABCD EFGH IJKL"


def test_uri_para_la_aplicacion_de_autenticacion():
    uri = uri_aprovisionamiento(SECRETO, "admin@demo.sart", "SART")

    assert uri.startswith("otpauth://totp/SART:admin%40demo.sart?")
    assert f"secret={SECRETO}" in uri
    assert "issuer=SART" in uri


def test_codigo_del_paso_actual_es_valido_y_devuelve_el_paso():
    assert (
        verificar_codigo(SECRETO, _codigo(AHORA), ahora=AHORA, ultimo_paso=None, tolerancia=1) == PASO_AHORA
    )


def test_acepta_espacios_alrededor_y_en_medio():
    codigo = _codigo(AHORA)
    con_espacios = f" {codigo[:3]} {codigo[3:]} "

    assert verificar_codigo(SECRETO, con_espacios, ahora=AHORA, ultimo_paso=None, tolerancia=1) == PASO_AHORA


def test_tolerancia_de_un_paso_por_desfase_de_reloj():
    anterior = _codigo(AHORA - timedelta(seconds=PASO_SEGUNDOS))
    dos_atras = _codigo(AHORA - timedelta(seconds=2 * PASO_SEGUNDOS))

    assert verificar_codigo(SECRETO, anterior, ahora=AHORA, ultimo_paso=None, tolerancia=1) == PASO_AHORA - 1
    assert verificar_codigo(SECRETO, dos_atras, ahora=AHORA, ultimo_paso=None, tolerancia=1) is None
    assert verificar_codigo(SECRETO, anterior, ahora=AHORA, ultimo_paso=None, tolerancia=0) is None


def test_un_codigo_ya_usado_no_sirve_de_nuevo():
    """Sin esto, quien vea el código por encima del hombro puede reusarlo dentro de los 30 s."""
    codigo = _codigo(AHORA)

    assert verificar_codigo(SECRETO, codigo, ahora=AHORA, ultimo_paso=PASO_AHORA, tolerancia=1) is None
    anterior = _codigo(AHORA - timedelta(seconds=PASO_SEGUNDOS))
    assert verificar_codigo(SECRETO, anterior, ahora=AHORA, ultimo_paso=PASO_AHORA, tolerancia=1) is None


def test_codigos_mal_formados_no_validan():
    for codigo in ("", "12345", "1234567", "abcdef", None):
        assert verificar_codigo(SECRETO, codigo, ahora=AHORA, ultimo_paso=None, tolerancia=1) is None


def test_fallos_hasta_el_maximo_bloquean_y_reinician_el_conteo():
    intentos, hasta = 0, None
    for _ in range(4):
        intentos, hasta = tras_fallo(intentos, maximo=5, minutos=15, ahora=AHORA)
        assert hasta is None
    assert intentos == 4

    intentos, hasta = tras_fallo(intentos, maximo=5, minutos=15, ahora=AHORA)

    assert intentos == 0
    assert hasta == AHORA + timedelta(minutes=15)


def test_bloqueado_mientras_no_pase_la_hora():
    hasta = AHORA + timedelta(minutes=15)

    assert bloqueado(hasta, AHORA) is True
    assert bloqueado(hasta, hasta) is False
    assert bloqueado(None, AHORA) is False


def test_bloqueado_acepta_fecha_sin_zona_como_utc():
    """SQLite devuelve las fechas sin zona horaria; PostgreSQL, con zona."""
    assert bloqueado((AHORA + timedelta(minutes=1)).replace(tzinfo=None), AHORA) is True
