"""Inicio y cierre de sesión con JWT en cookie httpOnly (RNF-S-1).

Rutas que ya usa la web: POST /auth/sesion, GET /auth/yo, POST /auth/cerrar-sesion.
"""

from datetime import UTC, datetime, timedelta

from conftest import CLAVE_DE_PRUEBA, SECRETO_DE_PRUEBA
from sqlalchemy import delete
from sqlalchemy.orm import Session

from sart.api.tokens import NOMBRE_COOKIE, emitir_token
from sart.db.modelos import Usuario
from sart.dominio.roles import Rol


def _entrar(cliente, correo, clave=CLAVE_DE_PRUEBA):
    return cliente.post("/auth/sesion", json={"correo": correo, "contrasena": clave})


def test_inicio_correcto_devuelve_el_usuario_y_pone_cookie_httponly(cliente, crear_cuenta):
    id_usuario = crear_cuenta("jefatura@demo.sart", "jefatura", nombre="Jefatura Demo")

    respuesta = _entrar(cliente, "jefatura@demo.sart")

    assert respuesta.status_code == 200
    assert respuesta.json() == {"usuario": {"id": id_usuario, "nombre": "Jefatura Demo", "rol": "Jefatura"}}
    cookie = respuesta.headers["set-cookie"]
    assert cookie.startswith(f"{NOMBRE_COOKIE}=")
    assert "HttpOnly" in cookie
    assert "SameSite=lax" in cookie
    assert "Max-Age=28800" in cookie  # 8 h de parametros.yaml (sesion.duracion_horas)
    assert "token" not in respuesta.text.lower()  # el JWT solo viaja en la cookie


def test_el_correo_no_distingue_mayusculas(cliente, crear_cuenta):
    crear_cuenta("subdirector@demo.sart", "subdirector")

    assert _entrar(cliente, "  Subdirector@Demo.SART ").status_code == 200


def test_clave_incorrecta_y_correo_inexistente_dan_el_mismo_401(cliente, crear_cuenta):
    """No revela si el correo existe."""
    crear_cuenta("jefatura@demo.sart", "jefatura")

    clave_mala = _entrar(cliente, "jefatura@demo.sart", "otra clave cualquiera")
    sin_cuenta = _entrar(cliente, "nadie@demo.sart")

    assert clave_mala.status_code == sin_cuenta.status_code == 401
    assert clave_mala.json() == sin_cuenta.json()
    assert "set-cookie" not in clave_mala.headers


def test_administrador_sin_mfa_no_entra(cliente, crear_cuenta):
    """RNF-S-1: MFA obligatorio para administradores; mientras no exista, no se les abre sesión."""
    crear_cuenta("admin@demo.sart", "administrador")

    respuesta = _entrar(cliente, "admin@demo.sart")

    assert respuesta.status_code == 403
    assert "MFA" in respuesta.json()["detail"]
    assert "set-cookie" not in respuesta.headers


def test_administrador_con_clave_mala_recibe_401_no_403(cliente, crear_cuenta):
    """El aviso de MFA solo aparece con la clave correcta: no revela que la cuenta es de administrador."""
    crear_cuenta("admin@demo.sart", "administrador")

    assert _entrar(cliente, "admin@demo.sart", "clave equivocada larga").status_code == 401


def test_yo_devuelve_el_usuario_de_la_cookie(cliente, crear_cuenta):
    crear_cuenta("jefatura@demo.sart", "jefatura", nombre="Jefatura Demo")
    _entrar(cliente, "jefatura@demo.sart")

    respuesta = cliente.get("/auth/yo")

    assert respuesta.status_code == 200
    assert respuesta.json()["usuario"]["nombre"] == "Jefatura Demo"


def test_yo_sin_sesion_da_401(cliente):
    assert cliente.get("/auth/yo").status_code == 401


def test_token_alterado_da_401(cliente, crear_cuenta):
    crear_cuenta("jefatura@demo.sart", "jefatura")
    _entrar(cliente, "jefatura@demo.sart")
    token = cliente.cookies.get(NOMBRE_COOKIE)
    cliente.cookies.set(NOMBRE_COOKIE, token[:-2] + ("aa" if not token.endswith("aa") else "bb"))

    assert cliente.get("/auth/yo").status_code == 401


def test_token_vencido_da_401(cliente, crear_cuenta):
    id_usuario = crear_cuenta("jefatura@demo.sart", "jefatura")
    vencido = emitir_token(
        usuario_id=id_usuario,
        rol=Rol.JEFATURA,
        secreto=SECRETO_DE_PRUEBA,
        duracion=timedelta(hours=8),
        ahora=datetime.now(UTC) - timedelta(hours=9),
    )
    cliente.cookies.set(NOMBRE_COOKIE, vencido)

    assert cliente.get("/auth/yo").status_code == 401


def test_token_firmado_con_otro_secreto_da_401(cliente, crear_cuenta):
    id_usuario = crear_cuenta("jefatura@demo.sart", "jefatura")
    ajeno = emitir_token(
        usuario_id=id_usuario,
        rol=Rol.JEFATURA,
        secreto="otro-secreto-de-al-menos-32-caracteres-xx",
        duracion=timedelta(hours=8),
    )
    cliente.cookies.set(NOMBRE_COOKIE, ajeno)

    assert cliente.get("/auth/yo").status_code == 401


def test_cuenta_borrada_pierde_la_sesion(cliente, crear_cuenta, motor_memoria):
    """RF-16 E2: tras la baja, la cookie que quedó en el navegador ya no sirve."""
    crear_cuenta("jefatura@demo.sart", "jefatura")
    _entrar(cliente, "jefatura@demo.sart")
    with Session(motor_memoria) as sesion:
        sesion.execute(delete(Usuario))
        sesion.commit()

    assert cliente.get("/auth/yo").status_code == 401


def test_cerrar_sesion_borra_la_cookie(cliente, crear_cuenta):
    crear_cuenta("jefatura@demo.sart", "jefatura")
    _entrar(cliente, "jefatura@demo.sart")

    respuesta = cliente.post("/auth/cerrar-sesion")

    assert respuesta.status_code == 204
    assert NOMBRE_COOKIE not in cliente.cookies
    assert cliente.get("/auth/yo").status_code == 401


def test_cookie_secure_por_defecto(cliente, crear_cuenta, monkeypatch):
    """RNF-S-3: en producción la cookie solo viaja por HTTPS; COOKIE_SEGURA=false es solo para desarrollo."""
    monkeypatch.delenv("COOKIE_SEGURA")
    crear_cuenta("jefatura@demo.sart", "jefatura")

    assert "Secure" in _entrar(cliente, "jefatura@demo.sart").headers["set-cookie"]


def test_sin_jwt_secret_valido_da_503(cliente, crear_cuenta, monkeypatch):
    """Un secreto vacío, corto o el de ejemplo no se acepta para firmar sesiones."""
    crear_cuenta("jefatura@demo.sart", "jefatura")
    for secreto in (None, "cambiar-esto", "corto"):
        if secreto is None:
            monkeypatch.delenv("JWT_SECRET")
        else:
            monkeypatch.setenv("JWT_SECRET", secreto)

        respuesta = _entrar(cliente, "jefatura@demo.sart")

        assert respuesta.status_code == 503
        assert "JWT_SECRET" in respuesta.json()["detail"]
