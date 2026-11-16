"""Administración de cuentas y centros asignados (RF-9, RF-16, TC-09, TC-16).

Todas las rutas son solo del administrador, que siempre entra con MFA (RNF-S-1, RNF-S-2). La lógica vive en
``sart.db.cuentas`` (la misma que usa ``python -m sart.cuentas``); aquí solo el acceso y el formato. Cada cambio
queda en la auditoría sin nombre ni correo (RNF-S-4).

- ``GET /administracion/usuarios``: las cuentas con su rol y sus centros.
- ``POST /administracion/usuarios``: alta con la aceptación de la versión vigente de §5.3; sin ella, 422 y no
  se guarda nada (RF-16 E1, TC-16).
- ``PUT /administracion/usuarios/{id}/centros``: reemplaza los centros asignados (RF-9).
- ``DELETE /administracion/usuarios/{id}``: baja; borra la cuenta y sus datos de contacto (RF-16 E2).
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Response, status
from pydantic import BaseModel
from sqlalchemy import select

from sart.api.dependencias import SesionDB, requiere_rol
from sart.db.cuentas import asignar_centros, buscar_centros, dar_de_alta, dar_de_baja
from sart.db.modelos import Usuario
from sart.dominio.cuentas import Aceptacion, ErrorAltaCuenta
from sart.dominio.roles import Rol

router = APIRouter(prefix="/administracion", tags=["administracion"])

Administrador = Annotated[Usuario, Depends(requiere_rol(Rol.ADMINISTRADOR))]


class CentroAsignado(BaseModel):
    codigo_deis: int
    nombre: str


class Cuenta(BaseModel):
    id: int
    nombre: str
    correo: str
    rol: Rol
    mfa_activo: bool
    centros: list[CentroAsignado]


class AltaCuenta(BaseModel):
    nombre: str
    correo: str
    rol: Rol
    contrasena: str
    acepta_finalidad: bool  # el funcionario leyó y aceptó el texto de §5.3 (RF-16)
    version_texto: str  # versión del texto que aceptó; debe ser la vigente
    centros: list[int] = []


class CentrosDeCuenta(BaseModel):
    centros: list[int]


def _cuenta(usuario: Usuario) -> Cuenta:
    return Cuenta(
        id=usuario.id,
        nombre=usuario.nombre,
        correo=usuario.correo,
        rol=usuario.rol,
        mfa_activo=usuario.mfa_activado_en is not None,
        centros=[
            CentroAsignado(codigo_deis=c.codigo_deis, nombre=c.nombre)
            for c in sorted(usuario.centros, key=lambda c: c.codigo_deis)
        ],
    )


def _buscar(sesion: SesionDB, usuario_id: int) -> Usuario:
    usuario = sesion.get(Usuario, usuario_id)
    if usuario is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No existe esa cuenta.")
    return usuario


def _invalido(error: ErrorAltaCuenta) -> HTTPException:
    return HTTPException(422, str(error))


@router.get("/usuarios")
def listar(sesion: SesionDB, _: Administrador) -> list[Cuenta]:
    return [_cuenta(u) for u in sesion.scalars(select(Usuario).order_by(Usuario.correo))]


@router.post("/usuarios", status_code=status.HTTP_201_CREATED)
def crear(datos: AltaCuenta, sesion: SesionDB, autor: Administrador) -> Cuenta:
    aceptacion = Aceptacion(datos.version_texto, datetime.now(UTC)) if datos.acepta_finalidad else None
    try:
        usuario = dar_de_alta(
            sesion,
            nombre=datos.nombre,
            correo=datos.correo,
            rol=datos.rol,
            contrasena=datos.contrasena,
            aceptacion=aceptacion,
            centros=buscar_centros(sesion, datos.centros) if aceptacion else (),
            autor=autor,
        )
    except ErrorAltaCuenta as error:
        if str(error).startswith("Ya existe"):
            raise HTTPException(status.HTTP_409_CONFLICT, str(error)) from None
        raise _invalido(error) from None
    return _cuenta(usuario)


@router.put("/usuarios/{usuario_id}/centros")
def cambiar_centros(usuario_id: int, datos: CentrosDeCuenta, sesion: SesionDB, autor: Administrador) -> Cuenta:
    usuario = _buscar(sesion, usuario_id)
    try:
        return _cuenta(asignar_centros(sesion, usuario, datos.centros, autor=autor))
    except ErrorAltaCuenta as error:
        raise _invalido(error) from None


@router.delete("/usuarios/{usuario_id}", status_code=status.HTTP_204_NO_CONTENT)
def dar_baja(usuario_id: int, sesion: SesionDB, autor: Administrador) -> Response:
    usuario = _buscar(sesion, usuario_id)
    if usuario.id == autor.id:
        raise HTTPException(status.HTTP_409_CONFLICT, "No puede dar de baja su propia cuenta.")
    dar_de_baja(sesion, usuario, autor=autor)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
