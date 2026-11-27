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

from sqlalchemy import select
from sqlalchemy.orm import Session

from sart.db.alertas import alertas_por_notificar
from sart.db.modelos import Alerta
from sart.db.sesion import SinBaseDeDatos, crear_motor
from sart.parametros import ErrorParametros
from sart.tareas.ambiental import ErrorCorridaAmbiental, correr_ambiental
from sart.tareas.boletin import enviar_boletin
from sart.tareas.notificaciones import notificar_alertas
from sart.tareas.precision_pronostico import evaluar_tc12_desde_bd
from sart.tareas.seguimiento import seguir_notificaciones
from sart.tareas.semanal import ErrorCorridaSemanal, correr_semanal
from sart.tareas.semanas_y_umbrales import marcar_semanas


def _argumentos(argv: list[str] | None) -> argparse.Namespace:
    analizador = argparse.ArgumentParser(prog="python -m sart.tareas", description="Corridas programadas.")
    tareas = analizador.add_subparsers(dest="tarea", required=True)
    semanal = tareas.add_parser("semanal", help="pronóstico, nivel y dotación (RF-2, RF-3, RF-6)")
    ambiental = tareas.add_parser(
        "ambiental",
        help = "alerta ambiental diaria de MP2,5 (RF-4)"
    )
    ambiental.add_argument(
        "--fecha",
        type = date.fromisoformat,
        help = "primer día que se evaluará (AAAA-MM-DD); por defecto, mañana",
    )

    tareas.add_parser(
        "tc12",
        help="evalúa la sensibilidad del pronóstico ambiental (TC-12)",
    )
    tareas.add_parser("seguimiento", help="reenvío a las 24 h y escalamiento a las 48 h (RF-15, RB-2)")
    boletin = tareas.add_parser("boletin", help="boletín del lunes por correo (RF-8)")
    boletin.add_argument("--fecha", type=date.fromisoformat, help="día del boletín AAAA-MM-DD (o: hoy)")

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
        print(f"No se pudo completar la corrida semanal o el envío RF-5: {error}", file=sys.stderr)
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
                envio = (
                    notificar_alertas(sesion, pendientes)
                    if pendientes
                    else {"correos_enviados": 0, "correos_fallidos": 0, "notificaciones": 0}
                )
                sesion.commit()
            except (ErrorCorridaSemanal, ValueError, KeyError, ErrorParametros) as error:
                print(f"No se pudo completar la corrida semanal o el envío RF-5: {error}", file=sys.stderr)
                return 1
    finally:
        motor.dispose()
    print(resumen.texto())
    print(f"ALERTA por notificar (RF-5): {len(pendientes)}.")
    print(
        f"RF-5: {envio['correos_enviados']} correo(s) enviado(s), "
        f"{envio['correos_fallidos']} fallido(s), "
        f"{envio['notificaciones']} notificación(es) registrada(s)."
    )
    return 0

def _ambiental(fecha: date | None) -> int:
    try:
        motor = crear_motor()
    except SinBaseDeDatos as error:
        print(f"No se hizo la corrida ambiental: {error}", file = sys.stderr)
        return 1

    try:
        with Session(motor) as session:
            try:
                resumen = correr_ambiental(session, fecha = fecha)
                # RF-4/RF-5: solo las alertas evaluadas en esta corrida. T4 omite
                # las ya notificadas y conserva su límite de intentos de envío.
                alertas = list(session.scalars(
                    select(Alerta).where(Alerta.id.in_(resumen.alertas_evaluadas)).order_by(Alerta.id)
                ))
                envio = (
                    notificar_alertas(session, alertas)
                    if alertas
                    else {"correos_enviados": 0, "correos_fallidos": 0, "notificaciones": 0}
                )
                session.commit()
            except (
                ErrorCorridaAmbiental,
                ValueError,
                KeyError,
                ErrorParametros,
            ) as error:
                print(f"No se hizo la corrida ambiental: {error}", file = sys.stderr)
                return 1
    finally:
        motor.dispose()

    print(resumen.texto())
    print(
        f"RF-5: {envio['correos_enviados']} correo(s) enviado(s), "
        f"{envio['correos_fallidos']} fallido(s), "
        f"{envio['notificaciones']} notificación(es) registrada(s)."
    )
    return 0

def _tc12() -> int:
    try:
        motor = crear_motor()
    except SinBaseDeDatos as error:
        print(f"No se pudo evaluar TC-12: {error}", file=sys.stderr)
        return 1

    try:
        with Session(motor) as sesion:
            resultado = evaluar_tc12_desde_bd(
                sesion,
                zona_horaria="America/Santiago",
            )
    except (ValueError, KeyError) as error:
        print(f"No se pudo evaluar TC-12: {error}", file=sys.stderr)
        return 1
    finally:
        motor.dispose()

    print("Evaluación TC-12: sensibilidad del pronóstico ambiental")
    print(f"Días observados: {resultado.dias_evaluados}")
    print(
        "Días observados sobre 50 µg/m³: "
        f"{resultado.dias_observados_sobre_umbral}"
    )
    print(f"Días sin pronóstico válido: {resultado.dias_sin_pronostico}")
    print(f"Verdaderos positivos: {resultado.verdaderos_positivos}")
    print(f"Falsos negativos: {resultado.falsos_negativos}")

    sensibilidad = resultado.sensibilidad
    if sensibilidad is None:
        print("Sensibilidad: no calculable")
    else:
        print(f"Sensibilidad: {sensibilidad:.3f}")

    print(
        "Cumple sensibilidad ≥ 0,50: "
        f"{'SÍ' if resultado.cumple else 'NO'}"
    )

    return 0

def _con_correo(nombre: str, tarea) -> int:
    """Corre una tarea que manda correos (RF-15, RF-8), hace commit y muestra sus conteos."""
    try:
        motor = crear_motor()
    except SinBaseDeDatos as error:
        print(f"No se hizo {nombre}: {error}", file=sys.stderr)
        return 1
    try:
        with Session(motor) as sesion:
            try:
                resultado = tarea(sesion)
                sesion.commit()
            except (ValueError, KeyError, ErrorParametros) as error:
                print(f"No se hizo {nombre}: {error}", file=sys.stderr)
                return 1
    finally:
        motor.dispose()
    conteos = ", ".join(f"{clave.replace('_', ' ')} {valor}" for clave, valor in resultado.items())
    print(f"{nombre}: {conteos}")
    return 0


def main(argv: list[str] | None = None) -> int:
    args = _argumentos(argv)

    if args.tarea == "semanal":
        return _semanal(args.fecha, args.prueba)
    if args.tarea == "ambiental":
        return _ambiental(args.fecha)
    if args.tarea == "tc12":
        return _tc12()
    if args.tarea == "seguimiento":
        return _con_correo("Seguimiento RB-2", seguir_notificaciones)
    if args.tarea == "boletin":
        return _con_correo("Boletín RF-8", lambda sesion: enviar_boletin(sesion, hoy=args.fecha))

    return 1  # pragma: no cover (argparse exige una tarea)


if __name__ == "__main__":
    sys.exit(main())
