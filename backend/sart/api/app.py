"""Aplicación FastAPI de SART.

Expone ``GET /salud``, que comprueba de punta a punta que la API lee los parámetros (RNF-M-4) y llega a
PostgreSQL, y las rutas de sesión de ``sart.api.auth`` (RNF-S-1). Las rutas de RF-7, RF-9, RF-15 y RF-16 se
agregan en las actividades 8 y 10, protegidas con ``requiere_rol`` (RNF-S-2).
"""

from __future__ import annotations

from fastapi import FastAPI
from sqlalchemy import create_engine, text

from sart import __version__
from sart.api import auth, referencias
from sart.configuracion import obtener_configuracion
from sart.parametros import ErrorParametros, cargar_parametros

app = FastAPI(title="SART", version=__version__)
app.include_router(auth.router)
app.include_router(referencias.router)


def _revisar_parametros() -> str:
    try:
        cargar_parametros()
    except ErrorParametros as error:
        return f"error: {error}"
    return "ok"


def _revisar_base_de_datos() -> str:
    url = obtener_configuracion().database_url
    if not url:
        return "sin configurar (falta DATABASE_URL)"
    try:
        motor = create_engine(url, pool_pre_ping=True, connect_args={"connect_timeout": 3})
        with motor.connect() as conexion:
            conexion.execute(text("SELECT 1"))
        motor.dispose()
    except Exception as error:  # /salud informa cualquier falla, no la propaga
        return f"sin conexión ({type(error).__name__})"
    return "ok"


@app.get("/salud")
def salud() -> dict:
    """Estado de la API y de sus dependencias. Responde 200 aunque algo falle, con estado «degradado»."""
    componentes = {
        "parametros": _revisar_parametros(),
        "base_de_datos": _revisar_base_de_datos(),
    }
    estado = "ok" if all(v == "ok" for v in componentes.values()) else "degradado"
    return {"estado": estado, "version": __version__, "componentes": componentes}
