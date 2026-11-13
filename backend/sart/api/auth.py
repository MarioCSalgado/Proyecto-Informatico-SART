"""Rutas de sesión (RNF-S-1): POST /auth/sesion, GET /auth/yo y POST /auth/cerrar-sesion.

- Contraseñas con Argon2id; el JWT va en una cookie httpOnly, SameSite=Lax y Secure (salvo COOKIE_SEGURA=false
  en desarrollo).
- Correo inexistente y clave incorrecta dan el mismo 401, y tardan lo mismo (se verifica contra un hash
  ficticio), para no revelar qué correos tienen cuenta.
- Administradores: RNF-S-1 exige MFA. Mientras no exista, no se les abre sesión (403), ver
  docs/pendientes_informe.md #16.
"""

from __future__ import annotations

from datetime import timedelta
from functools import lru_cache

from fastapi import APIRouter, HTTPException, Response, status
from pydantic import BaseModel

from sart.api.dependencias import SesionDB, UsuarioActual, secreto_jwt
from sart.api.tokens import NOMBRE_COOKIE, emitir_token
from sart.configuracion import obtener_configuracion
from sart.db.cuentas import buscar_por_correo
from sart.db.modelos import Usuario
from sart.dominio.contrasenas import hashear, necesita_rehash, verificar
from sart.dominio.roles import Rol
from sart.parametros import cargar_parametros

router = APIRouter(prefix="/auth", tags=["sesión"])

CREDENCIALES_INCORRECTAS = "Correo o contraseña incorrectos."
MFA_REQUERIDO = (
    "Las cuentas de administrador requieren MFA (RNF-S-1), que todavía no está disponible. "
    "Use una cuenta de jefatura o de subdirector."
)

# Nombres de rol tal como los usa la web (web/src/auth/permissions.ts)
ETIQUETA_ROL = {Rol.JEFATURA: "Jefatura", Rol.SUBDIRECTOR: "Subdirector", Rol.ADMINISTRADOR: "Administrador"}


class DatosInicioSesion(BaseModel):
    correo: str
    contrasena: str


class UsuarioPublico(BaseModel):
    """Solo lo que la web necesita para mostrar la sesión; sin correo ni hash (§5.3)."""

    id: int
    nombre: str
    rol: str


class RespuestaUsuario(BaseModel):
    usuario: UsuarioPublico


def _publico(usuario: Usuario) -> RespuestaUsuario:
    return RespuestaUsuario(
        usuario=UsuarioPublico(id=usuario.id, nombre=usuario.nombre, rol=ETIQUETA_ROL[usuario.rol])
    )


@lru_cache
def _hash_ficticio() -> str:
    return hashear("hash ficticio para igualar el tiempo de respuesta")


@router.post("/sesion", response_model=RespuestaUsuario)
def iniciar_sesion(datos: DatosInicioSesion, respuesta: Response, sesion: SesionDB) -> RespuestaUsuario:
    secreto = secreto_jwt()
    usuario = buscar_por_correo(sesion, datos.correo)
    if usuario is None:
        verificar(_hash_ficticio(), datos.contrasena)
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, CREDENCIALES_INCORRECTAS)
    if not verificar(usuario.hash_contrasena, datos.contrasena):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, CREDENCIALES_INCORRECTAS)
    if necesita_rehash(usuario.hash_contrasena):
        usuario.hash_contrasena = hashear(datos.contrasena)
        sesion.commit()
    if usuario.rol is Rol.ADMINISTRADOR:
        raise HTTPException(status.HTTP_403_FORBIDDEN, MFA_REQUERIDO)

    duracion = timedelta(hours=float(cargar_parametros()["sesion"]["duracion_horas"]))
    token = emitir_token(usuario_id=usuario.id, rol=usuario.rol, secreto=secreto, duracion=duracion)
    respuesta.set_cookie(
        NOMBRE_COOKIE,
        token,
        max_age=int(duracion.total_seconds()),
        httponly=True,
        samesite="lax",
        secure=obtener_configuracion().cookie_segura,
        path="/",
    )
    return _publico(usuario)


@router.get("/yo", response_model=RespuestaUsuario)
def yo(usuario: UsuarioActual) -> RespuestaUsuario:
    return _publico(usuario)


@router.post("/cerrar-sesion", status_code=status.HTTP_204_NO_CONTENT)
def cerrar_sesion() -> Response:
    respuesta = Response(status_code=status.HTTP_204_NO_CONTENT)
    respuesta.delete_cookie(
        NOMBRE_COOKIE, path="/", httponly=True, samesite="lax", secure=obtener_configuracion().cookie_segura
    )
    return respuesta
