"""Base de TC-09 · Acceso por rol (RNF-S-2): 0 accesos indebidos.

TC-09 completo necesita las rutas de RF-7 y RF-9; aquí se prueba la dependencia ``requiere_rol`` que las
protegerá, con una ruta de prueba.
"""

from typing import Annotated

import pytest
from conftest import CLAVE_DE_PRUEBA
from fastapi import Depends

from sart.api.app import app
from sart.api.dependencias import requiere_rol
from sart.db.modelos import Usuario
from sart.dominio.roles import Rol

RUTA = "/_prueba/solo-subdirector"


@pytest.fixture(autouse=True)
def ruta_protegida():
    @app.get(RUTA)
    def solo_subdirector(usuario: Annotated[Usuario, Depends(requiere_rol(Rol.SUBDIRECTOR))]):
        return {"ok": usuario.correo}

    yield
    app.router.routes[:] = [r for r in app.router.routes if getattr(r, "path", None) != RUTA]


def _entrar(cliente, correo):
    assert (
        cliente.post("/auth/sesion", json={"correo": correo, "contrasena": CLAVE_DE_PRUEBA}).status_code
        == 200
    )


def test_sin_sesion_da_401(cliente):
    assert cliente.get(RUTA).status_code == 401


def test_rol_no_autorizado_da_403(cliente, crear_cuenta):
    crear_cuenta("jefatura@demo.sart", "jefatura")
    _entrar(cliente, "jefatura@demo.sart")

    assert cliente.get(RUTA).status_code == 403


def test_rol_autorizado_entra(cliente, crear_cuenta):
    crear_cuenta("subdirector@demo.sart", "subdirector")
    _entrar(cliente, "subdirector@demo.sart")

    respuesta = cliente.get(RUTA)

    assert respuesta.status_code == 200
    assert respuesta.json() == {"ok": "subdirector@demo.sart"}
