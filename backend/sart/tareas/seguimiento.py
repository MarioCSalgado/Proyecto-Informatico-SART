"""Seguimiento de las notificaciones sin acuse (RF-15, RB-2, TC-06).

Aplica ``paso_rb2`` a cada notificación enviada a una jefatura y todavía sin confirmar:

- a las ``notificaciones.reenvio_horas`` desde la emisión original, le reenvía el correo una vez, con el mismo
  enlace de acuse, y la marca «reenviada»;
- a las ``notificaciones.escalamiento_horas``, avisa al Subdirector asistencial y la marca «escalada».

RB-2 habla de las alertas enviadas a una jefatura: la notificación del propio Subdirector no se reenvía
ni se escala. Una notificación «fallida» que ya agotó ``notificaciones.reintentos_envio`` no se reenvía
ni se escala: se avisa al administrador, una sola vez (RF-15 E2). Si un correo no sale, la notificación
no cambia de estado y se vuelve a intentar en la corrida siguiente. Todo queda en la auditoría
(RNF-S-4), sin nombres ni correos.

Pensada para correr cada hora desde el planificador (T11). El llamador hace el ``commit``.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from sart.configuracion import obtener_configuracion
from sart.db.auditoria import registrar_auditoria
from sart.db.modelos import Alerta, Auditoria, CentroSalud, Notificacion, Usuario, Zona
from sart.db.supuestos import parametros_vigentes
from sart.dominio.acuse import paso_rb2
from sart.dominio.roles import Rol
from sart.dominio.valores import EstadoNotificacion
from sart.tareas.notificaciones import Transportador, _detalle_alerta, enviar_correo_smtp

E = EstadoNotificacion
ACCION_AVISO_FALLIDA = "avisar_fallida_administrador"


def _utc(momento: datetime) -> datetime:
    """SQLite devuelve las fechas sin zona; PostgreSQL, con zona. Se comparan siempre en UTC."""
    return momento if momento.tzinfo else momento.replace(tzinfo=UTC)


def enviar_con_reintentos(
    transportador: Transportador, destino: str, asunto: str, cuerpo: str, intentos: int
) -> bool:
    """Hasta ``intentos`` veces (``notificaciones.reintentos_envio``); True si salió."""
    for _ in range(intentos):
        try:
            transportador(destino, asunto, cuerpo)
            return True
        except Exception:  # noqa: BLE001 — cualquier error del servidor de correo cuenta como intento fallido
            continue
    return False


def _lugar(sesion: Session, alerta: Alerta) -> str:
    lugar = (
        sesion.get(CentroSalud, alerta.centro_id) if alerta.centro_id else sesion.get(Zona, alerta.zona_id)
    )
    return lugar.nombre if lugar else "(sin lugar)"


def _por_rol(sesion: Session, rol: Rol) -> list[Usuario]:
    return list(sesion.scalars(select(Usuario).where(Usuario.rol == rol).order_by(Usuario.id)))


def seguir_notificaciones(
    sesion: Session,
    *,
    ahora: datetime | None = None,
    url_base: str | None = None,
    transportador: Transportador = enviar_correo_smtp,
) -> dict[str, int]:
    """Reenvía, escala y avisa de las fallidas según RB-2. Devuelve los conteos de la corrida."""
    ahora = _utc(ahora or datetime.now(UTC))
    plazos = parametros_vigentes(sesion)["notificaciones"]
    reenvio_horas = float(plazos["reenvio_horas"])
    escalamiento_horas = float(plazos["escalamiento_horas"])
    intentos = int(plazos["reintentos_envio"])
    base = (url_base or obtener_configuracion().sart_url_publica or "").rstrip("/")
    if not base:
        raise ValueError("Debe configurarse url_base o SART_URL_PUBLICA")

    resultado = {
        "reenviadas": 0,
        "escaladas": 0,
        "fallidas_avisadas": 0,
        "correos_fallidos": 0,
        "sin_subdirector": 0,
    }

    pendientes = sesion.execute(
        select(Notificacion, Usuario)
        .join(Usuario, Notificacion.usuario_id == Usuario.id)
        .where(Usuario.rol == Rol.JEFATURA, Notificacion.estado.in_([E.ENVIADA, E.REENVIADA]))
        .order_by(Notificacion.id)
    ).all()

    por_escalar: list[tuple[Notificacion, Usuario, Alerta]] = []
    for notificacion, jefatura in pendientes:
        paso = paso_rb2(
            notificacion.estado,
            _utc(notificacion.fecha_envio),
            ahora,
            reenvio_horas=reenvio_horas,
            escalamiento_horas=escalamiento_horas,
        )
        alerta = sesion.get(Alerta, notificacion.alerta_id)
        if paso == "escalar":
            por_escalar.append((notificacion, jefatura, alerta))
        elif paso == "reenviar":
            cuerpo = "\n".join(
                [
                    f"Hola {jefatura.nombre}:",
                    "",
                    f"Esta alerta de SART sigue sin confirmar desde hace {reenvio_horas:g} horas:",
                    "",
                    *_detalle_alerta(sesion, alerta),
                    f"Confirmar lectura: {base}/acuse/{notificacion.token_acuse}",
                    "",
                    f"Si no se confirma, a las {escalamiento_horas:g} horas se avisa al Subdirector"
                    " asistencial (RB-2).",
                ]
            )
            asunto = f"SART (recordatorio): alerta sin confirmar · {_lugar(sesion, alerta)}"
            if enviar_con_reintentos(transportador, jefatura.correo, asunto, cuerpo, intentos):
                notificacion.estado = E.REENVIADA
                notificacion.fecha_reenvio = ahora
                registrar_auditoria(
                    sesion,
                    autor=None,
                    accion="reenviar_notificacion",
                    entidad="notificacion",
                    entidad_id=notificacion.id,
                    anterior=E.ENVIADA.value,
                    nuevo=E.REENVIADA.value,
                )
                resultado["reenviadas"] += 1
            else:
                resultado["correos_fallidos"] += 1

    if por_escalar:
        subdirectores = _por_rol(sesion, Rol.SUBDIRECTOR)
        if not subdirectores:
            resultado["sin_subdirector"] = len(por_escalar)
        else:
            lineas = [
                "Estas alertas no tienen confirmación de lectura de la jefatura a las "
                f"{escalamiento_horas:g} horas de su emisión (RB-2):",
                "",
            ]
            for _, jefatura, alerta in por_escalar:
                lineas += [
                    f"- {_lugar(sesion, alerta)}: {alerta.tipo.value}, nivel {alerta.nivel}, emitida el "
                    f"{_utc(alerta.fecha_emision):%d/%m/%Y %H:%M} UTC. Jefatura: {jefatura.nombre}.",
                ]
            lineas += ["", f"Ver el estado de los centros: {base}/red"]
            asunto = f"SART: {len(por_escalar)} alerta(s) sin confirmar por la jefatura"
            salio = [
                enviar_con_reintentos(transportador, s.correo, asunto, "\n".join(lineas), intentos)
                for s in subdirectores
            ]
            if any(salio):
                for notificacion, _, _ in por_escalar:
                    anterior = notificacion.estado.value
                    notificacion.estado = E.ESCALADA
                    notificacion.fecha_escalamiento = ahora
                    registrar_auditoria(
                        sesion,
                        autor=None,
                        accion="escalar_notificacion",
                        entidad="notificacion",
                        entidad_id=notificacion.id,
                        anterior=anterior,
                        nuevo=E.ESCALADA.value,
                    )
                resultado["escaladas"] = len(por_escalar)
            resultado["correos_fallidos"] += salio.count(False)

    resultado["fallidas_avisadas"], fallidos = _avisar_fallidas(sesion, base, transportador, intentos)
    resultado["correos_fallidos"] += fallidos
    sesion.flush()
    return resultado


def _cuenta(sesion: Session, notificacion: Notificacion) -> str:
    usuario = sesion.get(Usuario, notificacion.usuario_id) if notificacion.usuario_id else None
    return f"{usuario.nombre} <{usuario.correo}>" if usuario else "cuenta dada de baja"


def _avisar_fallidas(
    sesion: Session, base: str, transportador: Transportador, intentos: int
) -> tuple[int, int]:
    """RF-15 E2: un correo a los administradores con las fallidas que todavía no se avisaron."""
    avisadas = set(
        sesion.scalars(select(Auditoria.entidad_id).where(Auditoria.accion == ACCION_AVISO_FALLIDA))
    )
    fallidas = [
        n
        for n in sesion.scalars(
            select(Notificacion)
            .where(Notificacion.estado == E.FALLIDA, Notificacion.intentos >= intentos)
            .order_by(Notificacion.id)
        )
        if str(n.id) not in avisadas
    ]
    administradores = _por_rol(sesion, Rol.ADMINISTRADOR)
    if not fallidas or not administradores:
        return 0, 0

    por_alerta: dict[int, list[Notificacion]] = defaultdict(list)
    for n in fallidas:
        por_alerta[n.alerta_id].append(n)
    lineas = [
        "Estos avisos de alerta no se pudieron enviar por correo (RF-5) y no se reenviarán (RF-15 E2):",
        "",
    ]
    for alerta_id, notificaciones in por_alerta.items():
        alerta = sesion.get(Alerta, alerta_id)
        cuentas = ", ".join(_cuenta(sesion, n) for n in notificaciones)
        lineas.append(f"- {_lugar(sesion, alerta)}: nivel {alerta.nivel} ({cuentas}).")
    lineas += ["", f"Revise el correo de esas cuentas en Administración: {base}/administracion"]
    asunto = f"SART: {len(fallidas)} aviso(s) de alerta sin enviar"
    salio = [
        enviar_con_reintentos(transportador, a.correo, asunto, "\n".join(lineas), intentos)
        for a in administradores
    ]
    if not any(salio):
        return 0, salio.count(False)
    for n in fallidas:
        registrar_auditoria(
            sesion, autor=None, accion=ACCION_AVISO_FALLIDA, entidad="notificacion", entidad_id=n.id
        )
    return len(fallidas), salio.count(False)
