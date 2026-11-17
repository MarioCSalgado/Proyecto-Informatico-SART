
from datetime import UTC, date, datetime, timedelta
from zoneinfo import ZoneInfo

import pytest
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from sart.db.modelos import Alerta, Auditoria, Corrida, Estacion, Medicion, Zona
from sart.db.supuestos import parametros_vigentes
from sart.dominio.valores import (
    EstadoCorrida,
    FuenteEstacion,
    OrigenMedicion,
    TipoAlerta,
    TipoMedicion,
)
from sart.tareas.__main__ import main
from sart.tareas.ambiental import TAREA, correr_ambiental


@pytest.fixture
def sesion(base_prueba):
    with Session(base_prueba) as sesion:
        yield sesion


def preparar_pronostico(sesion, fecha: date, valor: float = 95.0):
    """Inserta 24 horas de pronóstico para la estación Open-Meteo."""

    estacion = sesion.scalar(
        select(Estacion).where(
            Estacion.fuente == FuenteEstacion.OPEN_METEO
        )
    )
    assert estacion is not None, "La base de prueba debe tener una estación Open-Meteo."
    assert estacion.zona is not None

    parametros = parametros_vigentes(sesion)
    tz = ZoneInfo(parametros["zona_horaria"])

    inicio_local = datetime.combine(fecha, datetime.min.time(), tzinfo=tz)
    inicio_utc = inicio_local.astimezone(UTC)

    fin_utc = (inicio_local + timedelta(days=1)).astimezone(UTC)

    # Limpia únicamente los pronósticos del día y estación que usará esta prueba.
    sesion.execute(
        delete(Medicion).where(
            Medicion.estacion_id == estacion.id,
            Medicion.tipo == TipoMedicion.MP25,
            Medicion.origen == OrigenMedicion.PRONOSTICO,
            Medicion.fecha_hora >= inicio_utc,
            Medicion.fecha_hora < fin_utc,
        )
    )

    for hora in range(24):
        sesion.add(
            Medicion(
                estacion_id=estacion.id,
                fecha_hora=inicio_utc + timedelta(hours=hora),
                tipo=TipoMedicion.MP25,
                valor=valor,
                unidad="µg/m³",
                origen=OrigenMedicion.PRONOSTICO,
            )
        )

    sesion.commit()
    return estacion


def test_rf4_emite_alerta_con_promedio_sobre_umbral(sesion, monkeypatch):
    monkeypatch.setattr(
        "sart.tareas.ambiental._sensibilidad_tc12",
        lambda *args: (True, 1.0),
    )
    fecha = date(2026, 1, 15)
    estacion = preparar_pronostico(sesion, fecha, valor=95.0)

    resumen = correr_ambiental(sesion, fecha=fecha)

    alerta = sesion.scalar(
        select(Alerta).where(
            Alerta.tipo == TipoAlerta.AMBIENTAL,
            Alerta.zona_id == estacion.zona_id,
            Alerta.dia_pronosticado == fecha,
        )
    )

    assert resumen.alertas == 1
    assert resumen.promedios_calculados == 1
    assert alerta is not None
    assert "no constituye una declaración oficial" in alerta.mensaje
    assert "pronóstico" in alerta.mensaje
    assert alerta.nivel == "alerta"
    assert alerta.valor_mp25 == pytest.approx(95.0)


def test_rf4_no_duplica_alertas_al_repetir_corrida(sesion, monkeypatch):
    monkeypatch.setattr(
        "sart.tareas.ambiental._sensibilidad_tc12",
        lambda *args: (True, 1.0),
    )
    fecha = date(2026, 1, 15)
    estacion = preparar_pronostico(sesion, fecha, valor=95.0)

    correr_ambiental(sesion, fecha=fecha)
    segundo_resumen = correr_ambiental(sesion, fecha=fecha)

    cantidad = sesion.scalar(
        select(func.count(Alerta.id)).where(
            Alerta.tipo == TipoAlerta.AMBIENTAL,
            Alerta.zona_id == estacion.zona_id,
            Alerta.dia_pronosticado == fecha,
        )
    )

    assert cantidad == 1
    assert segundo_resumen.alertas == 0


def test_rf4_no_emite_alerta_con_nivel_normal(sesion, monkeypatch):
    monkeypatch.setattr(
        "sart.tareas.ambiental._sensibilidad_tc12",
        lambda *args: (True, 1.0),
    )
    fecha = date(2026, 1, 15)
    estacion = preparar_pronostico(sesion, fecha, valor=30.0)

    resumen = correr_ambiental(sesion, fecha=fecha)

    cantidad = sesion.scalar(
        select(func.count(Alerta.id)).where(
            Alerta.tipo == TipoAlerta.AMBIENTAL,
            Alerta.zona_id == estacion.zona_id,
            Alerta.dia_pronosticado == fecha,
        )
    )

    assert resumen.promedios_calculados == 1
    assert resumen.alertas == 0
    assert cantidad == 0

def test_rf4_cada_alerta_queda_en_la_auditoria(sesion, monkeypatch):
    monkeypatch.setattr(
        "sart.tareas.ambiental._sensibilidad_tc12",
        lambda *args: (True, 1.0),
    )
    fecha = date(2026, 1, 15)
    estacion = preparar_pronostico(sesion, fecha, valor=95.0)

    correr_ambiental(sesion, fecha=fecha)

    alerta = sesion.scalars(
        select(Alerta).where(
            Alerta.tipo == TipoAlerta.AMBIENTAL,
            Alerta.zona_id == estacion.zona_id,
            Alerta.dia_pronosticado == fecha,
        )
    ).one()

    registro = sesion.scalars(
        select(Auditoria).where(
            Auditoria.accion == "emision_alerta",
            Auditoria.entidad_id == str(alerta.id),
        )
    ).one()

    assert registro.autor_rol == "sistema"
    assert registro.valor_nuevo["tipo"] == "ambiental"
    assert registro.valor_nuevo["zona"] == estacion.zona.nombre
    assert registro.valor_nuevo["dia_pronosticado"] == fecha.isoformat()
    assert registro.valor_nuevo["nivel"] == "alerta"
    assert registro.valor_nuevo["valor_mp25"] == pytest.approx(95.0)


def test_rf4_corrida_queda_registrada_exitosamente(sesion, monkeypatch):
    monkeypatch.setattr(
        "sart.tareas.ambiental._sensibilidad_tc12",
        lambda *args: (True, 1.0),
    )
    fecha = date(2026, 1, 15)
    preparar_pronostico(sesion, fecha, valor=95.0)

    resumen = correr_ambiental(sesion, fecha=fecha)

    corrida = sesion.scalars(
        select(Corrida).where(Corrida.tarea == TAREA)
    ).one()

    assert corrida.estado is EstadoCorrida.EXITOSA
    assert corrida.filas == resumen.promedios_calculados
    assert corrida.filas == 1
    assert "1 alertas ambientales emitidas" in corrida.mensaje

def test_rf4_corrida_fallida_queda_registrada(sesion):
    parametros = {
        "zona_horaria": "America/Santiago",
    }

    with pytest.raises(KeyError):
        correr_ambiental(
            sesion,
            fecha=date(2026, 1, 15),
            parametros=parametros,
        )

    corrida = sesion.scalars(
        select(Corrida).where(Corrida.tarea == TAREA)
    ).one()

    assert corrida.estado is EstadoCorrida.FALLIDA
    assert corrida.fin is not None
    assert "KeyError" in corrida.mensaje

    alertas = sesion.scalars(select(Alerta)).all()
    auditorias = sesion.scalars(select(Auditoria)).all()

    assert alertas == []
    assert auditorias == []

def test_cli_ambiental_ejecuta_corrida_con_fecha(
    sesion, base_prueba, monkeypatch, capsys
):
    fecha = date(2026, 1, 15)
    preparar_pronostico(sesion, fecha, valor=95.0)

    monkeypatch.setenv(
        "DATABASE_URL",
        base_prueba.url.render_as_string(hide_password=False),
    )

    monkeypatch.setattr(
        "sart.tareas.ambiental._sensibilidad_tc12",
        lambda *args: (True, 1.0),
    )

    resultado = main(["ambiental", "--fecha", fecha.isoformat()])

    assert resultado == 0

    salida = capsys.readouterr().out
    assert f"Corrida ambiental desde {fecha}" in salida
    assert "1 alertas ambientales emitidas" in salida

    corrida = sesion.scalars(
        select(Corrida).where(Corrida.tarea == TAREA)
    ).one()

    assert corrida.estado is EstadoCorrida.EXITOSA


def test_cli_ambiental_sin_base_de_datos(monkeypatch, capsys):
    monkeypatch.delenv("DATABASE_URL", raising=False)

    assert main(["ambiental"]) == 1
    assert "DATABASE_URL" in capsys.readouterr().err



def _preparar_medicion_sinca(
    sesion,
    nombre_estacion: str,
    fecha: date,
    valor: float = 95.0,
):
    """Inserta o reemplaza una medición observada SINCA."""
    estacion = sesion.scalar(
        select(Estacion).where(Estacion.nombre == nombre_estacion)
    )
    assert estacion is not None, (
        f"No existe la estación SINCA {nombre_estacion!r}."
    )

    parametros = parametros_vigentes(sesion)
    tz = ZoneInfo(parametros["zona_horaria"])

    fecha_hora = datetime.combine(
        fecha,
        datetime.min.time(),
        tzinfo=tz,
    ).astimezone(UTC)

    # Evita conflictos con mediciones precargadas en la base de prueba.
    sesion.execute(
        delete(Medicion).where(
            Medicion.estacion_id == estacion.id,
            Medicion.tipo == TipoMedicion.MP25,
            Medicion.origen == OrigenMedicion.OBSERVADO,
            Medicion.fecha_hora == fecha_hora,
        )
    )

    sesion.add(
        Medicion(
            estacion_id=estacion.id,
            fecha_hora=fecha_hora,
            tipo=TipoMedicion.MP25,
            valor=valor,
            unidad="µg/m³",
            origen=OrigenMedicion.OBSERVADO,
        )
    )

    sesion.commit()
    return estacion



def test_rf4_sinca_emite_alerta_con_medicion_reciente(
    sesion, monkeypatch
):
    monkeypatch.setattr(
        "sart.tareas.ambiental._sensibilidad_tc12",
        lambda *args: (False, 0.0),
    )

    fecha = date(2026, 1, 15)
    estacion = _preparar_medicion_sinca(
        sesion,
        "Punteras",
        fecha,
        valor=95.0,
    )

    resumen = correr_ambiental(sesion, fecha=fecha)

    alerta = sesion.scalar(
        select(Alerta).where(
            Alerta.tipo == TipoAlerta.AMBIENTAL,
            Alerta.zona_id == estacion.zona_id,
            Alerta.fuente_ambiental == "sinca",
            Alerta.dia_observado == fecha,
        )
    )

    assert resumen.fuente == "sinca"
    assert resumen.alertas == 1
    assert alerta is not None
    assert alerta.fuente_ambiental == "sinca"
    assert alerta.dia_observado == fecha
    assert alerta.dia_pronosticado is None
    assert alerta.nivel == "alerta"
    assert alerta.valor_mp25 == pytest.approx(95.0)


def test_rf4_sinca_no_duplica_alertas_al_repetir_corrida(
    sesion, monkeypatch
):
    monkeypatch.setattr(
        "sart.tareas.ambiental._sensibilidad_tc12",
        lambda *args: (False, 0.0),
    )

    fecha = date(2026, 1, 15)
    estacion = _preparar_medicion_sinca(
        sesion,
        "Punteras",
        fecha,
        valor=95.0,
    )

    correr_ambiental(sesion, fecha=fecha)
    segundo_resumen = correr_ambiental(sesion, fecha=fecha)

    cantidad = sesion.scalar(
        select(func.count(Alerta.id)).where(
            Alerta.tipo == TipoAlerta.AMBIENTAL,
            Alerta.zona_id == estacion.zona_id,
            Alerta.fuente_ambiental == "sinca",
            Alerta.dia_observado == fecha,
        )
    )

    assert cantidad == 1
    assert segundo_resumen.alertas == 0


def test_rf4_sinca_utiliza_kingston_como_respaldo(
    sesion, monkeypatch
):
    monkeypatch.setattr(
        "sart.tareas.ambiental._sensibilidad_tc12",
        lambda *args: (False, 0.0),
    )

    fecha = date(2026, 1, 15)

    estacion_punteras = sesion.scalar(
        select(Estacion).where(Estacion.nombre == "Punteras")
    )
    assert estacion_punteras is not None

    # Eliminar mediciones observadas de Punteras para forzar el respaldo.
    sesion.execute(
        delete(Medicion).where(
            Medicion.estacion_id == estacion_punteras.id,
            Medicion.tipo == TipoMedicion.MP25,
            Medicion.origen == OrigenMedicion.OBSERVADO,
        )
    )
    sesion.commit()

    # Chiguayante tiene asignada Punteras, pero solo hay
    # una medición reciente de la estación de respaldo.
    estacion_respaldo = _preparar_medicion_sinca(
        sesion,
        "Kingston College",
        fecha,
        valor=95.0,
    )

    zona_chiguayante = sesion.scalar(
        select(Zona).where(Zona.nombre == "Chiguayante")
    )
    assert zona_chiguayante is not None

    resumen = correr_ambiental(sesion, fecha=fecha)

    alerta = sesion.scalar(
        select(Alerta).where(
            Alerta.tipo == TipoAlerta.AMBIENTAL,
            Alerta.zona_id == zona_chiguayante.id,
            Alerta.fuente_ambiental == "sinca",
            Alerta.dia_observado == fecha,
        )
    )

    assert estacion_respaldo is not None
    assert resumen.fuente == "sinca"
    assert alerta is not None
    assert alerta.valor_mp25 == pytest.approx(95.0)


def test_rf4_sinca_informa_datos_insuficientes_si_medicion_es_antigua(
    sesion, monkeypatch
):
    monkeypatch.setattr(
        "sart.tareas.ambiental._sensibilidad_tc12",
        lambda *args: (False, 0.0),
    )

    fecha = date(2026, 1, 15)

    estaciones = sesion.scalars(
        select(Estacion).where(
            Estacion.fuente == FuenteEstacion.SINCA
        )
    ).all()

    ids = [estacion.id for estacion in estaciones]
    assert ids

    # Elimina las mediciones observadas SINCA de la base de prueba
    # para controlar exactamente la antigüedad de los datos.
    sesion.execute(
        delete(Medicion).where(
            Medicion.estacion_id.in_(ids),
            Medicion.tipo == TipoMedicion.MP25,
            Medicion.origen == OrigenMedicion.OBSERVADO,
        )
    )
    sesion.commit()

    # Kingston tiene un dato, pero de diez días antes.
    _preparar_medicion_sinca(
        sesion,
        "Kingston College",
        fecha - timedelta(days=10),
        valor=95.0,
    )

    resumen = correr_ambiental(sesion, fecha=fecha)

    cantidad = sesion.scalar(
        select(func.count(Alerta.id)).where(
            Alerta.tipo == TipoAlerta.AMBIENTAL,
            Alerta.fuente_ambiental == "sinca",
            Alerta.dia_observado == fecha,
        )
    )

    assert resumen.fuente == "sinca"
    assert resumen.alertas == 0
    assert resumen.datos_insuficientes
    assert cantidad == 0
