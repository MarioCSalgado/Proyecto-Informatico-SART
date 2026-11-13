"""Reglas del alta de cuentas (RF-16, §5.1, RNF-S-1, RNF-S-2). Lógica pura: no toca la base de datos.

La versión vigente del texto de §5.3 y el largo mínimo de la contraseña se reciben como argumentos; vienen de
``config/parametros.yaml`` (sección ``cuentas``, RNF-M-4).
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime

from sart.dominio.roles import Rol

# Validación de forma, no de existencia: algo@dominio.tld, sin espacios ni dos arrobas.
_FORMA_CORREO = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


class ErrorAltaCuenta(ValueError):
    """Los datos no permiten crear la cuenta. El mensaje se puede mostrar al administrador."""


class SinAceptacion(ErrorAltaCuenta):
    """RF-16 E1: el funcionario no aceptó la finalidad vigente; no se crea la cuenta ni se guarda nada."""


@dataclass(frozen=True)
class Aceptacion:
    """Constancia de que el funcionario aceptó el texto de §5.3: versión, fecha y hora (RF-16)."""

    version_texto: str
    aceptada_en: datetime


@dataclass(frozen=True)
class AltaValidada:
    """Datos de una cuenta listos para guardar (la contraseña se hashea al guardar, no aquí)."""

    nombre: str
    correo: str
    rol: Rol
    aceptacion: Aceptacion


def normalizar_correo(correo: str) -> str:
    """Correo sin espacios en los bordes y en minúsculas: el correo único (§5.1) no depende de mayúsculas."""
    return correo.strip().lower()


def validar_alta(
    *,
    nombre: str,
    correo: str,
    rol: str | Rol,
    contrasena: str,
    aceptacion: Aceptacion | None,
    version_vigente: str,
    largo_minimo: int,
) -> AltaValidada:
    """Revisa los datos de una cuenta nueva y lanza ``ErrorAltaCuenta`` con el primer problema.

    La aceptación se revisa primero (RF-16 E1, TC-16): sin ella no se sigue mirando nada.
    """
    if aceptacion is None:
        raise SinAceptacion(
            "El funcionario no ha aceptado la finalidad del tratamiento de datos (§5.3): "
            "no se crea la cuenta."
        )
    if aceptacion.version_texto != version_vigente:
        raise SinAceptacion(
            f"La aceptación es de la versión {aceptacion.version_texto} del texto, pero la vigente es la "
            f"{version_vigente}: el funcionario debe aceptar la versión vigente."
        )

    nombre = nombre.strip()
    if not nombre:
        raise ErrorAltaCuenta("El nombre es obligatorio.")

    correo = normalizar_correo(correo)
    if not _FORMA_CORREO.match(correo):
        raise ErrorAltaCuenta(f"El correo «{correo}» no es válido.")

    try:
        rol = Rol(rol)
    except ValueError:
        validos = ", ".join(r.value for r in Rol)
        raise ErrorAltaCuenta(f"El rol «{rol}» no existe; debe ser uno de: {validos}.") from None

    if len(contrasena) < largo_minimo:
        raise ErrorAltaCuenta(f"La contraseña debe tener al menos {largo_minimo} caracteres.")

    return AltaValidada(nombre=nombre, correo=correo, rol=rol, aceptacion=aceptacion)
