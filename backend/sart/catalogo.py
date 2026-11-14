"""Comando para cargar el catálogo de centros y las consultas del DEIS en la base (CI-3, RF-1).

Uso, desde ``backend/`` (con la base migrada: ``alembic upgrade head``)::

    .venv/Scripts/python -m sart.catalogo cargar --prueba          # datos sintéticos de datos/prueba
    .venv/Scripts/python -m sart.catalogo cargar --establecimientos RUTA.csv [--consultas RUTA.parquet]

Se puede repetir: actualiza lo que ya existe sin duplicar.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from sqlalchemy.orm import Session

from sart.configuracion import RAIZ_REPOSITORIO
from sart.db.sesion import SinBaseDeDatos, crear_motor
from sart.parametros import ErrorParametros
from sart.tareas.carga import cargar_catalogo, cargar_consultas

PRUEBA = RAIZ_REPOSITORIO / "datos" / "prueba" / "crudos"


def _argumentos(argv: list[str] | None) -> argparse.Namespace:
    analizador = argparse.ArgumentParser(prog="python -m sart.catalogo", description="Catálogo y consultas.")
    acciones = analizador.add_subparsers(dest="accion", required=True)
    cargar = acciones.add_parser("cargar", help="carga centros (y consultas, si se indica el archivo)")
    cargar.add_argument("--prueba", action="store_true", help="usar los archivos sintéticos de datos/prueba")
    cargar.add_argument("--establecimientos", type=Path, help="registro de establecimientos (CSV del MINSAL)")
    cargar.add_argument("--consultas", type=Path, help="urgencias respiratorias semanales (parquet del DEIS)")
    return analizador.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _argumentos(argv)
    establecimientos, consultas = args.establecimientos, args.consultas
    if args.prueba:
        establecimientos = establecimientos or PRUEBA / "establecimientos.csv"
        consultas = consultas or PRUEBA / "at_urg_respiratorio_semanal.parquet"
    if establecimientos is None:
        print(
            "Indique --establecimientos RUTA.csv, o --prueba para los datos de datos/prueba.", file=sys.stderr
        )
        return 1

    try:
        motor = crear_motor()
        try:
            with Session(motor) as sesion:
                catalogo = cargar_catalogo(sesion, establecimientos)
                fuera, por_tipo = catalogo.omitidos_fuera_del_escenario, catalogo.omitidos_por_tipo
                print(
                    f"Catálogo: {catalogo.zonas} zonas, {catalogo.estaciones} estaciones y "
                    f"{catalogo.centros} centros. Omitidos: {fuera} fuera de las comunas del escenario "
                    f"y {por_tipo} que no son de urgencia."
                )
                if consultas is not None:
                    print("Cargando consultas (puede tardar un par de minutos)…")
                    resumen = cargar_consultas(sesion, consultas)
                    sin_catalogo = resumen.establecimientos_sin_catalogo
                    omitidas = sum(resumen.causas_omitidas.values())
                    print(
                        f"Consultas: {resumen.filas} registros de {resumen.centros} centros "
                        f"en {resumen.semanas} semanas. Omitidos: {sin_catalogo} establecimientos "
                        f"sin catálogo y {omitidas} filas de causas que no se cargan."
                    )
        finally:
            motor.dispose()
    except (ValueError, OSError, ErrorParametros, SinBaseDeDatos) as error:
        print(f"No se completó la carga: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
