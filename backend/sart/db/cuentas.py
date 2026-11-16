"""Alta, baja, centros asignados y búsqueda de cuentas en la base (RF-9, RF-16, RNF-S-1, RNF-S-4)."""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from sart.db.auditoria import registrar_auditoria
from sart.db.modelos import AceptacionFinalidad, CentroSalud, Usuario
from sart.dominio.contrasenas import hashear
from sart.dominio.cuentas import (
    Aceptacion,
    ErrorAltaCuenta,
    normalizar_correo,
    validar_alta,
    validar_contrasena,
)
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
    centros: Iterable[CentroSalud] = (),
    autor: Usuario | None = None,
) -> Usuario:
    """Crea la cuenta, su constancia de aceptación y sus centros (RF-9) en una sola transacción (RF-16).

    El alta queda en la auditoría solo con el rol, los centros y la versión aceptada: sin nombre ni correo
    (RNF-S-4). Si falta la aceptación o algún dato es inválido, lanza ``ErrorAltaCuenta`` antes de escribir nada (TC-16).
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
    usuario.centros.extend(centros)
    sesion.add(usuario)
    try:
        sesion.flush()
        registrar_auditoria(
            sesion,
            autor=autor,
            accion="crear_cuenta",
            entidad="usuario",
            entidad_id=usuario.id,
            nuevo={
                "rol": alta.rol.value,
                "centros": _codigos(usuario),
                "version_finalidad": alta.aceptacion.version_texto,
            },
        )
        sesion.commit()
    except IntegrityError:  # otra alta con el mismo correo entró entre la búsqueda y el commit
        sesion.rollback()
        raise ErrorAltaCuenta(f"Ya existe una cuenta con el correo {alta.correo}.") from None
    return usuario


def buscar_por_correo(sesion: Session, correo: str) -> Usuario | None:
    return sesion.scalar(select(Usuario).where(Usuario.correo == normalizar_correo(correo)))


def restablecer_contrasena(
    sesion: Session,
    correo: str,
    contrasena: str,
    *,
    autor: Usuario | None = None,
    parametros: dict[str, Any] | None = None,
) -> Usuario:
    """Cambia la contraseña de una cuenta (pendientes #23). Queda en la auditoría sin la clave (RNF-S-4)."""
    usuario = buscar_por_correo(sesion, correo)
    if usuario is None:
        raise ErrorAltaCuenta(f"No existe una cuenta con el correo {correo}.")
    largo_minimo = int((parametros or cargar_parametros())["cuentas"]["largo_minimo_contrasena"])
    validar_contrasena(contrasena, largo_minimo)
    usuario.hash_contrasena = hashear(contrasena)
    registrar_auditoria(
        sesion,
        autor=autor,
        accion="restablecer_clave",
        entidad="usuario",
        entidad_id=usuario.id,
        nuevo={"contrasena": "restablecida"},
    )
    sesion.commit()
    return usuario


def _codigos(usuario: Usuario) -> list[int]:
    return sorted(c.codigo_deis for c in usuario.centros)


def buscar_centros(sesion: Session, codigos: Iterable[int]) -> list[CentroSalud]:
    """Centros por su código DEIS; si alguno no existe, ``ErrorAltaCuenta`` sin cambiar nada (RF-9)."""
    codigos = set(codigos)
    centros = list(sesion.scalars(select(CentroSalud).where(CentroSalud.codigo_deis.in_(codigos))))
    faltan = sorted(codigos - {c.codigo_deis for c in centros})
    if faltan:
        raise ErrorAltaCuenta(f"No existen los centros con código DEIS {', '.join(map(str, faltan))}.")
    return centros


def asignar_centros(
    sesion: Session, usuario: Usuario, codigos: Iterable[int], *, autor: Usuario | None = None
) -> Usuario:
    """Reemplaza los centros asignados de la cuenta (RF-9). Queda en la auditoría con los códigos antes y después."""
    centros = buscar_centros(sesion, codigos)
    anterior = _codigos(usuario)
    usuario.centros = centros
    registrar_auditoria(
        sesion,
        autor=autor,
        accion="asignar_centros",
        entidad="usuario",
        entidad_id=usuario.id,
        anterior=anterior,
        nuevo=_codigos(usuario),
    )
    sesion.commit()
    return usuario


def dar_de_baja(sesion: Session, usuario: Usuario, *, autor: Usuario | None = None) -> None:
    """RF-16 E2: borra la cuenta, su aceptación y sus centros; la auditoría conserva solo el id y el rol."""
    registrar_auditoria(
        sesion,
        autor=autor,
        accion="baja_cuenta",
        entidad="usuario",
        entidad_id=usuario.id,
        anterior={"rol": usuario.rol.value},
    )
    usuario.aceptaciones.clear()  # sin depender del ON DELETE CASCADE de la base
    sesion.delete(usuario)
    sesion.commit()
