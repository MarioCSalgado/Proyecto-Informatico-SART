
from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from sart.dominio.precision_pronostico import (
    ObservacionAmbiental,
    PronosticoHorario,
    evaluar_sensibilidad_tc12,
)

ZONA = ZoneInfo("America/Santiago")


def _pronostico(dia, emision, valor, horas=24):
    inicio = datetime.combine(dia, time.min, tzinfo=ZONA)
    emitido = datetime.combine(emision, time(7), tzinfo=ZONA)

    return [
        PronosticoHorario(
            fecha_hora=inicio + timedelta(hours=i),
            emitido_en=emitido,
            valor=valor,
        )
        for i in range(horas)
    ]


def _observacion(dia, valor):
    return ObservacionAmbiental(
        fecha_hora=datetime.combine(dia, time.min, tzinfo=ZONA),
        valor=valor,
    )


def test_tc12_calcula_sensibilidad_correctamente():
    dia1 = date(2026, 10, 10)
    dia2 = date(2026, 10, 11)

    pronosticos = (
        _pronostico(dia1, dia1 - timedelta(days=1), 60)
        + _pronostico(dia2, dia2 - timedelta(days=1), 40)
    )
    observaciones = [
        _observacion(dia1, 70),
        _observacion(dia2, 65),
    ]

    resultado = evaluar_sensibilidad_tc12(
        pronosticos, observaciones, "America/Santiago"
    )

    assert resultado.verdaderos_positivos == 1
    assert resultado.falsos_negativos == 1
    assert resultado.dias_observados_sobre_umbral == 2
    assert resultado.sensibilidad == 0.5
    assert resultado.cumple is True


def test_tc12_sin_dias_sobre_umbral_no_es_evaluable():
    dia = date(2026, 10, 10)

    resultado = evaluar_sensibilidad_tc12(
        _pronostico(dia, dia - timedelta(days=1), 60),
        [_observacion(dia, 40)],
        "America/Santiago",
    )

    assert resultado.sensibilidad is None
    assert resultado.cumple is False
    assert resultado.dias_observados_sobre_umbral == 0


def test_tc12_no_acepta_emision_del_mismo_dia():
    dia = date(2026, 10, 10)

    resultado = evaluar_sensibilidad_tc12(
        _pronostico(dia, dia, 80),
        [_observacion(dia, 70)],
        "America/Santiago",
    )

    assert resultado.verdaderos_positivos == 0
    assert resultado.falsos_negativos == 1
    assert resultado.dias_sin_pronostico == 1
    assert resultado.sensibilidad == 0.0


def test_tc12_pronostico_incompleto_cuenta_como_faltante():
    dia = date(2026, 10, 10)

    resultado = evaluar_sensibilidad_tc12(
        _pronostico(dia, dia - timedelta(days=1), 80, horas=23),
        [_observacion(dia, 70)],
        "America/Santiago",
    )

    assert resultado.verdaderos_positivos == 0
    assert resultado.falsos_negativos == 1
    assert resultado.dias_sin_pronostico == 1
    assert resultado.sensibilidad == 0.0
