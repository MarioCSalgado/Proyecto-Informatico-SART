"""Alta y búsqueda de cuentas en la base (RF-16, RNF-S-1)."""

from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from sart.db.modelos import AceptacionFinalidad, Usuario
from sart.dominio.contrasenas import hashear
from sart.dominio.cuentas import Aceptacion, ErrorAltaCuenta, normalizar_correo, validar_alta
from sart.dominio.roles import Rol
from sart.parametros import cargar_parametros


def dar_de_alta(
    sesion: Session,
    *,
    nombre: str,
    correo: str,
    rol: str | Rol,
    contrasena: str,
    aceptacion: Aceptacion | None,
    parametros: dict[str, Any] | None = None,
) -> Usuario:
    """Crea la cuenta y su constancia de aceptación en una sola transacción (RF-16).

    Si falta la aceptación o algún dato es inválido, lanza ``ErrorAltaCuenta`` antes de escribir nada (TC-16).
    """
    cuentas = (parametros or cargar_parametros())["cuentas"]
    alta = validar_alta(
        nombre=nombre,
        correo=correo,
        rol=rol,
        contrasena=contrasena,
        aceptacion=aceptacion,
        version_vigente=str(cuentas["version_texto_finalidad"]),
        largo_minimo=int(cuentas["largo_minimo_contrasena"]),
    )
    if buscar_por_correo(sesion, alta.correo) is not None:
        raise ErrorAltaCuenta(f"Ya existe una cuenta con el correo {alta.correo}.")

    usuario = Usuario(
        nombre=alta.nombre, correo=alta.correo, rol=alta.rol, hash_contrasena=hashear(contrasena)
    )
    usuario.aceptaciones.append(
        AceptacionFinalidad(
            version_texto=alta.aceptacion.version_texto, aceptada_en=alta.aceptacion.aceptada_en
        )
    )
    sesion.add(usuario)
    try:
        sesion.commit()
    except IntegrityError:  # otra alta con el mismo correo entró entre la búsqueda y el commit
        sesion.rollback()
        raise ErrorAltaCuenta(f"Ya existe una cuenta con el correo {alta.correo}.") from None
    return usuario


def buscar_por_correo(sesion: Session, correo: str) -> Usuario | None:
    return sesion.scalar(select(Usuario).where(Usuario.correo == normalizar_correo(correo)))
