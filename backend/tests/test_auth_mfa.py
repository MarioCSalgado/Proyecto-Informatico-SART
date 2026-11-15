"""Inicio de sesión de administradores con MFA TOTP (RNF-S-1).

1. Correo y clave correctos, sin código → 200 con ``mfa_requerido`` y sin cookie.
2. Con el código de la aplicación → 200 con el usuario y la cookie de sesión.
"""

from datetime import UTC, datetime, timedelta

import pyotp
import pytest
from conftest import CLAVE_DE_PRUEBA
from sqlalchemy.orm import Session

from sart.api.tokens import NOMBRE_COOKIE
from sart.db.mfa import confirmar_activacion, iniciar_activacion
from sart.db.modelos import Usuario

ADMIN = "admin@demo.sart"


@pytest.fixture
def secreto_admin(crear_cuenta, motor_memoria):
    """Administrador con MFA ya activado; devuelve su secreto TOTP."""
    crear_cuenta(ADMIN, "administrador", nombre="Administrador Demo")
    with Session(motor_memoria) as sesion:
        secreto, _ = iniciar_activacion(sesion, ADMIN, emisor="SART")
        # se confirma con el código de hace 30 s para que el código actual quede libre para las pruebas
        hace_un_paso = datetime.now(UTC) - timedelta(seconds=30)
        confirmar_activacion(
            sesion, ADMIN, pyotp.TOTP(secreto).at(hace_un_paso), ahora=hace_un_paso, tolerancia=0
        )
    return secreto


def _entrar(cliente, codigo=None, clave=CLAVE_DE_PRUEBA):
    datos = {"correo": ADMIN, "contrasena": clave}
    if codigo is not None:
        datos["codigo"] = codigo
    return cliente.post("/auth/sesion", json=datos)


def _codigo(secreto):
    return pyotp.TOTP(secreto).now()


def _usuario(motor) -> Usuario:
    with Session(motor) as sesion:
        usuario = sesion.query(Usuario).filter_by(correo=ADMIN).one()
        sesion.expunge(usuario)
        return usuario


def test_sin_mfa_activado_el_administrador_no_entra(cliente, crear_cuenta):
    crear_cuenta(ADMIN, "administrador")

    respuesta = _entrar(cliente, codigo="123456")

    assert respuesta.status_code == 403
    assert "MFA" in respuesta.json()["detail"]
    assert "set-cookie" not in respuesta.headers


def test_activacion_sin_confirmar_tampoco_basta(cliente, crear_cuenta, motor_memoria):
    crear_cuenta(ADMIN, "administrador")
    with Session(motor_memoria) as sesion:
        secreto, _ = iniciar_activacion(sesion, ADMIN, emisor="SART")

    assert _entrar(cliente, codigo=_codigo(secreto)).status_code == 403


def test_clave_correcta_sin_codigo_pide_el_codigo_sin_abrir_sesion(cliente, secreto_admin):
    respuesta = _entrar(cliente)

    assert respuesta.status_code == 200
    assert respuesta.json() == {"mfa_requerido": True}
    assert "set-cookie" not in respuesta.headers


def test_clave_incorrecta_no_revela_que_pide_codigo(cliente, secreto_admin):
    assert _entrar(cliente, clave="otra clave cualquiera").status_code == 401


def test_con_el_codigo_correcto_entra(cliente, secreto_admin):
    respuesta = _entrar(cliente, codigo=_codigo(secreto_admin))

    assert respuesta.status_code == 200
    assert respuesta.json()["usuario"]["rol"] == "Administrador"
    assert NOMBRE_COOKIE in cliente.cookies
    assert cliente.get("/auth/yo").json()["usuario"]["nombre"] == "Administrador Demo"


def test_el_mismo_codigo_no_sirve_dos_veces(cliente, secreto_admin):
    codigo = _codigo(secreto_admin)
    assert _entrar(cliente, codigo=codigo).status_code == 200
    cliente.cookies.clear()

    respuesta = _entrar(cliente, codigo=codigo)

    assert respuesta.status_code == 401
    assert "código" in respuesta.json()["detail"].lower()


def test_codigo_incorrecto_da_401(cliente, secreto_admin):
    respuesta = _entrar(cliente, codigo="000000" if _codigo(secreto_admin) != "000000" else "111111")

    assert respuesta.status_code == 401
    assert "set-cookie" not in respuesta.headers


def test_cinco_codigos_malos_bloquean_aunque_despues_venga_el_bueno(cliente, secreto_admin, motor_memoria):
    """parametros.yaml: mfa.intentos_maximos = 5 y mfa.bloqueo_minutos = 15."""
    malo = "000000" if _codigo(secreto_admin) != "000000" else "111111"
    for _ in range(5):
        assert _entrar(cliente, codigo=malo).status_code == 401

    respuesta = _entrar(cliente, codigo=_codigo(secreto_admin))

    assert respuesta.status_code == 429
    assert "15 min" in respuesta.json()["detail"]
    assert _usuario(motor_memoria).mfa_bloqueado_hasta is not None


def test_pasado_el_bloqueo_vuelve_a_entrar(cliente, secreto_admin, motor_memoria):
    with Session(motor_memoria) as sesion:
        usuario = sesion.query(Usuario).filter_by(correo=ADMIN).one()
        usuario.mfa_bloqueado_hasta = datetime.now(UTC) - timedelta(minutes=1)
        sesion.commit()

    assert _entrar(cliente, codigo=_codigo(secreto_admin)).status_code == 200


def test_un_acierto_reinicia_el_conteo_de_fallos(cliente, secreto_admin, motor_memoria):
    _entrar(cliente, codigo="000000" if _codigo(secreto_admin) != "000000" else "111111")
    assert _usuario(motor_memoria).mfa_intentos_fallidos == 1

    assert _entrar(cliente, codigo=_codigo(secreto_admin)).status_code == 200
    assert _usuario(motor_memoria).mfa_intentos_fallidos == 0


def test_jefatura_no_necesita_codigo(cliente, crear_cuenta):
    """RNF-S-1: MFA solo para administradores."""
    crear_cuenta("jefatura@demo.sart", "jefatura")

    respuesta = cliente.post(
        "/auth/sesion", json={"correo": "jefatura@demo.sart", "contrasena": CLAVE_DE_PRUEBA}
    )

    assert respuesta.status_code == 200
    assert "usuario" in respuesta.json()


# ---------------------------------------------------------------------------
# Código fijo de desarrollo (pendientes #49): solo con MFA_CODIGO_DESARROLLO y COOKIE_SEGURA=false
# ---------------------------------------------------------------------------
CODIGO_FIJO = "135790"


def test_codigo_fijo_de_desarrollo_entra_en_local(cliente, secreto_admin, monkeypatch):
    monkeypatch.setenv("MFA_CODIGO_DESARROLLO", CODIGO_FIJO)  # «cliente» ya pone COOKIE_SEGURA=false

    primero = _entrar(cliente, codigo=CODIGO_FIJO)
    segundo = _entrar(cliente, codigo=CODIGO_FIJO)  # a diferencia del TOTP, se puede repetir

    assert primero.status_code == 200 and NOMBRE_COOKIE in primero.headers["set-cookie"]
    assert segundo.status_code == 200


def test_codigo_fijo_no_vale_con_cookie_segura(cliente, secreto_admin, monkeypatch):
    """En producción (COOKIE_SEGURA=true, RNF-S-3) el código fijo se ignora: solo vale el TOTP."""
    monkeypatch.setenv("MFA_CODIGO_DESARROLLO", CODIGO_FIJO)
    monkeypatch.setenv("COOKIE_SEGURA", "true")

    assert _entrar(cliente, codigo=CODIGO_FIJO).status_code == 401
    assert _entrar(cliente, codigo=_codigo(secreto_admin)).status_code == 200


def test_sin_la_variable_no_hay_codigo_fijo(cliente, secreto_admin, monkeypatch):
    monkeypatch.delenv("MFA_CODIGO_DESARROLLO", raising=False)

    assert _entrar(cliente, codigo=CODIGO_FIJO).status_code == 401


@pytest.mark.parametrize("mal_formado", ["", "123", "abcdef", "1234567"])
def test_codigo_fijo_mal_formado_se_ignora(cliente, secreto_admin, monkeypatch, mal_formado):
    monkeypatch.setenv("MFA_CODIGO_DESARROLLO", mal_formado)

    assert _entrar(cliente, codigo=mal_formado or "000000").status_code == 401


def test_el_codigo_fijo_no_salta_el_bloqueo(cliente, secreto_admin, monkeypatch):
    monkeypatch.setenv("MFA_CODIGO_DESARROLLO", CODIGO_FIJO)
    for _ in range(5):
        _entrar(cliente, codigo="000000")

    assert _entrar(cliente, codigo=CODIGO_FIJO).status_code == 429


def test_salud_avisa_si_el_codigo_fijo_esta_activo(cliente, monkeypatch):
    monkeypatch.setenv("MFA_CODIGO_DESARROLLO", CODIGO_FIJO)

    assert "código fijo" in cliente.get("/salud").json()["componentes"]["mfa"]
