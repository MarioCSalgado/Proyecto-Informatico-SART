"""Comandos de cuentas (RF-16) y MFA de administradores (RNF-S-1), mientras no exista la pantalla de RF-9.

Uso, desde ``backend/``::

    .venv/Scripts/python -m sart.cuentas crear --nombre "Ana Pérez" --correo ana@ejemplo.cl \\
        --rol jefatura --acepta-finalidad

La contraseña se pide por teclado (dos veces). Con ``--contrasena-stdin`` se lee de la entrada estándar; nunca
se recibe como argumento, para que no quede en el historial de la terminal.

``--acepta-finalidad`` es la constancia de RF-16: el administrador declara que el funcionario leyó y aceptó la
versión vigente del texto de §5.3. Sin esa opción no se crea la cuenta ni se guarda ningún dato (TC-16).

MFA de un administrador, en dos pasos (así se puede hacer sin una terminal interactiva)::

    .venv/Scripts/python -m sart.cuentas activar-mfa --correo admin@ejemplo.cl     # muestra la clave
    .venv/Scripts/python -m sart.cuentas confirmar-mfa --correo admin@ejemplo.cl --codigo 123456
    .venv/Scripts/python -m sart.cuentas reiniciar-mfa --correo admin@ejemplo.cl   # teléfono perdido
"""

from __future__ import annotations

import argparse
import getpass
import sys
from datetime import UTC, datetime

from sqlalchemy.orm import Session

from sart.db.cuentas import dar_de_alta
from sart.db.mfa import ErrorMfa, confirmar_activacion, iniciar_activacion, reiniciar
from sart.db.sesion import SinBaseDeDatos, crear_motor
from sart.dominio.cuentas import Aceptacion, ErrorAltaCuenta
from sart.dominio.mfa import secreto_legible
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

    activar = acciones.add_parser("activar-mfa", help="paso 1: genera la clave TOTP de un administrador")
    activar.add_argument("--correo", required=True)
    confirmar = acciones.add_parser("confirmar-mfa", help="paso 2: activa el MFA con un código")
    confirmar.add_argument("--correo", required=True)
    confirmar.add_argument("--codigo", required=True, help="código de 6 dígitos que muestra la aplicación")
    reiniciar_mfa = acciones.add_parser("reiniciar-mfa", help="borra el MFA (teléfono perdido o cambiado)")
    reiniciar_mfa.add_argument("--correo", required=True)
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


def _con_sesion(accion) -> None:
    motor = crear_motor()
    try:
        with Session(motor) as sesion:
            accion(sesion)
    finally:
        motor.dispose()


def _activar_mfa(args: argparse.Namespace) -> int:
    emisor = str(cargar_parametros()["mfa"]["emisor"])
    resultado: dict[str, str] = {}

    def accion(sesion: Session) -> None:
        resultado["secreto"], resultado["uri"] = iniciar_activacion(sesion, args.correo, emisor=emisor)

    _con_sesion(accion)
    lineas = [
        "1. En la aplicación de autenticación (Google Authenticator, Microsoft Authenticator, Authy…),",
        "   agregue una cuenta con «Ingresar clave de configuración» y escriba esta clave",
        "   (tipo: basada en tiempo):",
        "",
        f"      {secreto_legible(resultado['secreto'])}",
        "",
        f"   (o use este URI en un generador de QR local: {resultado['uri']})",
        "",
        "2. Confirme con el código de 6 dígitos que muestra la aplicación:",
        "",
        f"      python -m sart.cuentas confirmar-mfa --correo {args.correo} --codigo <código>",
        "",
        "Mientras no se confirme, la cuenta no puede iniciar sesión.",
    ]
    print("\n".join(lineas))
    return 0


def _confirmar_mfa(args: argparse.Namespace) -> int:
    tolerancia = int(cargar_parametros()["mfa"]["tolerancia_pasos"])
    _con_sesion(
        lambda sesion: confirmar_activacion(
            sesion, args.correo, args.codigo, ahora=datetime.now(UTC), tolerancia=tolerancia
        )
    )
    print(f"MFA activado para {args.correo}. Desde ahora, al iniciar sesión se pide el código.")
    return 0


def _reiniciar_mfa(args: argparse.Namespace) -> int:
    _con_sesion(lambda sesion: reiniciar(sesion, args.correo))
    print(f"MFA borrado para {args.correo}. Actívelo de nuevo con activar-mfa antes de iniciar sesión.")
    return 0


ACCIONES = {
    "crear": (_crear, "No se crea la cuenta"),
    "activar-mfa": (_activar_mfa, "No se activa el MFA"),
    "confirmar-mfa": (_confirmar_mfa, "No se activa el MFA"),
    "reiniciar-mfa": (_reiniciar_mfa, "No se reinicia el MFA"),
}


def main(argv: list[str] | None = None) -> int:
    args = _argumentos(argv)
    accion, prefijo_error = ACCIONES[args.accion]
    try:
        return accion(args)
    except (ErrorAltaCuenta, ErrorMfa, ErrorParametros, SinBaseDeDatos) as error:
        print(f"{prefijo_error}: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
