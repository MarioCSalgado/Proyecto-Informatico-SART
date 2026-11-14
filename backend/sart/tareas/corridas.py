"""Log de corridas y aviso cuando una fuente falla varias veces seguidas (RNF-M-3).

Uso::

    with registrar_corrida(sesion, "ingesta", "DEIS") as corrida:
        resumen = cargar_consultas(sesion, ruta)
        corrida.filas = resumen.filas

Si el bloque lanza una excepción, se deshace lo que alcanzó a hacer, la corrida queda «fallida» con el
mensaje, y la excepción sigue su curso.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from sart.db.modelos import Corrida
from sart.dominio.valores import EstadoCorrida
from sart.parametros import cargar_parametros

LARGO_MAXIMO_MENSAJE = 2000


@contextmanager
def registrar_corrida(sesion: Session, tarea: str, fuente: str | None = None) -> Iterator[Corrida]:
    corrida = Corrida(tarea=tarea, fuente=fuente, inicio=datetime.now(UTC), estado=EstadoCorrida.EN_CURSO)
    sesion.add(corrida)
    sesion.commit()
    corrida_id = corrida.id
    try:
        yield corrida
    except Exception as error:
        sesion.rollback()
        fallida = sesion.get(Corrida, corrida_id)
        fallida.estado = EstadoCorrida.FALLIDA
        fallida.fin = datetime.now(UTC)
        fallida.mensaje = f"{type(error).__name__}: {error}"[:LARGO_MAXIMO_MENSAJE]
        sesion.commit()
        raise
    corrida.estado = EstadoCorrida.EXITOSA
    corrida.fin = datetime.now(UTC)
    sesion.commit()


def fallas_seguidas(sesion: Session, fuente: str) -> int:
    """Cuántas de las últimas corridas terminadas de la fuente fallaron sin un éxito entremedio."""
    estados = sesion.scalars(
        select(Corrida.estado)
        .where(Corrida.fuente == fuente, Corrida.estado != EstadoCorrida.EN_CURSO)
        .order_by(Corrida.inicio.desc(), Corrida.id.desc())
    )
    racha = 0
    for estado in estados:
        if estado is not EstadoCorrida.FALLIDA:
            break
        racha += 1
    return racha


def hay_que_avisar(sesion: Session, fuente: str, parametros: dict[str, Any] | None = None) -> bool:
    """RNF-M-3: avisar si la fuente falló ``ingesta.avisar_tras_fallas_seguidas`` veces seguidas o más."""
    limite = int((parametros or cargar_parametros())["ingesta"]["avisar_tras_fallas_seguidas"])
    return fallas_seguidas(sesion, fuente) >= limite
