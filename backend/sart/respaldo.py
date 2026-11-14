"""Comando de respaldo y restauración de la base (RNF-D-2, TC-14).

Uso, desde ``backend/``::

    .venv/Scripts/python -m sart.respaldo crear                          # diario, 04:30 (horarios.respaldo)
    .venv/Scripts/python -m sart.respaldo listar
    .venv/Scripts/python -m sart.respaldo restaurar ARCHIVO --confirmar  # REEMPLAZA el contenido de la base

Después de restaurar hay que volver a cargar las fuentes públicas (``python -m sart.catalogo cargar …``).
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session

from sart.configuracion import RAIZ_REPOSITORIO
from sart.db.sesion import SinBaseDeDatos, crear_motor, url_base_de_datos
from sart.parametros import ErrorParametros, cargar_parametros
from sart.tareas.corridas import registrar_corrida
from sart.tareas.respaldo import ErrorRespaldo, crear_respaldo, podar_respaldos, respaldos, restaurar_respaldo


def _argumentos(argv: list[str] | None) -> argparse.Namespace:
    analizador = argparse.ArgumentParser(prog="python -m sart.respaldo", description="Respaldo de la base.")
    acciones = analizador.add_subparsers(dest="accion", required=True)
    acciones.add_parser("crear", help="respalda la base y borra los respaldos más antiguos")
    acciones.add_parser("listar", help="muestra los respaldos guardados")
    restaurar = acciones.add_parser(
        "restaurar", help="restaura un respaldo (reemplaza el contenido de la base)"
    )
    restaurar.add_argument("archivo", type=Path)
    restaurar.add_argument("--confirmar", action="store_true", help="confirma que se reemplaza la base")
    return analizador.parse_args(argv)


def _carpeta() -> Path:
    return RAIZ_REPOSITORIO / cargar_parametros()["respaldo"]["carpeta"]


def _crear() -> int:
    parametros = cargar_parametros()["respaldo"]
    motor = crear_motor()
    try:
        with Session(motor) as sesion, registrar_corrida(sesion, "respaldo") as corrida:
            archivo = crear_respaldo(url_base_de_datos(), _carpeta(), parametros["tablas_sin_datos"])
            borrados = podar_respaldos(_carpeta(), int(parametros["conservar"]))
            corrida.mensaje = archivo.name
    finally:
        motor.dispose()
    print(f"Respaldo creado: {archivo} ({archivo.stat().st_size / 1e6:.1f} MB).")
    if borrados:
        print(f"Se borraron {len(borrados)} respaldos antiguos (se conservan {parametros['conservar']}).")
    return 0


def _listar() -> int:
    encontrados = respaldos(_carpeta())
    if not encontrados:
        print(f"No hay respaldos en {_carpeta()}.")
    for archivo in encontrados:
        print(f"{archivo.name}  {archivo.stat().st_size / 1e6:.1f} MB")
    return 0


def _restaurar(archivo: Path, confirmado: bool) -> int:
    base = make_url(url_base_de_datos()).database
    if not archivo.is_file():
        print(f"No existe el archivo {archivo}.", file=sys.stderr)
        return 1
    if not confirmado:
        print(
            f"Esto REEMPLAZA todo el contenido de la base «{base}» por el de {archivo.name}. "
            "Si está seguro, repita el comando con --confirmar.",
            file=sys.stderr,
        )
        return 2
    inicio = time.monotonic()
    restaurar_respaldo(url_base_de_datos(), archivo)
    print(
        f"Base «{base}» restaurada en {time.monotonic() - inicio:.0f} s. Falta volver a cargar las fuentes "
        "públicas: python -m sart.catalogo cargar … (TC-14: todo en 2 h o menos)."
    )
    return 0


def main(argv: list[str] | None = None) -> int:
    args = _argumentos(argv)
    try:
        if args.accion == "crear":
            return _crear()
        if args.accion == "listar":
            return _listar()
        return _restaurar(args.archivo, args.confirmar)
    except (ErrorRespaldo, ErrorParametros, SinBaseDeDatos) as error:
        print(f"No se completó: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
