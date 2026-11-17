"""Fixtures comunes de las pruebas del backend."""

import os
import uuid
from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from sart import configuracion
from sart.api.app import app
from sart.api.dependencias import obtener_sesion_db
from sart.configuracion import RAIZ_REPOSITORIO, Configuracion
from sart.db.cuentas import dar_de_alta
from sart.db.modelos import Base
from sart.dominio.cuentas import Aceptacion
from sart.parametros import cargar_parametros

SECRETO_DE_PRUEBA = "secreto-de-prueba-solo-para-pytest-0123456789"
CLAVE_DE_PRUEBA = "clave de prueba suficientemente larga"


@pytest.fixture(autouse=True)
def sin_env_del_desarrollador(tmp_path, monkeypatch):
    """Aísla las pruebas del ``.env`` real del repositorio (RNF-P-1).

    Cada prueba ve un ``.env`` inexistente; la que necesite uno lo escribe y apunta ``ARCHIVO_ENV`` a él.
    """
    monkeypatch.setattr(configuracion, "ARCHIVO_ENV", tmp_path / "no_existe.env")


@pytest.fixture
def motor_memoria():
    """Base SQLite en memoria compartida por todas las conexiones de la prueba."""
    motor = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(motor)
    yield motor
    motor.dispose()


@pytest.fixture
def cliente(motor_memoria, monkeypatch):
    """Cliente de la API con base en memoria, JWT_SECRET de prueba y cookie sin Secure (usa http)."""
    monkeypatch.setenv("JWT_SECRET", SECRETO_DE_PRUEBA)
    monkeypatch.setenv("COOKIE_SEGURA", "false")

    def sesion_de_prueba():
        with Session(motor_memoria) as sesion:
            yield sesion

    app.dependency_overrides[obtener_sesion_db] = sesion_de_prueba
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.pop(obtener_sesion_db, None)


@pytest.fixture
def crear_cuenta(motor_memoria):
    """Crea una cuenta en la base en memoria con la aceptación vigente (RF-16) y devuelve su id."""
    version = cargar_parametros()["cuentas"]["version_texto_finalidad"]

    def _crear(correo: str, rol: str, nombre: str = "Cuenta de prueba", clave: str = CLAVE_DE_PRUEBA) -> int:
        with Session(motor_memoria) as sesion:
            usuario = dar_de_alta(
                sesion,
                nombre=nombre,
                correo=correo,
                rol=rol,
                contrasena=clave,
                aceptacion=Aceptacion(version, datetime.now(UTC)),
            )
            return usuario.id

    return _crear


def url_postgres() -> str | None:
    """DATABASE_URL del entorno o del .env real (el fixture de arriba aísla el .env; aquí se lee a mano)."""
    return os.environ.get("DATABASE_URL") or Configuracion(_env_file=RAIZ_REPOSITORIO / ".env").database_url


@pytest.fixture
def crear_base_temporal():
    """Fábrica de bases PostgreSQL vacías para las pruebas de integración; se borran al terminar.
    Si no hay PostgreSQL disponible, la prueba se salta (por ejemplo, en CI sin servicio de base)."""
    url = url_postgres()
    if not url:
        pytest.skip("sin DATABASE_URL: no hay PostgreSQL para esta prueba de integración")
    administrador = create_engine(
        make_url(url).set(database="postgres"),
        isolation_level="AUTOCOMMIT",
        connect_args={"connect_timeout": 5},  # sin límite, una base inalcanzable cuelga la prueba
    )
    creadas: list[str] = []

    def crear() -> str:
        nombre = f"sart_prueba_{uuid.uuid4().hex[:8]}"
        try:
            with administrador.connect() as conexion:
                conexion.execute(text(f'CREATE DATABASE "{nombre}"'))
        except Exception as error:  # base apagada o sin permisos: se salta, no falla
            pytest.skip(f"PostgreSQL no disponible ({type(error).__name__})")
        creadas.append(nombre)
        return make_url(url).set(database=nombre).render_as_string(hide_password=False)

    try:
        yield crear
    finally:
        if creadas:  # si la prueba se saltó sin crear nada, no conectarse: con la base apagada fallaría
            with administrador.connect() as conexion:
                for nombre in creadas:
                    conexion.execute(text(f'DROP DATABASE IF EXISTS "{nombre}" WITH (FORCE)'))
        administrador.dispose()


DATOS_PRUEBA = RAIZ_REPOSITORIO / "datos" / "prueba" / "crudos"


@pytest.fixture(scope="session")
def archivo_base_prueba(tmp_path_factory):
    """SQLite con todo ``datos/prueba`` cargado (catálogo, consultas, SINCA y clima). Se carga una sola vez
    por sesión de pytest porque tarda ~35 s; las pruebas que escriben usan ``base_prueba`` (una copia)."""
    from sart.tareas.carga import cargar_catalogo, cargar_clima, cargar_consultas, cargar_sinca

    ruta = tmp_path_factory.mktemp("base_prueba") / "sart.db"
    motor = create_engine(f"sqlite:///{ruta.as_posix()}")
    Base.metadata.create_all(motor)
    with Session(motor) as sesion:
        cargar_catalogo(sesion, DATOS_PRUEBA / "establecimientos.csv")
        cargar_consultas(sesion, DATOS_PRUEBA / "at_urg_respiratorio_semanal.parquet")
        cargar_sinca(sesion, DATOS_PRUEBA / "sinca")
        cargar_clima(sesion, DATOS_PRUEBA / "clima_openmeteo.csv")
    motor.dispose()
    return ruta


@pytest.fixture
def base_prueba(archivo_base_prueba, tmp_path):
    """Motor sobre una copia de la base con ``datos/prueba``: cada prueba escribe sin afectar a otras."""
    import shutil

    copia = tmp_path / "sart.db"
    shutil.copyfile(archivo_base_prueba, copia)
    motor = create_engine(f"sqlite:///{copia.as_posix()}")
    yield motor
    motor.dispose()


@pytest.fixture(scope="session")
def archivos_deis_reales():
    """Rutas opcionales de DEIS: solo catálogo y consultas, sin insumos ambientales."""
    from pathlib import Path

    valor = os.environ.get("SART_DATOS_REALES")
    if not valor:
        pytest.skip("sin SART_DATOS_REALES: validación real opcional de DEIS")
    crudos = Path(valor) / "crudos"
    registro = crudos / "establecimientos.csv"
    if not registro.is_file():
        registro = crudos / "establecimientos_20260818.csv"
    consultas = crudos / "at_urg_respiratorio_semanal.parquet"
    faltantes = [str(ruta) for ruta in (registro, consultas) if not ruta.is_file()]
    if faltantes:
        pytest.fail("Archivos DEIS faltantes: " + ", ".join(faltantes))
    return registro, consultas


@pytest.fixture(scope="session")
def archivo_base_deis_real(tmp_path_factory, archivos_deis_reales):
    """SQLite temporal con establecimientos y urgencias reales; no usa la base local."""
    from sart.tareas.carga import cargar_catalogo, cargar_consultas

    registro, consultas = archivos_deis_reales
    ruta = tmp_path_factory.mktemp("base_deis_real") / "sart.db"
    motor = create_engine(f"sqlite:///{ruta.as_posix()}")
    try:
        Base.metadata.create_all(motor)
        with Session(motor) as sesion:
            cargar_catalogo(sesion, registro)
            cargar_consultas(sesion, consultas)
    finally:
        motor.dispose()
    return ruta


@pytest.fixture(scope="session")
def archivo_base_real(tmp_path_factory):
    """Validación opcional del panel y pronósticos completos; nunca usa la base del desarrollador.

    SART_DATOS_REALES apunta a la carpeta que contiene crudos/ y procesados/.
    Se necesitan también los insumos ambientales para comparar el panel completo.
    """
    from pathlib import Path

    from sart.tareas.carga import cargar_catalogo, cargar_clima, cargar_consultas, cargar_sinca

    if not os.environ.get("SART_DATOS_REALES"):
        pytest.skip("sin SART_DATOS_REALES: validación real opcional de T1")
    raiz = Path(os.environ["SART_DATOS_REALES"])
    crudos = raiz / "crudos"
    registro = crudos / "establecimientos.csv"
    if not registro.exists():
        registro = crudos / "establecimientos_20260818.csv"
    requeridos = [
        registro,
        crudos / "at_urg_respiratorio_semanal.parquet",
        crudos / "clima_openmeteo.csv",
        crudos / "sinca",
        raiz / "procesados" / "panel_semanal.parquet",
    ]
    faltantes = [str(p) for p in requeridos if not p.exists()]
    if faltantes:
        pytest.fail("SART_DATOS_REALES incompleto: " + ", ".join(faltantes))
    ruta = tmp_path_factory.mktemp("base_real") / "sart.db"
    motor = create_engine(f"sqlite:///{ruta.as_posix()}")
    Base.metadata.create_all(motor)
    try:
        with Session(motor) as sesion:
            cargar_catalogo(sesion, registro)
            cargar_consultas(sesion, requeridos[1])
            cargar_sinca(sesion, crudos / "sinca")
            cargar_clima(sesion, crudos / "clima_openmeteo.csv")
    finally:
        motor.dispose()
    return ruta
