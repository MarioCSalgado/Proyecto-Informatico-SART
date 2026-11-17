
"""Cálculo del promedio diario pronosticado de MP2,5 (RF-4, RB-1 y RB-5).

La función recibe pronósticos horarios y zonas del escenario.
Devuelve un resultado por zona y día.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from math import isfinite
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from sart.dominio.mp25 import NivelMp25, clasificar_mp25


@dataclass(frozen=True)
class PronosticoHorarioMp25:
    zona: str
    fecha_hora: datetime
    valor: float


@dataclass(frozen=True)
class PromedioDiarioMp25:
    zona: str
    dia: date
    promedio: float | None
    nivel: NivelMp25 | None
    estado: str
    horas_recibidas: int
    horas_esperadas: int


def calcular_promedios_diarios_mp25(
    pronosticos: list[PronosticoHorarioMp25],
    zonas: list[str],
    primer_dia: date,
    umbrales: dict,
    zona_horaria: str = "America/Santiago",
    cantidad_dias: int = 5,
) -> list[PromedioDiarioMp25]:

    # Validaciones iniciales
    if cantidad_dias < 1:
        raise ValueError("cantidad_dias debe ser al menos 1")

    if len(set(zonas)) != len(zonas):
        raise ValueError("La lista de zonas no puede tener duplicados")

    try:
        zona = ZoneInfo(zona_horaria)
    except ZoneInfoNotFoundError as error:
        raise ValueError(
            f"Zona horaria desconocida: {zona_horaria}"
        ) from error

    # Agrupar pronósticos por zona e instante horario
    por_zona_hora: dict[tuple[str, datetime], float] = {}

    for registro in pronosticos:

        # Ignorar zonas que no pertenecen al escenario
        if registro.zona not in zonas:
            continue

        # Validar zona horaria
        if (
            registro.fecha_hora.tzinfo is None
            or registro.fecha_hora.utcoffset() is None
        ):
            raise ValueError(
                "Cada pronóstico debe incluir una zona horaria"
            )

        # Validar concentración
        valor = float(registro.valor)

        if not isfinite(valor) or valor < 0:
            raise ValueError(
                "Los valores pronosticados de MP2,5 "
                "deben ser finitos y no negativos"
            )

        # Normalizar instante a UTC y precisión horaria
        instante = (
            registro.fecha_hora
            .astimezone(UTC)
            .replace(minute=0, second=0, microsecond=0)
        )

        clave = (registro.zona, instante)

        # Rechazar horas duplicadas
        if clave in por_zona_hora:
            raise ValueError(
                f"Pronóstico horario duplicado para "
                f"{registro.zona} en {instante.isoformat()}"
            )

        por_zona_hora[clave] = valor

    # Calcular resultados por zona y día
    resultados: list[PromedioDiarioMp25] = []

    for nombre_zona in zonas:

        for desplazamiento in range(cantidad_dias):

            dia = primer_dia + timedelta(days=desplazamiento)

            inicio_local = datetime.combine(
                dia,
                datetime.min.time(),
                tzinfo=zona,
            )

            fin_local = datetime.combine(
                dia + timedelta(days=1),
                datetime.min.time(),
                tzinfo=zona,
            )

            inicio_utc = inicio_local.astimezone(UTC)
            fin_utc = fin_local.astimezone(UTC)

            horas = int(
                (fin_utc - inicio_utc).total_seconds() // 3600
            )

            instantes = [
                inicio_utc + timedelta(hours=hora)
                for hora in range(horas)
            ]

            valores = [
                por_zona_hora[(nombre_zona, instante)]
                for instante in instantes
                if (nombre_zona, instante) in por_zona_hora
            ]

            # Datos insuficientes
            if len(valores) != horas:
                resultados.append(
                    PromedioDiarioMp25(
                        zona=nombre_zona,
                        dia=dia,
                        promedio=None,
                        nivel=None,
                        estado="datos_insuficientes",
                        horas_recibidas=len(valores),
                        horas_esperadas=horas,
                    )
                )
                continue

            # Promedio y clasificación
            promedio = sum(valores) / horas

            resultados.append(
                PromedioDiarioMp25(
                    zona=nombre_zona,
                    dia=dia,
                    promedio=promedio,
                    nivel=clasificar_mp25(promedio, umbrales),
                    estado="clasificado",
                    horas_recibidas=horas,
                    horas_esperadas=horas,
                )
            )

    return resultados
