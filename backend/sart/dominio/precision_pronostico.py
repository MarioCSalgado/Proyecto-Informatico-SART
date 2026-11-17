
"""Evaluación de sensibilidad del pronóstico ambiental (TC-12 / RF-4)."""

from collections import defaultdict
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from math import fsum, isfinite
from zoneinfo import ZoneInfo


@dataclass(frozen=True)
class PronosticoHorario:
    fecha_hora: datetime
    emitido_en: datetime
    valor: float


@dataclass(frozen=True)
class ObservacionAmbiental:
    fecha_hora: datetime
    valor: float


@dataclass(frozen=True)
class ResultadoTC12:
    sensibilidad: float | None
    verdaderos_positivos: int
    falsos_negativos: int
    dias_observados_sobre_umbral: int
    dias_sin_pronostico: int
    dias_evaluados: int
    cumple: bool


def _a_local(fecha_hora: datetime, zona: ZoneInfo) -> datetime:
    if fecha_hora.tzinfo is None or fecha_hora.utcoffset() is None:
        raise ValueError("Las fechas del pronóstico y las observaciones deben incluir zona horaria.")
    return fecha_hora.astimezone(zona)


def _validar_valor(valor: float) -> None:
    if not isfinite(valor) or valor < 0:
        raise ValueError("Los valores ambientales deben ser finitos y no negativos.")


def evaluar_sensibilidad_tc12(
    pronosticos: list[PronosticoHorario],
    observaciones: list[ObservacionAmbiental],
    zona_horaria: str,
    umbral: float = 50.0,
) -> ResultadoTC12:
    """Calcula la sensibilidad usando pronósticos emitidos al menos un día antes.

    Para cada fecha observada selecciona la emisión más reciente que:
    - se haya emitido, según la hora local, como máximo el día anterior;
    - contenga exactamente 24 registros horarios distintos.

    Los días observados sobre el umbral que no tengan un pronóstico válido
    cuentan como falsos negativos.
    """
    if not isfinite(umbral) or umbral < 0:
        raise ValueError("El umbral debe ser finito y no negativo.")

    zona = ZoneInfo(zona_horaria)

    # Agrupa los registros por día objetivo y emisión.
    grupos: dict[tuple[date, datetime], list[tuple[datetime, float]]] = defaultdict(list)

    for pronostico in pronosticos:
        objetivo = _a_local(pronostico.fecha_hora, zona)
        _a_local(pronostico.emitido_en, zona)  # valida la fecha de emisión
        _validar_valor(pronostico.valor)

        emision_utc = pronostico.emitido_en.astimezone(UTC)
        grupos[(objetivo.date(), emision_utc)].append(
            (objetivo, float(pronostico.valor))
        )

    # Solo se consideran emisiones con cobertura horaria completa.
    candidatos: dict[date, list[tuple[datetime, float]]] = defaultdict(list)

    for (dia_objetivo, emision_utc), registros in grupos.items():
        emision_local = emision_utc.astimezone(zona)

        if emision_local.date() > dia_objetivo - timedelta(days=1):
            continue

        horas = {
            (momento.hour, momento.minute, momento.second, momento.microsecond)
            for momento, _ in registros
        }

        cobertura_completa = (
            len(registros) == 24
            and len(horas) == 24
            and {hora[0] for hora in horas} == set(range(24))
            and all(hora[1:] == (0, 0, 0) for hora in horas)
        )

        if not cobertura_completa:
            continue

        promedio = fsum(valor for _, valor in registros) / 24
        candidatos[dia_objetivo].append((emision_utc, promedio))

    # Agrupa las mediciones observadas por día local.
    observaciones_diarias: dict[date, list[float]] = defaultdict(list)

    for observacion in observaciones:
        momento = _a_local(observacion.fecha_hora, zona)
        _validar_valor(observacion.valor)
        observaciones_diarias[momento.date()].append(float(observacion.valor))

    verdaderos_positivos = 0
    falsos_negativos = 0
    dias_observados_sobre_umbral = 0
    dias_sin_pronostico = 0

    for dia, valores_observados in observaciones_diarias.items():
        promedio_observado = fsum(valores_observados) / len(valores_observados)
        observado_sobre_umbral = promedio_observado > umbral

        if observado_sobre_umbral:
            dias_observados_sobre_umbral += 1

        emisiones_validas = candidatos.get(dia, [])

        if not emisiones_validas:
            dias_sin_pronostico += 1
            if observado_sobre_umbral:
                falsos_negativos += 1
            continue

        # Se utiliza la emisión válida más reciente.
        _, promedio_pronosticado = max(emisiones_validas, key=lambda item: item[0])
        pronosticado_sobre_umbral = promedio_pronosticado > umbral

        if observado_sobre_umbral and pronosticado_sobre_umbral:
            verdaderos_positivos += 1
        elif observado_sobre_umbral and not pronosticado_sobre_umbral:
            falsos_negativos += 1

    if dias_observados_sobre_umbral == 0:
        sensibilidad = None
    else:
        sensibilidad = verdaderos_positivos / dias_observados_sobre_umbral

    return ResultadoTC12(
        sensibilidad=sensibilidad,
        verdaderos_positivos=verdaderos_positivos,
        falsos_negativos=falsos_negativos,
        dias_observados_sobre_umbral=dias_observados_sobre_umbral,
        dias_sin_pronostico=dias_sin_pronostico,
        dias_evaluados=len(observaciones_diarias),
        cumple=sensibilidad is not None and sensibilidad >= 0.50,
    )
