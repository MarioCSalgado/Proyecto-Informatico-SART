"""Rutas de sesión (RNF-S-1): POST /auth/sesion, GET /auth/yo y POST /auth/cerrar-sesion.

- Contraseñas con Argon2id; el JWT va en una cookie httpOnly, SameSite=Lax y Secure (salvo COOKIE_SEGURA=false
  en desarrollo).
- Correo inexistente y clave incorrecta dan el mismo 401, y tardan lo mismo (se verifica contra un hash
  ficticio), para no revelar qué correos tienen cuenta.
- Administradores: MFA con código TOTP (RNF-S-1). Con correo y clave correctos pero sin código, la respuesta
  es ``{"mfa_requerido": true}`` sin cookie; la web pide el código y reenvía todo. Sin MFA activado: 403.
  Tras ``mfa.intentos_maximos`` códigos malos, la cuenta se bloquea ``mfa.bloqueo_minutos`` (429).
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
from sart.db.mfa import ResultadoMfa, revisar_inicio
from sart.db.modelos import Usuario
from sart.dominio.contrasenas import hashear, necesita_rehash, verificar
from sart.dominio.roles import Rol
from sart.parametros import cargar_parametros

router = APIRouter(prefix="/auth", tags=["sesión"])

CREDENCIALES_INCORRECTAS = "Correo o contraseña incorrectos."
MFA_NO_ACTIVADO = (
    "Las cuentas de administrador requieren MFA (RNF-S-1) y esta todavía no lo tiene activado. "
    "Pida que se active con: python -m sart.cuentas activar-mfa"
)
CODIGO_INCORRECTO = "Código de verificación incorrecto."

# Nombres de rol tal como los usa la web (web/src/auth/permissions.ts)
ETIQUETA_ROL = {Rol.JEFATURA: "Jefatura", Rol.SUBDIRECTOR: "Subdirector", Rol.ADMINISTRADOR: "Administrador"}


class DatosInicioSesion(BaseModel):
    correo: str
    contrasena: str
    codigo: str | None = None  # código TOTP de 6 dígitos; solo administradores (RNF-S-1)


class UsuarioPublico(BaseModel):
    """Solo lo que la web necesita para mostrar la sesión; sin correo ni hash (§5.3)."""

    id: int
    nombre: str
    rol: str


class RespuestaUsuario(BaseModel):
    usuario: UsuarioPublico


class RespuestaMfaRequerido(BaseModel):
    """Clave correcta de un administrador, falta el código: no se abre sesión todavía."""

    mfa_requerido: bool = True


def _publico(usuario: Usuario) -> RespuestaUsuario:
    return RespuestaUsuario(
        usuario=UsuarioPublico(id=usuario.id, nombre=usuario.nombre, rol=ETIQUETA_ROL[usuario.rol])
    )


@lru_cache
def _hash_ficticio() -> str:
    return hashear("hash ficticio para igualar el tiempo de respuesta")


@router.post("/sesion", response_model=RespuestaUsuario | RespuestaMfaRequerido)
def iniciar_sesion(
    datos: DatosInicioSesion, respuesta: Response, sesion: SesionDB
) -> RespuestaUsuario | RespuestaMfaRequerido:
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
        resultado = revisar_inicio(sesion, usuario, datos.codigo)
        if resultado is ResultadoMfa.FALTA_CODIGO:
            return RespuestaMfaRequerido()
        if resultado is ResultadoMfa.NO_ACTIVADO:
            raise HTTPException(status.HTTP_403_FORBIDDEN, MFA_NO_ACTIVADO)
        if resultado is ResultadoMfa.BLOQUEADO:
            minutos = cargar_parametros()["mfa"]["bloqueo_minutos"]
            raise HTTPException(
                status.HTTP_429_TOO_MANY_REQUESTS,
                f"Demasiados códigos incorrectos: cuenta bloqueada {minutos} min. Intente más tarde.",
            )
        if resultado is ResultadoMfa.INCORRECTO:
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, CODIGO_INCORRECTO)

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
