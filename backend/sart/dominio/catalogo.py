"""Clasificación de lo que traen el registro de establecimientos y las urgencias del DEIS (CI-3, RF-1).

Las tablas de equivalencias (tipos, causas y estación por comuna) vienen de ``config/parametros.yaml``
(secciones ``catalogo`` e ``ingesta``, RNF-M-4). Las glosas del MINSAL cambian de mayúsculas y tildes entre
versiones, por eso se comparan normalizadas.
"""

from __future__ import annotations

import unicodedata

from sart.dominio.valores import TipoCentro


def normalizar(texto: str) -> str:
    """Minúsculas, sin tildes y con un solo espacio entre palabras."""
    sin_tildes = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode()
    return " ".join(sin_tildes.lower().split())


def tipo_centro(glosa: str | None, tipos: dict[str, str]) -> TipoCentro | None:
    """Tipo de §5.1 según ``TipoEstablecimientoGlosa``; ``None`` si no es un centro de urgencia."""
    if not glosa:
        return None
    equivalencias = {normalizar(origen): destino for origen, destino in tipos.items()}
    destino = equivalencias.get(normalizar(glosa))
    return TipoCentro(destino) if destino else None


def clave_causa(glosa: str, causas: dict[str, str]) -> str | None:
    """Clave de la causa si la glosa empieza como alguna de ``ingesta.causas``; si no, ``None``."""
    texto = normalizar(glosa)
    for inicio, clave in causas.items():
        if texto.startswith(normalizar(inicio)):
            return clave
    return None


def estacion_de_comuna(comuna: str, estacion_por_comuna: dict[str, str], respaldo: str) -> str:
    """Estación asignada a la comuna (CI-3); si la comuna no tiene asignación, la de respaldo (RB-5)."""
    mapa = {normalizar(c): e for c, e in estacion_por_comuna.items()}
    return mapa.get(normalizar(comuna), respaldo)
