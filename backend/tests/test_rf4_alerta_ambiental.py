"""RF_4, RB-1 y RB-5 promedio diario de MP2,5 pronosticado por zona"""

from datetime import UTC, date, datetime, timedelta

import pytest

from sart.dominio.ambiental import PronosticoHorarioMp25, calcular_promedios_diarios_mp25
from sart.parametros import cargar_parametros

UMBRALES = cargar_parametros()["mp25_niveles"]
DIA = date(2026, 10, 10)

def _pronosticos(zona: str, valor: float, cantidad: int = 24) -> list[PronosticoHorarioMp25]:
    inicio = datetime(2026, 10, 10, 3, tzinfo=UTC) # 00:00 en America/Santiago
    return [
        PronosticoHorarioMp25(zona, inicio + timedelta(hours = hora), valor)
        for hora in range(cantidad)
    ]

def test_rf4_promedio_diaro_95_emite_alerta():
    resultado = calcular_promedios_diarios_mp25(
        _pronosticos("Concepción", 95), ["Concepción"], DIA, UMBRALES
    )[0]

    assert resultado.estado == "clasificado"
    assert resultado.promedio == pytest.approx(95)
    assert resultado.nivel.clave == "alerta"
    assert resultado.horas_recibidas == resultado.horas_esperadas == 24

def test_rf4_dia_con_pronostico_horario_incompleto_datos_insuficientes():
    resultado = calcular_promedios_diarios_mp25(
        _pronosticos("Concepción", 95, cantidad = 23), ["Concepción"], DIA, UMBRALES
    )[0]

    assert resultado.estado == "datos_insuficientes"
    assert resultado.promedio is None
    assert resultado.nivel is None
    assert resultado.horas_recibidas == 23
    assert resultado.horas_esperadas == 24

def test_rb5_no_extrapola_pronostico_de_conce_a_otra_zona():
    resultados = calcular_promedios_diarios_mp25(
        _pronosticos("Concepción", 95), ["Concepción", "Coronel"], DIA, UMBRALES
    )

    por_zona = {resultado.zona: resultado for resultado in resultados if resultado.dia == DIA}
    concepcion = por_zona["Concepción"]
    coronel = por_zona["Coronel"]
    assert concepcion.nivel.clave == "alerta"
    assert coronel.estado == "datos_insuficientes"
    assert coronel.promedio is None

def test_rf4_sin_pronosticos_registra_datos_insuficientes_para_todas_las_zonas():
    resultados = calcular_promedios_diarios_mp25(
        [], ["Concepción", "Coronel"], DIA, UMBRALES
    )

    primer_dia = [resultado for resultado in resultados if resultado.dia == DIA]
    assert [resultado.estado for resultado in primer_dia] == [
        "datos_insuficientes",
        "datos_insuficientes",
    ]


def test_rf4_rechaza_pronosticos_sin_zona_horaria():
    pronostico = PronosticoHorarioMp25("Concepción", datetime(2026, 10, 10, 3), 95)

    with pytest.raises(ValueError, match="zona horaria"):
        calcular_promedios_diarios_mp25([pronostico], ["Concepción"], DIA, UMBRALES)


def test_rf4_rechaza_valores_negativos():
    with pytest.raises(ValueError, match="no negativos"):
        calcular_promedios_diarios_mp25(
            _pronosticos("Concepción", -1), ["Concepción"], DIA, UMBRALES
        )


def test_rf4_rechaza_horas_duplicadas():
    pronosticos = _pronosticos("Concepción", 95)
    pronosticos.append(pronosticos[0])

    with pytest.raises(ValueError, match="duplicado"):
        calcular_promedios_diarios_mp25(pronosticos, ["Concepción"], DIA, UMBRALES)
