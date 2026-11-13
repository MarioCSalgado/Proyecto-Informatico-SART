"""Comando para crear cuentas (RF-16) mientras no exista la pantalla de administración (RF-9).

Uso, desde ``backend/``::

    .venv/Scripts/python -m sart.cuentas crear --nombre "Ana Pérez" --correo ana@ejemplo.cl \\
        --rol jefatura --acepta-finalidad

La contraseña se pide por teclado (dos veces). Con ``--contrasena-stdin`` se lee de la entrada estándar; nunca
se recibe como argumento, para que no quede en el historial de la terminal.

``--acepta-finalidad`` es la constancia de RF-16: el administrador declara que el funcionario leyó y aceptó la
versión vigente del texto de §5.3. Sin esa opción no se crea la cuenta ni se guarda ningún dato (TC-16).
"""

from __future__ import annotations

import argparse
import getpass
import sys
from datetime import UTC, datetime

from sqlalchemy.orm import Session

from sart.db.cuentas import dar_de_alta
from sart.db.sesion import SinBaseDeDatos, crear_motor
from sart.dominio.cuentas import Aceptacion, ErrorAltaCuenta
from sart.dominio.roles import Rol
from sart.parametros import ErrorParametros, cargar_parametros


def _argumentos(argv: list[str] | None) -> argparse.Namespace:
    analizador = argparse.ArgumentParser(
        prog="python -m sart.cuentas", description="Cuentas de SART (RF-16)."
    )
    acciones = analizador.add_subparsers(dest="accion", required=True)

    crear = acciones.add_parser("crear", help="crea una cuenta con su aceptación de la finalidad (RF-16)")
    crear.add_argument("--nombre", required=True)
    crear.add_argument("--correo", required=True, help="correo institucional")
    crear.add_argument("--rol", required=True, choices=[r.value for r in Rol])
    crear.add_argument(
        "--acepta-finalidad",
        action="store_true",
        help="el funcionario aceptó la versión vigente del texto de §5.3 (obligatorio)",
    )
    crear.add_argument(
        "--contrasena-stdin", action="store_true", help="leer la contraseña de la entrada estándar"
    )
    return analizador.parse_args(argv)


def _leer_contrasena(desde_stdin: bool) -> str:
    if desde_stdin:
        return sys.stdin.readline().rstrip("\r\n")
    primera = getpass.getpass("Contraseña: ")
    if getpass.getpass("Repita la contraseña: ") != primera:
        raise ErrorAltaCuenta("Las contraseñas no coinciden.")
    return primera


def _crear(args: argparse.Namespace) -> int:
    parametros = cargar_parametros()
    version = str(parametros["cuentas"]["version_texto_finalidad"])
    aceptacion = Aceptacion(version, datetime.now(UTC)) if args.acepta_finalidad else None
    if aceptacion is None:
        # RF-16 E1: se corta antes de pedir la contraseña o abrir la base
        print(
            f"No se crea la cuenta: falta --acepta-finalidad (versión vigente del texto de §5.3: {version}).",
            file=sys.stderr,
        )
        return 2

    contrasena = _leer_contrasena(args.contrasena_stdin)
    motor = crear_motor()
    try:
        with Session(motor) as sesion:
            usuario = dar_de_alta(
                sesion,
                nombre=args.nombre,
                correo=args.correo,
                rol=args.rol,
                contrasena=contrasena,
                aceptacion=aceptacion,
                parametros=parametros,
            )
            print(
                f"Cuenta creada: id {usuario.id}, {usuario.correo}, rol {usuario.rol.value}, "
                f"finalidad v{version}."
            )
    finally:
        motor.dispose()
    return 0


def main(argv: list[str] | None = None) -> int:
    args = _argumentos(argv)
    try:
        return _crear(args)
    except (ErrorAltaCuenta, ErrorParametros, SinBaseDeDatos) as error:
        print(f"No se crea la cuenta: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
