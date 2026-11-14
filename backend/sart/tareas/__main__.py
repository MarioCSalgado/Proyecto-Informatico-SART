"""Comando de las corridas programadas (RNF-M-3). Por ahora, la corrida semanal de los lunes (RF-2, RF-3,
RF-6).

Uso, desde ``backend/`` (con la base migrada y los datos cargados: ``python -m sart.catalogo cargar``)::

    .venv/Scripts/python -m sart.tareas semanal                     # día de la corrida: hoy
    .venv/Scripts/python -m sart.tareas semanal --fecha 2026-10-05  # simula la corrida de ese día
    .venv/Scripts/python -m sart.tareas semanal --prueba            # con datos/prueba: el lunes de la semana
                                                                    # siguiente a la última semana completa

El día de la corrida solo importa para saber si el pronóstico está desactualizado (RF-3 E2). Los datos de
prueba terminan en 09/2026: sin ``--prueba`` o ``--fecha``, la corrida sale desactualizada y no emite alertas.
"""

from __future__ import annotations

import argparse
import sys
from datetime import date, timedelta

from sqlalchemy.orm import Session

from sart.db.alertas import alertas_por_notificar
from sart.db.sesion import SinBaseDeDatos, crear_motor
from sart.parametros import ErrorParametros
from sart.tareas.semanal import ErrorCorridaSemanal, correr_semanal
from sart.tareas.semanas_y_umbrales import marcar_semanas


def _argumentos(argv: list[str] | None) -> argparse.Namespace:
    analizador = argparse.ArgumentParser(prog="python -m sart.tareas", description="Corridas programadas.")
    tareas = analizador.add_subparsers(dest="tarea", required=True)
    semanal = tareas.add_parser("semanal", help="pronóstico, nivel y dotación (RF-2, RF-3, RF-6)")
    cuando = semanal.add_mutually_exclusive_group()
    cuando.add_argument("--fecha", type=date.fromisoformat, help="día de la corrida AAAA-MM-DD (o: hoy)")
    cuando.add_argument(
        "--prueba",
        action="store_true",
        help="datos de prueba: corre como el lunes de la semana siguiente a la última semana completa",
    )
    return analizador.parse_args(argv)


def _semanal(fecha: date | None, prueba: bool) -> int:
    try:
        motor = crear_motor()
    except SinBaseDeDatos as error:
        print(f"No se hizo la corrida semanal: {error}", file=sys.stderr)
        return 1
    try:
        with Session(motor) as sesion:
            try:
                if prueba:
                    corte = marcar_semanas(sesion)
                    if corte is None:
                        raise ErrorCorridaSemanal("No hay semanas completas: cargue datos/prueba primero.")
                    fecha = corte + timedelta(weeks=1, days=1)  # lunes de la semana pronosticada
                resumen = correr_semanal(sesion, fecha=fecha)
                pendientes = alertas_por_notificar(sesion, resumen.anio, resumen.semana)
            except (ErrorCorridaSemanal, ValueError, KeyError, ErrorParametros) as error:
                print(f"No se hizo la corrida semanal: {error}", file=sys.stderr)
                return 1
    finally:
        motor.dispose()
    print(resumen.texto())
    print(f"ALERTA por notificar (RF-5): {len(pendientes)}.")
    return 0


def main(argv: list[str] | None = None) -> int:
    args = _argumentos(argv)
    if args.tarea == "semanal":
        return _semanal(args.fecha, args.prueba)
    return 1  # pragma: no cover (argparse exige una tarea)


if __name__ == "__main__":
    sys.exit(main())
