"""Semanas epidemiológicas del MINSAL (RF-1, TC-01): de domingo a sábado, y la SE 1 es la primera semana con
4 o más días del año nuevo (el mismo calendario que la librería ``epiweeks`` llama «CDC»).

Se implementa aquí, sin dependencia nueva (pendientes #11), y se contrasta en las pruebas con las 666 semanas
del panel de prueba que el notebook 5 armó con ``epiweeks``.
"""

from __future__ import annotations

from collections import Counter
from datetime import date, datetime, timedelta


def _como_fecha(fecha: date | datetime) -> date:
    return fecha.date() if isinstance(fecha, datetime) else fecha


def _inicio_se1(anio: int) -> date:
    """Domingo en que empieza la SE 1 del año."""
    primero = date(anio, 1, 1)
    domingo = primero - timedelta(days=(primero.weekday() + 1) % 7)  # weekday(): lunes 0 … domingo 6
    dias_del_anio_nuevo = 7 - (primero - domingo).days
    return domingo if dias_del_anio_nuevo >= 4 else domingo + timedelta(days=7)


def semanas_del_anio(anio: int) -> int:
    """52 o 53."""
    return (_inicio_se1(anio + 1) - _inicio_se1(anio)).days // 7


def inicio_semana(anio: int, semana: int) -> date:
    """Domingo en que empieza la semana ``semana`` del año epidemiológico ``anio``."""
    if not 1 <= semana <= semanas_del_anio(anio):
        raise ValueError(f"El año {anio} no tiene semana epidemiológica {semana}.")
    return _inicio_se1(anio) + timedelta(weeks=semana - 1)


def semana_epidemiologica(fecha: date | datetime) -> tuple[int, int]:
    """(año epidemiológico, semana) de una fecha. Cerca del año nuevo, el año puede ser otro."""
    dia = _como_fecha(fecha)
    anio = dia.year
    if dia < _inicio_se1(anio):
        anio -= 1
    elif dia >= _inicio_se1(anio + 1):
        anio += 1
    return anio, (dia - _inicio_se1(anio)).days // 7 + 1


def fracciones_de_etiqueta(anio_calendario: int, semana: int) -> dict[tuple[int, int], float]:
    """Reparte una etiqueta del DEIS entre semanas epidemiológicas según sus días (TC-01, pendientes #11).

    El DEIS rotula con (año calendario, número de semana): la etiqueta junta los días de ese año calendario
    que tienen ese número de semana, que cerca del año nuevo pueden ser de dos semanas distintas. Se supone
    el mismo número de consultas por día (como el notebook 5, ``_reasignar_por_dias``).
    """
    dia, fin = date(anio_calendario, 1, 1), date(anio_calendario, 12, 31)
    dias: Counter[tuple[int, int]] = Counter()
    while dia <= fin:
        anio_epi, numero = semana_epidemiologica(dia)
        if numero == semana:
            dias[(anio_epi, numero)] += 1
        dia += timedelta(days=1)
    if not dias:
        raise ValueError(f"La etiqueta {anio_calendario}-{semana} no corresponde a ningún día de ese año.")
    total = sum(dias.values())
    return {clave: cantidad / total for clave, cantidad in sorted(dias.items())}
