"""Escenario de prueba local en un paso: datos de prueba, umbrales, pronóstico de la semana y cuentas demo.

Uso, desde ``backend/`` (con la base migrada: ``alembic upgrade head``)::

    .venv/Scripts/python -m sart.demo preparar               # todo
    .venv/Scripts/python -m sart.demo preparar --solo-cuentas  # si los datos ya están cargados

Deja las mismas cuentas, clave y código MFA que se mostraron al equipo en el video del 14/11:
jefatura (centro 100001), subdirector y administrador con MFA activado, todas con ``CLAVE_DEMO``. El código
MFA ``123456`` lo da ``MFA_CODIGO_DESARROLLO`` en el ``.env`` (pendientes #49).

**Solo para entornos locales:** se niega si ``COOKIE_SEGURA`` no es ``false`` (en producción es ``true``,
RNF-S-3). Se puede repetir: no duplica cuentas ni cambia la clave de una cuenta que ya existe.
"""

from __future__ import annotations

import argparse
import sys
from datetime import UTC, datetime
from typing import Any

import pyotp
from sqlalchemy import select
from sqlalchemy.orm import Session

from sart import catalogo
from sart.configuracion import codigo_mfa_desarrollo, obtener_configuracion
from sart.db.cuentas import buscar_por_correo, dar_de_alta
from sart.db.mfa import confirmar_activacion, iniciar_activacion
from sart.db.modelos import CentroSalud
from sart.db.sesion import SinBaseDeDatos, crear_motor
from sart.dominio.cuentas import Aceptacion
from sart.dominio.roles import Rol
from sart.parametros import cargar_parametros
from sart.tareas import __main__ as tareas

# Clave de las cuentas demo: la del video del 14/11. Solo existe en bases locales de prueba (este comando se
# niega a correr con COOKIE_SEGURA=true); no es un secreto del sistema.
CLAVE_DEMO = "demo-WYDVvVkcQmq_jO4I"
CENTRO_JEFATURA = 100001
CUENTAS_DEMO = [
    ("Jefatura Capturas", "jefatura.capturas@demo.sart", Rol.JEFATURA),
    ("Subdirección Capturas", "subdirector.capturas@demo.sart", Rol.SUBDIRECTOR),
    ("Administración Demo", "admin@demo.sart", Rol.ADMINISTRADOR),
]


class ErrorDemo(RuntimeError):
    """No se puede preparar el escenario. El mensaje se puede mostrar."""


def preparar_cuentas_demo(
    sesion: Session, *, clave: str = CLAVE_DEMO, parametros: dict[str, Any] | None = None
) -> list[str]:
    """Crea las cuentas demo que falten, asigna el centro a la jefatura y activa el MFA del administrador.

    Devuelve una línea por cuenta para el resumen.
    """
    parametros = parametros or cargar_parametros()
    resumen = []
    for nombre, correo, rol in CUENTAS_DEMO:
        usuario = buscar_por_correo(sesion, correo)
        if usuario is None:
            aceptacion = Aceptacion(parametros["cuentas"]["version_texto_finalidad"], datetime.now(UTC))
            usuario = dar_de_alta(
                sesion, nombre=nombre, correo=correo, rol=rol, contrasena=clave, aceptacion=aceptacion
            )
            resumen.append(f"{correo}: creada ({rol.value})")
        else:
            resumen.append(f"{correo}: ya existía; se deja su clave como estaba")

        if rol is Rol.JEFATURA:
            centro = sesion.scalar(select(CentroSalud).where(CentroSalud.codigo_deis == CENTRO_JEFATURA))
            if centro is None:
                raise ErrorDemo(f"No existe el centro {CENTRO_JEFATURA}: primero cargue los datos de prueba.")
            if centro not in usuario.centros:
                usuario.centros.append(centro)
                sesion.commit()
        if rol is Rol.ADMINISTRADOR and usuario.mfa_activado_en is None:
            secreto, _ = iniciar_activacion(sesion, correo, emisor=parametros["mfa"]["emisor"])
            confirmar_activacion(
                sesion,
                correo,
                pyotp.TOTP(secreto).now(),
                ahora=datetime.now(UTC),
                tolerancia=int(parametros["mfa"]["tolerancia_pasos"]),
            )
    return resumen


def _argumentos(argv: list[str] | None) -> argparse.Namespace:
    analizador = argparse.ArgumentParser(prog="python -m sart.demo", description="Escenario de prueba local.")
    acciones = analizador.add_subparsers(dest="accion", required=True)
    preparar = acciones.add_parser("preparar", help="datos de prueba, pronóstico y cuentas demo")
    preparar.add_argument(
        "--solo-cuentas", action="store_true", help="no cargar datos ni correr el pronóstico"
    )
    return analizador.parse_args(argv)


def _paso(nombre: str, codigo: int) -> None:
    if codigo != 0:
        raise ErrorDemo(f"falló el paso «{nombre}» (ver el mensaje de arriba).")


def main(argv: list[str] | None = None) -> int:
    args = _argumentos(argv)
    configuracion = obtener_configuracion()
    if configuracion.cookie_segura:
        print(
            "No se prepara el escenario demo: es solo para entornos locales y COOKIE_SEGURA no es false.",
            file=sys.stderr,
        )
        return 1
    try:
        if not args.solo_cuentas:
            print("1/4 Cargando los datos de prueba (puede tardar un par de minutos)…")
            _paso("cargar datos", catalogo.main(["cargar", "--prueba"]))
            print("2/4 Calculando los umbrales de cada centro (RB-3)…")
            _paso("umbrales", catalogo.main(["recalcular-umbrales"]))
            print("3/4 Corriendo el pronóstico de la semana (RF-2, RF-3, RF-6)…")
            _paso("pronóstico", tareas.main(["semanal", "--prueba"]))
        print("4/4 Cuentas demo…")
        motor = crear_motor()
        try:
            with Session(motor) as sesion:
                resumen = preparar_cuentas_demo(sesion)
        finally:
            motor.dispose()
    except (ErrorDemo, SinBaseDeDatos) as error:
        print(f"No se completó el escenario demo: {error}", file=sys.stderr)
        return 1

    for linea in resumen:
        print(f"  {linea}")
    print(f"\nListo. Clave de las cuentas nuevas: {CLAVE_DEMO}")
    if codigo_mfa_desarrollo(configuracion):
        print(f"Código MFA del administrador: {codigo_mfa_desarrollo(configuracion)} (fijo, solo local)")
    else:
        print(
            "Para el código MFA fijo del administrador, agregue MFA_CODIGO_DESARROLLO=123456 al .env "
            "y reinicie la API."
        )
    print("Web: http://localhost:5173 (con la API en el puerto 8000 y npm run dev en web/).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
