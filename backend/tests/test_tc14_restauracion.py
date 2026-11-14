"""TC-14 · Restaurar el respaldo diario y volver a descargar las fuentes: sistema operativo en 2 h o menos
(RNF-D-2: RPO 24 h, RTO 2 h).

Contra PostgreSQL real, en dos bases temporales: se respalda una base con cuentas, auditoría y datos; se
restaura en otra vacía; lo propio del sistema vuelve entero y las fuentes públicas (consultas y mediciones),
que no se respaldan, se vuelven a cargar.
"""

import time
from datetime import UTC, datetime
from pathlib import Path

import pandas as pd
import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, func, select, text
from sqlalchemy.orm import Session

from sart.configuracion import RAIZ_REPOSITORIO
from sart.db.auditoria import registrar_auditoria
from sart.db.cuentas import dar_de_alta
from sart.db.modelos import AceptacionFinalidad, Auditoria, CentroSalud, ConsultaSemanal, Medicion, Usuario
from sart.dominio.cuentas import Aceptacion
from sart.parametros import cargar_parametros
from sart.tareas.carga import cargar_catalogo, cargar_consultas, cargar_pronostico_mp25
from sart.tareas.respaldo import ErrorRespaldo, crear_respaldo, docker_disponible, restaurar_respaldo

pytestmark = pytest.mark.integracion

PRUEBA = RAIZ_REPOSITORIO / "datos" / "prueba" / "crudos"
ALEMBIC_INI = Path(__file__).resolve().parents[1] / "alembic.ini"
TABLAS_SIN_DATOS = cargar_parametros()["respaldo"]["tablas_sin_datos"]
RTO_SEGUNDOS = 2 * 3600


@pytest.fixture(autouse=True)
def exige_docker():
    if not docker_disponible():
        pytest.skip("sin el contenedor de la base: no hay pg_dump para esta prueba")


def _migrar(url: str) -> None:
    config = Config(str(ALEMBIC_INI))
    config.attributes["url"] = url
    command.upgrade(config, "head")


@pytest.fixture
def consultas_recortadas(tmp_path) -> Path:
    datos = pd.read_parquet(PRUEBA / "at_urg_respiratorio_semanal.parquet")
    ruta = tmp_path / "consultas.parquet"
    datos[(datos["Anio"] == 2026) & datos["SemanaEstadistica"].isin([38, 39])].to_parquet(ruta)
    return ruta


def _contar(url: str) -> dict[str, int]:
    motor = create_engine(url)
    try:
        with Session(motor) as sesion:
            conteo = {
                modelo.__tablename__: sesion.scalar(select(func.count()).select_from(modelo))
                for modelo in (
                    Usuario,
                    AceptacionFinalidad,
                    Auditoria,
                    CentroSalud,
                    ConsultaSemanal,
                    Medicion,
                )
            }
            conteo["version"] = sesion.scalar(text("SELECT version_num FROM alembic_version"))
            return conteo
    finally:
        motor.dispose()


def test_tc14_respaldar_restaurar_y_volver_a_cargar(crear_base_temporal, consultas_recortadas, tmp_path):
    origen = crear_base_temporal()
    _migrar(origen)
    motor = create_engine(origen)
    with Session(motor) as sesion:
        cargar_catalogo(sesion, PRUEBA / "establecimientos.csv")
        cargar_consultas(sesion, consultas_recortadas)
        cargar_pronostico_mp25(sesion, PRUEBA / "pronostico_mp25_openmeteo.csv")
        usuario = dar_de_alta(
            sesion,
            nombre="Jefatura",
            correo="j@demo.sart",
            rol="jefatura",
            contrasena="clave larga de prueba",
            aceptacion=Aceptacion("2026-1", datetime.now(UTC)),
        )
        registrar_auditoria(sesion, autor=usuario, accion="confirmacion", entidad="notificacion")
        sesion.commit()
    motor.dispose()
    antes = _contar(origen)

    archivo = crear_respaldo(origen, tmp_path, TABLAS_SIN_DATOS)
    assert archivo.stat().st_size > 0

    destino = crear_base_temporal()
    inicio = time.monotonic()
    restaurar_respaldo(destino, archivo)
    restaurada = _contar(destino)

    # lo propio del sistema vuelve entero (RNF-D-2)
    for tabla in ("usuario", "aceptacion_finalidad", "auditoria", "centro_salud", "version"):
        assert restaurada[tabla] == antes[tabla], tabla
    # las fuentes públicas no van en el respaldo: solo su estructura
    assert antes["consulta_semanal"] > 0 and restaurada["consulta_semanal"] == 0
    assert antes["medicion"] > 0 and restaurada["medicion"] == 0

    # «volver a descargar las fuentes»
    motor = create_engine(destino)
    with Session(motor) as sesion:
        cargar_consultas(sesion, consultas_recortadas)
        cargar_pronostico_mp25(sesion, PRUEBA / "pronostico_mp25_openmeteo.csv")
    motor.dispose()
    recargada = _contar(destino)
    duracion = time.monotonic() - inicio

    assert recargada["consulta_semanal"] == antes["consulta_semanal"]
    assert recargada["medicion"] == antes["medicion"]
    assert duracion < RTO_SEGUNDOS


def test_restaurar_sobre_una_base_con_datos_la_reemplaza(crear_base_temporal, tmp_path):
    """--clean: lo que había en el destino se reemplaza por el respaldo, sin mezclar."""
    origen, destino = crear_base_temporal(), crear_base_temporal()
    for url in (origen, destino):
        _migrar(url)
    motor = create_engine(destino)
    with Session(motor) as sesion:
        cargar_catalogo(sesion, PRUEBA / "establecimientos.csv")
    motor.dispose()

    restaurar_respaldo(destino, crear_respaldo(origen, tmp_path, TABLAS_SIN_DATOS))

    assert _contar(destino)["centro_salud"] == 0


def test_respaldo_de_una_base_que_no_existe_da_error_claro(crear_base_temporal, tmp_path):
    inexistente = crear_base_temporal().rsplit("/", 1)[0] + "/no_existe_esta_base"

    with pytest.raises(ErrorRespaldo, match="no_existe_esta_base"):
        crear_respaldo(inexistente, tmp_path, TABLAS_SIN_DATOS)
    assert list(tmp_path.glob("*.dump")) == []  # no deja archivos a medias
