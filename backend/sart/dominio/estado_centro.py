"""Reglas del estado de un centro que se muestra a cada usuario (RF-7, RB-5). Lógica pura.

- **Datos antiguos (RF-7 E1):** se cuenta desde el sábado que cierra la semana de corte hasta hoy; sobre
  ``consulta.aviso_datos_antiguos_dias`` días, aviso visible.
- **Nivel observado:** el de una semana ya ocurrida, con sus consultas reales contra los umbrales del centro
  (sin margen k, que es para la incertidumbre del pronóstico). «Supera» es estrictamente mayor (#37).
- **MP2,5 de la zona (RB-5, RF-7 E3):** la estación asignada si reportó durante la última semana completa; si
  no, la de respaldo, marcada «de respaldo»; si ninguna, «datos insuficientes» con la última medición válida.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from typing import Literal

from sart.dominio.alerta_demanda import NivelDemanda

DIAS_SEMANA_COMPLETA = 7  # RB-5: «durante una semana completa» (definición, no supuesto)

EstadoMp25 = Literal["ok", "datos_insuficientes"]


def fin_de_semana(inicio: date) -> date:
    """Sábado en que cierra la semana epidemiológica que empieza el domingo ``inicio``."""
    return inicio + timedelta(days=6)


def datos_antiguos(fecha_corte: date, hoy: date, *, dias_aviso: int) -> bool:
    return (hoy - fin_de_semana(fecha_corte)).days > dias_aviso


def nivel_observado(
    consultas: float, *, umbral_atencion: float | None, umbral_alerta: float | None
) -> NivelDemanda | None:
    if umbral_atencion is None or umbral_alerta is None:
        return None
    if consultas > umbral_alerta:
        return "alerta"
    if consultas > umbral_atencion:
        return "atencion"
    return "normal"


@dataclass(frozen=True)
class MedicionDiaria:
    estacion: str
    fecha: date  # día local
    valor: float  # promedio de 24 h, µg/m³


@dataclass(frozen=True)
class Mp25Zona:
    estado: EstadoMp25
    medicion: MedicionDiaria | None
    de_respaldo: bool


def elegir_mp25(
    asignada: MedicionDiaria | None,
    respaldo: MedicionDiaria | None,
    hoy: date,
    *,
    asignada_es_respaldo: bool,
) -> Mp25Zona:
    """RB-5 con la última medición diaria de cada estación (``None`` si nunca reportó)."""

    def reciente(medicion: MedicionDiaria | None) -> bool:
        return medicion is not None and (hoy - medicion.fecha).days < DIAS_SEMANA_COMPLETA

    if reciente(asignada):
        return Mp25Zona("ok", asignada, de_respaldo=False)
    if reciente(respaldo):
        return Mp25Zona("ok", respaldo, de_respaldo=not asignada_es_respaldo)
    disponibles = [m for m in (asignada, respaldo) if m is not None]
    if not disponibles:
        return Mp25Zona("datos_insuficientes", None, de_respaldo=False)
    ultima = max(disponibles, key=lambda m: m.fecha)
    return Mp25Zona(
        "datos_insuficientes", ultima, de_respaldo=ultima is respaldo and not asignada_es_respaldo
    )
