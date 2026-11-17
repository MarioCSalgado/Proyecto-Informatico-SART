"""TC-09 (parte RF-9) y TC-16 en la API · Administración de cuentas y centros (RF-9, RF-16, RNF-S-2, RNF-S-4).

Solo el administrador (que siempre entra con MFA) lista, crea, da de baja y asigna centros. La jefatura y el
subdirector reciben 403 y sin sesión 401: 0 accesos indebidos. La sesión del administrador se arma con el
token directamente (el MFA ya está probado en ``test_auth_mfa.py``).
"""

from datetime import timedelta

import pytest
from conftest import SECRETO_DE_PRUEBA
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from sart.api.tokens import NOMBRE_COOKIE, emitir_token
from sart.configuracion import RAIZ_REPOSITORIO
from sart.db.modelos import AceptacionFinalidad, Auditoria, Usuario
from sart.dominio.roles import Rol
from sart.parametros import cargar_parametros
from sart.tareas.carga import cargar_catalogo

ESTABLECIMIENTOS = RAIZ_REPOSITORIO / "datos" / "prueba" / "crudos" / "establecimientos.csv"
CLAVE = "una clave suficientemente larga"
RUTAS = [
    ("get", "/administracion/usuarios"),
    ("post", "/administracion/usuarios"),
    ("put", "/administracion/usuarios/1/centros"),
    ("delete", "/administracion/usuarios/1"),
]


@pytest.fixture
def catalogo(motor_memoria):
    with Session(motor_memoria) as sesion:
        cargar_catalogo(sesion, ESTABLECIMIENTOS)


def _como(cliente, usuario_id: int, rol: Rol):
    token = emitir_token(
        usuario_id=usuario_id, rol=rol, secreto=SECRETO_DE_PRUEBA, duracion=timedelta(hours=1)
    )
    cliente.cookies.set(NOMBRE_COOKIE, token)
    return cliente


@pytest.fixture
def admin(cliente, crear_cuenta, catalogo):
    return _como(cliente, crear_cuenta("admin@demo.sart", "administrador"), Rol.ADMINISTRADOR)


def _alta(**cambios) -> dict:
    datos = {
        "nombre": "Ana Pérez",
        "correo": "ana@demo.sart",
        "rol": "jefatura",
        "contrasena": CLAVE,
        "acepta_finalidad": True,
        "version_texto": cargar_parametros()["cuentas"]["version_texto_finalidad"],
    }
    return {**datos, **cambios}


# ---------------------------------------------------------------------------
# TC-09: 0 accesos indebidos
# ---------------------------------------------------------------------------
@pytest.mark.parametrize(("metodo", "ruta"), RUTAS)
def test_tc09_rf9_sin_sesion_401(cliente, metodo, ruta):
    assert cliente.request(metodo, ruta, json={}).status_code == 401


@pytest.mark.parametrize("rol", [Rol.JEFATURA, Rol.SUBDIRECTOR])
@pytest.mark.parametrize(("metodo", "ruta"), RUTAS)
def test_tc09_rf9_otro_rol_403(cliente, crear_cuenta, metodo, ruta, rol):
    _como(cliente, crear_cuenta(f"{rol.value}@demo.sart", rol.value), rol)

    assert cliente.request(metodo, ruta, json=_alta()).status_code == 403


# ---------------------------------------------------------------------------
# RF-16 por la API
# ---------------------------------------------------------------------------
def test_tc16_api_sin_aceptacion_no_crea_ni_guarda_nada(admin, motor_memoria):
    respuesta = admin.post("/administracion/usuarios", json=_alta(acepta_finalidad=False))

    assert respuesta.status_code == 422
    assert "finalidad" in respuesta.json()["detail"]
    with Session(motor_memoria) as sesion:
        assert sesion.scalar(select(func.count()).select_from(Usuario)) == 1  # solo el administrador
        assert sesion.scalar(select(Usuario).where(Usuario.correo == "ana@demo.sart")) is None


def test_tc16_api_version_antigua_no_crea(admin):
    assert admin.post("/administracion/usuarios", json=_alta(version_texto="1999-1")).status_code == 422


def test_rf16_alta_con_centros_y_auditoria_sin_datos_personales(admin, motor_memoria):
    respuesta = admin.post("/administracion/usuarios", json=_alta(centros=[100001]))

    assert respuesta.status_code == 201
    cuenta = respuesta.json()
    assert cuenta["correo"] == "ana@demo.sart"
    assert [c["codigo_deis"] for c in cuenta["centros"]] == [100001]
    assert "contrasena" not in cuenta and "hash_contrasena" not in cuenta
    with Session(motor_memoria) as sesion:
        registro = sesion.scalar(
            select(Auditoria).where(
                Auditoria.accion == "crear_cuenta", Auditoria.entidad_id == str(cuenta["id"])
            )
        )
        assert registro.autor_rol == "administrador"
        assert "ana" not in str(registro.valor_nuevo).lower()


def test_rf16_correo_repetido_409(admin):
    assert admin.post("/administracion/usuarios", json=_alta()).status_code == 201
    assert admin.post("/administracion/usuarios", json=_alta(correo="ANA@demo.sart")).status_code == 409


def test_rf9_lista_las_cuentas_con_sus_centros(admin):
    admin.post("/administracion/usuarios", json=_alta(centros=[100002, 100001]))

    cuentas = admin.get("/administracion/usuarios").json()

    assert [c["correo"] for c in cuentas] == ["admin@demo.sart", "ana@demo.sart"]
    assert [c["codigo_deis"] for c in cuentas[1]["centros"]] == [100001, 100002]
    assert cuentas[0]["mfa_activo"] is False


# ---------------------------------------------------------------------------
# RF-9: centros asignados
# ---------------------------------------------------------------------------
def test_rf9_reemplaza_los_centros_y_queda_en_la_auditoria(admin, motor_memoria):
    id_ana = admin.post("/administracion/usuarios", json=_alta(centros=[100001])).json()["id"]

    respuesta = admin.put(f"/administracion/usuarios/{id_ana}/centros", json={"centros": [100002, 100003]})

    assert respuesta.status_code == 200
    assert [c["codigo_deis"] for c in respuesta.json()["centros"]] == [100002, 100003]
    with Session(motor_memoria) as sesion:
        registro = sesion.scalar(select(Auditoria).where(Auditoria.accion == "asignar_centros"))
        assert registro.valor_anterior == [100001]
        assert registro.valor_nuevo == [100002, 100003]


def test_rf9_centro_inexistente_422_sin_cambios(admin):
    id_ana = admin.post("/administracion/usuarios", json=_alta(centros=[100001])).json()["id"]

    assert (
        admin.put(f"/administracion/usuarios/{id_ana}/centros", json={"centros": [999999]}).status_code == 422
    )
    assert admin.get("/administracion/usuarios").json()[1]["centros"][0]["codigo_deis"] == 100001


def test_rf9_cuenta_inexistente_404(admin):
    assert admin.put("/administracion/usuarios/999/centros", json={"centros": []}).status_code == 404
    assert admin.delete("/administracion/usuarios/999").status_code == 404


# ---------------------------------------------------------------------------
# RF-16 E2: baja
# ---------------------------------------------------------------------------
def test_rf16_e2_baja_borra_contacto_y_deja_auditoria_sin_datos_personales(admin, motor_memoria):
    id_ana = admin.post("/administracion/usuarios", json=_alta(centros=[100001])).json()["id"]

    assert admin.delete(f"/administracion/usuarios/{id_ana}").status_code == 204

    with Session(motor_memoria) as sesion:
        assert sesion.get(Usuario, id_ana) is None
        assert sesion.scalar(select(func.count()).select_from(AceptacionFinalidad)) == 1  # la del admin
        registro = sesion.scalar(select(Auditoria).where(Auditoria.accion == "baja_cuenta"))
        assert registro.entidad_id == str(id_ana)
        assert "ana" not in f"{registro.valor_anterior}{registro.valor_nuevo}".lower()


def test_rf16_e2_el_administrador_no_se_da_de_baja_a_si_mismo(admin):
    id_admin = admin.get("/administracion/usuarios").json()[0]["id"]

    assert admin.delete(f"/administracion/usuarios/{id_admin}").status_code == 409
