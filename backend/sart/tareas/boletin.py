"""Envío del boletín del lunes por correo (RF-8, TC-18, RNF-S-5). Corre antes de las 08:00 (T11).

Cada jefatura recibe el boletín de **sus** centros y el Subdirector el de toda la red, igual que lo que ven en
RF-7 (``centros_visibles``). Las cifras son las guardadas por la corrida semanal (``estado_de_centros``, #39);
los centros con el pronóstico desactualizado (RF-3 E2) no entran. El texto lo arma
``sart.dominio.boletin.redactar_boletin``: el LLM solo redacta y, si su texto no cuadra o no hay proveedor
(pendientes #12), sale la plantilla con las mismas cifras. El saludo con el nombre se agrega aquí, después: el
nombre nunca va al LLM.

Un boletín por usuario y semana: repetir la corrida no lo manda dos veces (queda en la auditoría, sin
nombre ni correo). El llamador hace el ``commit``.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import date, datetime
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.orm import Session

from sart.configuracion import obtener_configuracion
from sart.db.auditoria import registrar_auditoria
from sart.db.estado_centros import centros_visibles, estado_de_centros
from sart.db.modelos import Auditoria, Usuario
from sart.db.supuestos import parametros_vigentes
from sart.dominio.boletin import (
    ErrorDatosPersonales,
    FilaBoletin,
    boletin_plantilla,
    filas_desde_estado,
    redactar_boletin,
)
from sart.dominio.roles import Rol
from sart.tareas.notificaciones import Transportador, enviar_correo_smtp
from sart.tareas.seguimiento import enviar_con_reintentos

ACCION = "enviar_boletin"
FUENTES = "Fuentes: DEIS (datos abiertos, licencia CC BY-NC), SINCA y Open-Meteo."


def _clave(anio: int, semana: int, usuario: Usuario) -> str:
    return f"{anio}-SE{semana}-usuario-{usuario.id}"


def enviar_boletin(
    sesion: Session,
    *,
    hoy: date | None = None,
    redactor: Callable[[str], str] | None = None,
    url_base: str | None = None,
    transportador: Transportador = enviar_correo_smtp,
) -> dict[str, int]:
    """Manda el boletín de la semana a cada jefatura y subdirector. Devuelve los conteos de la corrida."""
    parametros = parametros_vigentes(sesion)
    hoy = hoy or datetime.now(ZoneInfo(parametros["zona_horaria"])).date()
    intentos = int(parametros["notificaciones"]["reintentos_envio"])
    base = (url_base or obtener_configuracion().sart_url_publica or "").rstrip("/")
    if not base:
        raise ValueError("Debe configurarse url_base o SART_URL_PUBLICA")

    todos = list(sesion.scalars(select(Usuario).order_by(Usuario.id)))
    cuentas = [(u.nombre, u.correo) for u in todos]  # para revisar que no vayan al LLM (RNF-S-5)
    enviados = set(sesion.scalars(select(Auditoria.entidad_id).where(Auditoria.accion == ACCION)))
    textos: dict[tuple[str, ...], tuple[str, str]] = {}  # mismos centros → mismo texto, una llamada al LLM
    resultado = {"enviados": 0, "ya_enviados": 0, "sin_pronostico": 0, "correos_fallidos": 0, "con_llm": 0}

    for usuario in todos:
        if usuario.rol not in (Rol.JEFATURA, Rol.SUBDIRECTOR):
            continue
        estados = [
            e
            for e in estado_de_centros(
                sesion, centros_visibles(sesion, usuario), hoy=hoy, parametros=parametros
            )
            if e["pronostico"] is not None and not e["pronostico"]["desactualizado"]
        ]
        anio, semana, filas = filas_desde_estado(estados)
        if not filas:
            resultado["sin_pronostico"] += 1
            continue
        clave = _clave(anio, semana, usuario)
        if clave in enviados:
            resultado["ya_enviados"] += 1
            continue

        texto, origen = _texto(textos, anio, semana, filas, redactor, cuentas)
        destino = "mi-centro" if usuario.rol is Rol.JEFATURA else "red"
        cuerpo = "\n".join(
            [
                f"Hola {usuario.nombre}:",
                "",
                texto,
                "",
                f"Detalle en SART: {base}/{destino}",
                FUENTES,
            ]
        )
        asunto = f"SART: boletín de la SE {semana} de {anio}"
        if not enviar_con_reintentos(transportador, usuario.correo, asunto, cuerpo, intentos):
            resultado["correos_fallidos"] += 1
            continue
        registrar_auditoria(
            sesion,
            autor=None,
            accion=ACCION,
            entidad="boletin",
            entidad_id=clave,
            nuevo={"origen": origen, "centros": len(filas)},
        )
        enviados.add(clave)
        resultado["enviados"] += 1
        resultado["con_llm"] += origen == "llm"

    sesion.flush()
    return resultado


def _texto(
    cache: dict[tuple[str, ...], tuple[str, str]],
    anio: int,
    semana: int,
    filas: list[FilaBoletin],
    redactor: Callable[[str], str] | None,
    cuentas: list[tuple[str, str]],
) -> tuple[str, str]:
    llave = tuple(f.centro for f in filas)
    if llave not in cache:
        try:
            cache[llave] = redactar_boletin(anio, semana, filas, redactor=redactor, cuentas=cuentas)
        except ErrorDatosPersonales:  # el texto nombraba a un usuario: no se manda al LLM, sale la plantilla
            cache[llave] = (boletin_plantilla(anio, semana, filas), "plantilla")
    return cache[llave]
