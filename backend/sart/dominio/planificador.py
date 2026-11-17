"""Qué tarea programada toca en cada momento (RNF-P-1, TC-13, T11). Lógica pura: no corre nada.

Los horarios salen de ``horarios`` en ``config/parametros.yaml`` (RNF-M-4), en la hora local de
``zona_horaria``:

- respaldo (``respaldo``), ingesta (``ingesta``) y alerta ambiental (``alerta_ambiental``): todos los días;
- pronóstico (``pronostico``) y boletín (``boletin``, antes de ``boletin_limite``): el ``dia_semanal``;
- seguimiento de RB-2: cada ``seguimiento_cada_minutos``.

``tareas_debidas(desde, hasta)`` devuelve las que caen en el intervalo ``(desde, hasta]``, en orden. Si el
planificador estuvo detenido, no se ponen al día las corridas perdidas: el intervalo lo fija quien llama.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from typing import Any
from zoneinfo import ZoneInfo

DIAS = ("lunes", "martes", "miercoles", "jueves", "viernes", "sabado", "domingo")
_SIN_TILDE = str.maketrans("áéíóú", "aeiou")


class ErrorHorarios(ValueError):
    """Los horarios del YAML no se pueden usar."""


@dataclass(frozen=True)
class Tarea:
    nombre: str
    comando: tuple[str, ...]  # argumentos para ``python -m``
    hora: time | None  # None: periódica
    solo_dia: int | None = None  # 0 = lunes; None: todos los días
    cada_minutos: int | None = None


def _hora(texto: str, clave: str) -> time:
    try:
        horas, minutos = (int(p) for p in str(texto).split(":"))
        return time(horas, minutos)
    except ValueError as error:
        raise ErrorHorarios(f"horarios.{clave} debe ser HH:MM (es {texto!r})") from error


def tareas_programadas(horarios: dict[str, Any]) -> list[Tarea]:
    """Las tareas del día de SART con su horario, en el orden en que se corren."""
    nombre_dia = str(horarios["dia_semanal"]).lower().translate(_SIN_TILDE)
    if nombre_dia not in DIAS:
        raise ErrorHorarios(f"horarios.dia_semanal no es un día de la semana: {horarios['dia_semanal']!r}")
    dia = DIAS.index(nombre_dia)
    boletin, limite = (
        _hora(horarios["boletin"], "boletin"),
        _hora(horarios["boletin_limite"], "boletin_limite"),
    )
    pronostico = _hora(horarios["pronostico"], "pronostico")
    if not pronostico < boletin < limite:
        raise ErrorHorarios("horarios.boletin debe quedar después del pronóstico y antes de boletin_limite")
    cada = int(horarios["seguimiento_cada_minutos"])
    if not 1 <= cada <= 24 * 60:
        raise ErrorHorarios("horarios.seguimiento_cada_minutos debe estar entre 1 y 1440")
    return [
        Tarea("respaldo", ("sart.respaldo", "crear"), _hora(horarios["respaldo"], "respaldo")),
        Tarea("ingesta", ("sart.tareas.descarga",), _hora(horarios["ingesta"], "ingesta")),
        Tarea("pronostico", ("sart.tareas", "semanal"), pronostico, solo_dia=dia),
        Tarea(
            "alerta_ambiental",
            ("sart.tareas", "ambiental"),
            _hora(horarios["alerta_ambiental"], "alerta_ambiental"),
        ),
        Tarea("boletin", ("sart.tareas", "boletin"), boletin, solo_dia=dia),
        Tarea("seguimiento", ("sart.tareas", "seguimiento"), None, cada_minutos=cada),
    ]


def _momentos(tarea: Tarea, desde: datetime, hasta: datetime, zona: ZoneInfo) -> list[datetime]:
    if tarea.cada_minutos is not None:
        paso = timedelta(minutes=tarea.cada_minutos)
        inicio_dia = datetime.combine(desde.astimezone(zona).date(), time(0), zona)
        n = (desde - inicio_dia) // paso + 1
        momento, salida = inicio_dia + n * paso, []
        while momento <= hasta:
            salida.append(momento)
            momento += paso
        return salida
    salida = []
    dia: date = desde.astimezone(zona).date()
    while dia <= hasta.astimezone(zona).date():
        momento = datetime.combine(dia, tarea.hora, zona)
        if desde < momento <= hasta and (tarea.solo_dia is None or dia.weekday() == tarea.solo_dia):
            salida.append(momento)
        dia += timedelta(days=1)
    return salida


def tareas_debidas(
    desde: datetime, hasta: datetime, horarios: dict[str, Any], zona_horaria: str
) -> list[tuple[datetime, Tarea]]:
    """Las tareas cuyo horario cae en ``(desde, hasta]``, ordenadas por hora y por el orden del día."""
    if desde.tzinfo is None or hasta.tzinfo is None:
        raise ValueError("desde y hasta deben tener zona horaria")
    zona = ZoneInfo(zona_horaria)
    tareas = tareas_programadas(horarios)
    debidas = [(m, i, t) for i, t in enumerate(tareas) for m in _momentos(t, desde, hasta, zona)]
    return [(m, t) for m, _, t in sorted(debidas, key=lambda x: (x[0], x[1]))]
