"""Carga de mediciones ambientales: MP2,5 diario de SINCA, clima diario y pronóstico horario de MP2,5 de
Open-Meteo (RF-1, RF-4, RB-5). Usa los archivos sintéticos de datos/prueba."""

from datetime import datetime

import pytest
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session

from sart.configuracion import RAIZ_REPOSITORIO
from sart.db.modelos import Base, Estacion, Medicion
from sart.dominio.mediciones import valor_sinca
from sart.dominio.valores import CalidadDato, OrigenMedicion, TipoMedicion
from sart.tareas.carga import cargar_catalogo, cargar_clima, cargar_pronostico_mp25, cargar_sinca

PRUEBA = RAIZ_REPOSITORIO / "datos" / "prueba" / "crudos"
CABECERA_SINCA = (
    "FECHA (YYMMDD);HORA (HHMM);Registros validados;Registros preliminares;Registros no validados;\n"
)


@pytest.fixture
def sesion():
    motor = create_engine("sqlite://")
    Base.metadata.create_all(motor)
    with Session(motor) as sesion:
        cargar_catalogo(sesion, PRUEBA / "establecimientos.csv")
        yield sesion
    motor.dispose()


def _contar(sesion, *condiciones) -> int:
    return sesion.scalar(select(func.count()).select_from(Medicion).where(*condiciones))


def _estacion(sesion, nombre) -> Estacion:
    return sesion.scalars(select(Estacion).where(Estacion.nombre == nombre)).one()


# --- Regla del dato de SINCA (lógica pura) -----------------------------------
def test_sinca_prefiere_validado_sobre_preliminar_y_no_validado():
    assert valor_sinca("12,5", "13,0", "14") == (12.5, CalidadDato.VALIDADO)
    assert valor_sinca(None, "13,0", "14") == (13.0, CalidadDato.PRELIMINAR)
    assert valor_sinca("", None, "14,2") == (14.2, CalidadDato.NO_VALIDADO)


def test_sinca_sin_dato_o_negativo_no_se_usa():
    assert valor_sinca(None, None, None) is None
    assert valor_sinca("-3", None, None) is None


# --- SINCA -------------------------------------------------------------------
def test_sinca_carga_las_seis_estaciones_con_su_calidad(sesion):
    resumen = cargar_sinca(sesion, PRUEBA / "sinca")

    assert resumen.estaciones == 6
    assert resumen.filas == _contar(sesion, Medicion.tipo == TipoMedicion.MP25)
    assert resumen.sin_dato > 0  # días sin validado ni preliminar
    assert _contar(sesion, Medicion.calidad == CalidadDato.PRELIMINAR) > 0
    assert _contar(sesion, Medicion.unidad != "µg/m³") == 0


def test_sinca_guarda_el_dia_local_en_utc(sesion):
    """El 1 de enero de 2014 a las 00:00 de Santiago (horario de verano, UTC−3) son las 03:00 UTC."""
    cargar_sinca(sesion, PRUEBA / "sinca")
    kingston = _estacion(sesion, "Kingston College")

    primera = sesion.scalars(
        select(Medicion).where(Medicion.estacion_id == kingston.id).order_by(Medicion.fecha_hora)
    ).first()

    assert primera.fecha_hora.replace(tzinfo=None) == datetime(2014, 1, 1, 3, 0)


def test_sinca_casos_borde_y_archivo_sin_estacion(sesion, tmp_path):
    carpeta = tmp_path / "sinca"
    carpeta.mkdir()
    (carpeta / "Punteras.csv").write_text(
        CABECERA_SINCA
        + "260101;0000;10,5;11;;\n"  # validado
        + "260102;0000;;12,5;;\n"  # preliminar
        + "260103;0000;;;;\n"  # sin dato
        + "260104;0000;-1;;;\n",  # inválido
        encoding="latin-1",
    )
    (carpeta / "Estación desconocida.csv").write_text(
        CABECERA_SINCA + "260101;0000;5;;;\n", encoding="latin-1"
    )

    resumen = cargar_sinca(sesion, carpeta)

    assert resumen.filas == 2
    assert resumen.sin_dato == 2
    assert resumen.archivos_sin_estacion == ["Estación desconocida.csv"]
    valores = sorted(sesion.scalars(select(Medicion.valor)))
    assert valores == [10.5, 12.5]


def test_sinca_dos_veces_no_duplica(sesion):
    primera = cargar_sinca(sesion, PRUEBA / "sinca")
    cargar_sinca(sesion, PRUEBA / "sinca")

    assert _contar(sesion) == primera.filas


# --- Open-Meteo ----------------------------------------------------------------
def test_clima_diario_en_la_estacion_de_open_meteo(sesion):
    resumen = cargar_clima(sesion, PRUEBA / "clima_openmeteo.csv")

    open_meteo = _estacion(sesion, "Open-Meteo Concepción")
    assert resumen.filas == 3 * 4659
    assert _contar(sesion, Medicion.estacion_id == open_meteo.id) == resumen.filas
    assert _contar(sesion, Medicion.tipo == TipoMedicion.HUMEDAD, Medicion.unidad == "%") == 4659
    assert _contar(sesion, Medicion.tipo == TipoMedicion.TEMPERATURA_MINIMA, Medicion.unidad == "°C") == 4659


def test_pronostico_horario_de_mp25_queda_como_pronostico(sesion):
    """RF-4 usa el pronóstico de MP2,5; se distingue de lo observado por su origen."""
    resumen = cargar_pronostico_mp25(sesion, PRUEBA / "pronostico_mp25_openmeteo.csv")

    assert resumen.filas == 2 * 120
    assert _contar(sesion, Medicion.origen == OrigenMedicion.PRONOSTICO) == 240
    assert _contar(sesion, Medicion.origen == OrigenMedicion.OBSERVADO) == 0
    assert _contar(sesion, Medicion.tipo == TipoMedicion.MP10) == 120


def test_sin_catalogo_da_error_claro(tmp_path):
    motor = create_engine("sqlite://")
    Base.metadata.create_all(motor)
    with Session(motor) as sesion, pytest.raises(ValueError, match="catálogo"):
        cargar_clima(sesion, PRUEBA / "clima_openmeteo.csv")
    motor.dispose()
