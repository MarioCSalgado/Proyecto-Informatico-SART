
"""Integración de la evaluación TC-12 con las mediciones y pronósticos guardados."""

from datetime import date, datetime, timezone
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.orm import Session

from sart.db.modelos import Estacion, Medicion, PronosticoAmbiental
from sart.dominio.precision_pronostico import (
    ObservacionAmbiental,
    PronosticoHorario,
    ResultadoTC12,
    evaluar_sensibilidad_tc12,
)
from sart.dominio.valores import (
    FuenteEstacion,
    OrigenMedicion,
    TipoMedicion,
    UNIDAD_POR_TIPO,
)


def _como_utc(fecha: datetime) -> datetime:
    """Las fechas naive recuperadas desde la BD se interpretan como UTC."""
    if fecha.tzinfo is None or fecha.utcoffset() is None:
        return fecha.replace(tzinfo=timezone.utc)
    return fecha.astimezone(timezone.utc)


def evaluar_tc12_desde_bd(
    sesion: Session,
    zona_horaria: str = "America/Santiago",
    desde: date | None = None,
    hasta: date | None = None,
) -> ResultadoTC12:
    """Evalúa TC-12 comparando pronósticos Open-Meteo con Kingston College."""

    kingston = sesion.scalars(
        select(Estacion).where(
            Estacion.nombre == "Kingston College",
            Estacion.fuente == FuenteEstacion.SINCA,
        )
    ).one_or_none()

    if kingston is None:
        raise ValueError("No existe la estación SINCA Kingston College.")

    open_meteo = sesion.scalars(
        select(Estacion).where(
            Estacion.fuente == FuenteEstacion.OPEN_METEO,
        )
    ).one_or_none()

    if open_meteo is None:
        raise ValueError("No existe una estación Open-Meteo única.")

    unidad_esperada = UNIDAD_POR_TIPO[TipoMedicion.MP25]

    mediciones = sesion.scalars(
        select(Medicion).where(
            Medicion.estacion_id == kingston.id,
            Medicion.tipo == TipoMedicion.MP25,
            Medicion.origen == OrigenMedicion.OBSERVADO,
        )
    ).all()

    pronosticos_bd = sesion.scalars(
        select(PronosticoAmbiental).where(
            PronosticoAmbiental.estacion_id == open_meteo.id,
            PronosticoAmbiental.tipo == TipoMedicion.MP25,
        )
    ).all()

    observaciones = []
    for medicion in mediciones:
        if medicion.unidad != unidad_esperada:
            raise ValueError(
                f"Unidad inesperada en Kingston College: {medicion.unidad!r}."
            )

        fecha_hora = _como_utc(medicion.fecha_hora)

        if desde is not None or hasta is not None:
            dia_local = fecha_hora.astimezone(
                ZoneInfo(zona_horaria)
            ).date()
            if desde is not None and dia_local < desde:
                continue
            if hasta is not None and dia_local > hasta:
                continue

        observaciones.append(
            ObservacionAmbiental(
                fecha_hora=fecha_hora,
                valor=float(medicion.valor),
            )
        )

    pronosticos = []
    for pronostico in pronosticos_bd:
        if pronostico.unidad != unidad_esperada:
            raise ValueError(
                f"Unidad inesperada en pronóstico: {pronostico.unidad!r}."
            )

        fecha_hora = _como_utc(pronostico.fecha_hora)

        if desde is not None or hasta is not None:
            dia_local = fecha_hora.astimezone(
                ZoneInfo(zona_horaria)
            ).date()
            if desde is not None and dia_local < desde:
                continue
            if hasta is not None and dia_local > hasta:
                continue

        pronosticos.append(
            PronosticoHorario(
                fecha_hora=fecha_hora,
                emitido_en=_como_utc(pronostico.emitido_en),
                valor=float(pronostico.valor),
            )
        )

    return evaluar_sensibilidad_tc12(
        pronosticos,
        observaciones,
        zona_horaria,
    )
