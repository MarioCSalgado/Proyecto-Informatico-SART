"""Escala de MP2,5 en 5 niveles (RB-1, D.S. 12/2011 y PPDA D.S. 6/2018). Lógica pura.

Los límites vienen de ``config/parametros.yaml`` (``mp25_niveles``, RNF-M-4). Los nombres son los de RB-1 y
TC-05; el diseño de Figma usa «Bueno» y «Regular», pero se sigue la especificación (pendientes #25). Los
límites son enteros porque el promedio de 24 h se compara redondeado (pendientes #8).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class NivelMp25:
    clave: str
    nombre: str
    desde: int
    hasta: int | None  # None: sin límite superior


def niveles_mp25(umbrales: dict[str, Any]) -> list[NivelMp25]:
    normal_hasta = int(umbrales["normal_hasta"])
    alerta = int(umbrales["alerta_desde"])
    preemergencia = int(umbrales["preemergencia_desde"])
    emergencia = int(umbrales["emergencia_desde"])
    if not 0 < normal_hasta < alerta - 1 < preemergencia - 1 < emergencia - 1:
        raise ValueError("Los límites de mp25_niveles en parametros.yaml deben ir de menor a mayor.")
    return [
        NivelMp25("normal", "Normal", 0, normal_hasta),
        NivelMp25("sobre_la_norma", "Sobre la norma", normal_hasta + 1, alerta - 1),
        NivelMp25("alerta", "Alerta", alerta, preemergencia - 1),
        NivelMp25("preemergencia", "Preemergencia", preemergencia, emergencia - 1),
        NivelMp25("emergencia", "Emergencia", emergencia, None),
    ]


def clasificar_mp25(valor: float, umbrales: dict[str, Any]) -> NivelMp25:
    """Nivel de RB-1 para un promedio de 24 h de MP2,5 (RF-4, TC-05).

    Se compara tal como lo escribe RB-1: Normal ≤ 50; sobre la norma > 50 y < 80; Alerta 80 a < 110;
    Preemergencia 110 a < 170; Emergencia ≥ 170. Si el promedio debe redondearse antes, es la pendiente #8.
    """
    if valor < 0:
        raise ValueError("Una concentración de MP2,5 no puede ser negativa.")
    normal, sobre_la_norma, alerta, preemergencia, emergencia = niveles_mp25(umbrales)
    if valor <= umbrales["normal_hasta"]:
        return normal
    if valor < umbrales["alerta_desde"]:
        return sobre_la_norma
    if valor < umbrales["preemergencia_desde"]:
        return alerta
    if valor < umbrales["emergencia_desde"]:
        return preemergencia
    return emergencia
