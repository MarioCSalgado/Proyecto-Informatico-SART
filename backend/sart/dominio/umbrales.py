"""Umbrales de atención (p75) y alerta (p90) de cada centro (RB-3, RF-3). Criterio decidido el 14/11 (#6).

Se recalculan una vez al año (``umbrales.mes_recalculo``) con las últimas 52 × ``umbrales.anios_umbral``
semanas válidas de cada centro hasta la fecha del recálculo: sin los años de ``modelo.anios_excluidos``
(pandemia) y sin semanas incompletas (RB-4). Así se respeta el recálculo anual de RB-3 y se usan los datos
más recientes. Un centro con menos de ``modelo.min_semanas_historia`` semanas válidas no tiene umbral
(RF-3 E1). Cuantiles con interpolación lineal, igual que ``pandas.quantile`` en el notebook 5.
"""

from __future__ import annotations

from collections.abc import Collection
from dataclasses import dataclass
from datetime import date

import numpy as np

from sart.dominio.semanas import semana_epidemiologica

SEMANAS_POR_ANIO = 52


@dataclass(frozen=True)
class UmbralCalculado:
    atencion: float
    alerta: float
    desde: date  # primera semana usada
    hasta: date  # última semana usada
    semanas: int

    @property
    def descripcion(self) -> str:
        """Texto corto para ``umbral_centro.anios_usados``, p. ej. «2023-SE11 a 2026-SE09 (156 semanas)»."""
        (a1, s1), (a2, s2) = semana_epidemiologica(self.desde), semana_epidemiologica(self.hasta)
        return f"{a1}-SE{s1:02d} a {a2}-SE{s2:02d} ({self.semanas} semanas)"


def semanas_de_la_ventana(anios_umbral: int) -> int:
    return SEMANAS_POR_ANIO * int(anios_umbral)


def calcular_umbrales(
    series: dict[int, dict[date, float]],
    *,
    hasta: date,
    semanas: int,
    anios_excluidos: Collection[int],
    cuantil_atencion: float,
    cuantil_alerta: float,
    minimo_semanas: int,
    semanas_invalidas: Collection[date] = (),
) -> dict[int, UmbralCalculado]:
    """{centro: umbral} a partir de ``series`` = {centro: {inicio de semana: consultas respiratorias}}."""
    if not 0 < cuantil_atencion <= cuantil_alerta < 1:
        raise ValueError("Los cuantiles deben cumplir 0 < atención ≤ alerta < 1.")
    excluidos, invalidas = set(anios_excluidos), set(semanas_invalidas)
    resultado: dict[int, UmbralCalculado] = {}
    for centro, serie in series.items():
        validas = sorted(
            s
            for s in serie
            if s <= hasta and s not in invalidas and semana_epidemiologica(s)[0] not in excluidos
        )[-semanas:]
        if len(validas) < minimo_semanas:
            continue
        valores = np.array([serie[s] for s in validas], dtype=float)
        resultado[centro] = UmbralCalculado(
            atencion=float(np.quantile(valores, cuantil_atencion)),
            alerta=float(np.quantile(valores, cuantil_alerta)),
            desde=validas[0],
            hasta=validas[-1],
            semanas=len(validas),
        )
    return resultado
