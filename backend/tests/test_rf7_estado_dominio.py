"""Lógica pura del estado de un centro (RF-7 E1 y E3, RB-5)."""

from datetime import date

import pytest

from sart.dominio.estado_centro import MedicionDiaria, datos_antiguos, elegir_mp25, nivel_observado

CORTE = date(2026, 9, 27)  # domingo de la SE 39; la semana cierra el sábado 03/10


@pytest.mark.parametrize(
    ("hoy", "antiguos"),
    [
        (date(2026, 10, 5), False),  # lunes siguiente: 2 días desde el cierre
        (date(2026, 10, 11), False),  # 8 días: todavía no
        (date(2026, 10, 12), True),  # 9 días: aviso (RF-7 E1)
    ],
)
def test_rf7_e1_datos_antiguos_cuenta_desde_el_cierre_de_la_semana(hoy, antiguos):
    assert datos_antiguos(CORTE, hoy, dias_aviso=8) is antiguos


@pytest.mark.parametrize(
    ("consultas", "nivel"),
    [(100, "normal"), (150, "normal"), (151, "atencion"), (200, "atencion"), (201, "alerta")],
)
def test_nivel_observado_sin_margen_y_supera_estricto(consultas, nivel):
    """El nivel de una semana ya ocurrida compara las consultas reales con los umbrales (sin margen k)."""
    assert nivel_observado(consultas, umbral_atencion=150, umbral_alerta=200) == nivel


def test_nivel_observado_sin_umbral():
    assert nivel_observado(100, umbral_atencion=None, umbral_alerta=None) is None


HOY = date(2026, 10, 5)
PROPIA = MedicionDiaria("Punteras", date(2026, 10, 4), 30.0)
RESPALDO = MedicionDiaria("Kingston College", date(2026, 10, 4), 60.0)


def test_rb5_usa_la_estacion_asignada_si_reporto_en_la_semana():
    mp = elegir_mp25(PROPIA, RESPALDO, HOY, asignada_es_respaldo=False)
    assert (mp.estado, mp.medicion, mp.de_respaldo) == ("ok", PROPIA, False)


def test_rb5_sin_dato_propio_usa_la_de_respaldo_y_lo_marca():
    antigua = MedicionDiaria("Punteras", date(2026, 9, 20), 30.0)
    mp = elegir_mp25(antigua, RESPALDO, HOY, asignada_es_respaldo=False)
    assert (mp.estado, mp.medicion, mp.de_respaldo) == ("ok", RESPALDO, True)
    assert elegir_mp25(None, RESPALDO, HOY, asignada_es_respaldo=False).de_respaldo is True


def test_rb5_ninguna_reporto_en_la_semana_datos_insuficientes_con_la_ultima_valida():
    propia = MedicionDiaria("Punteras", date(2026, 9, 20), 30.0)
    respaldo = MedicionDiaria("Kingston College", date(2026, 9, 25), 60.0)
    mp = elegir_mp25(propia, respaldo, HOY, asignada_es_respaldo=False)
    assert (mp.estado, mp.medicion, mp.de_respaldo) == ("datos_insuficientes", respaldo, True)
    assert elegir_mp25(None, None, HOY, asignada_es_respaldo=False).medicion is None


def test_rb5_si_la_asignada_es_la_de_respaldo_no_se_marca():
    mp = elegir_mp25(RESPALDO, RESPALDO, HOY, asignada_es_respaldo=True)
    assert (mp.estado, mp.de_respaldo) == ("ok", False)
