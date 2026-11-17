
"""Envío de alertas por correo electrónico (RF-5)."""

from __future__ import annotations

import smtplib
from collections.abc import Callable
from datetime import UTC, datetime
from email.message import EmailMessage

from sqlalchemy import select
from sqlalchemy.orm import Session

from sart.configuracion import obtener_configuracion
from sart.db.destinatarios import destinatarios_de_alerta
from sart.db.modelos import (
    Alerta,
    CentroSalud,
    DotacionSugerida,
    Notificacion,
    Pronostico,
    Usuario,
    Zona,
)
from sart.dominio.valores import EstadoNotificacion, TipoAlerta
from sart.parametros import cargar_parametros

Transportador = Callable[[str, str, str], None]


def enviar_correo_smtp(destinatario: str, asunto: str, cuerpo: str) -> None:
    """Envía un correo mediante SMTP. Configuración mediante variables de entorno."""
    configuracion = obtener_configuracion()
    host = configuracion.smtp_host
    remitente = configuracion.smtp_from
    if not host or not remitente:
        raise ValueError("Deben configurarse SMTP_HOST y SMTP_FROM en .env")
    puerto = configuracion.smtp_port
    usuario = configuracion.smtp_user
    contrasena = configuracion.smtp_password

    mensaje = EmailMessage()
    mensaje["Subject"] = asunto
    mensaje["From"] = remitente
    mensaje["To"] = destinatario
    mensaje.set_content(cuerpo)

    with smtplib.SMTP(host, puerto, timeout=30) as servidor:
        if configuracion.smtp_starttls:
            servidor.starttls()
        if usuario and contrasena:
            servidor.login(usuario, contrasena)
        servidor.send_message(mensaje)


def _detalle_alerta(sesion: Session, alerta: Alerta) -> list[str]:
    """Construye el detalle del correo sin recalcular pronósticos ni dotaciones."""
    lineas = [
        f"Tipo: {alerta.tipo.value}",
        f"Nivel: {alerta.nivel}",
        f"Emitida: {alerta.fecha_emision.isoformat()}",
    ]

    if alerta.tipo == TipoAlerta.DEMANDA:
        pronostico = sesion.get(Pronostico, alerta.pronostico_id)
        centro = sesion.get(CentroSalud, alerta.centro_id)

        if centro:
            lineas.append(f"Centro: {centro.nombre}")

        if pronostico:
            lineas.extend([
                f"Pronóstico de consultas: {pronostico.valor:.2f}",
                (
                    "Intervalo del pronóstico: "
                    f"{pronostico.limite_inferior:.2f} – "
                    f"{pronostico.limite_superior:.2f}"
                ),
            ])

            dotacion = sesion.get(DotacionSugerida, pronostico.id)
            if dotacion:
                lineas.append(
                    f"Dotación sugerida: {dotacion.profesionales} profesionales"
                )
                lineas.append(
                    f"Espera media estimada: {dotacion.espera_media_min:.1f} minutos"
                )

    elif alerta.tipo == TipoAlerta.AMBIENTAL:
        zona = sesion.get(Zona, alerta.zona_id)
        if zona:
            lineas.append(f"Zona: {zona.nombre}")

        lineas.append(f"MP2,5: {alerta.valor_mp25} µg/m³")
        lineas.append(f"Fuente: {alerta.fuente_ambiental}")

        if alerta.dia_pronosticado:
            lineas.append(f"Día pronosticado: {alerta.dia_pronosticado}")
        if alerta.dia_observado:
            lineas.append(f"Día observado: {alerta.dia_observado}")

    return lineas


def _obtener_notificacion(
    sesion: Session,
    alerta: Alerta,
    usuario: Usuario,
) -> Notificacion | None:
    return sesion.scalar(
        select(Notificacion).where(
            Notificacion.alerta_id == alerta.id,
            Notificacion.usuario_id == usuario.id,
        )
    )


def notificar_alertas(
    sesion: Session,
    alertas: list[Alerta],
    *,
    url_base: str | None = None,
    transportador: Transportador = enviar_correo_smtp,
    max_intentos: int | None = None,
) -> dict[str, int]:
    """Agrupa alertas por usuario, envía un correo por usuario y registra cada aviso.

    Las notificaciones fallidas se pueden reintentar en una corrida posterior.
    Las que ya fueron enviadas o confirmadas no se duplican.
    El llamador es responsable de confirmar la transacción con commit().
    """
    if max_intentos is None:
        max_intentos = int(cargar_parametros()["notificaciones"]["reintentos_envio"])
    if max_intentos < 1:
        raise ValueError("notificaciones.reintentos_envio debe ser al menos 1")

    configuracion = obtener_configuracion()
    base = (url_base or configuracion.sart_url_publica or "").rstrip("/")
    if not base:
        raise ValueError("Debe configurarse url_base o SART_URL_PUBLICA")

    por_usuario: dict[int, tuple[Usuario, list[tuple[Alerta, Notificacion]]]] = {}

    for alerta in alertas:
        for usuario in destinatarios_de_alerta(sesion, alerta):
            notificacion = _obtener_notificacion(sesion, alerta, usuario)

            if notificacion is not None:
                if (
                        notificacion.estado != EstadoNotificacion.FALLIDA
                        or notificacion.intentos >= max_intentos
                ):
                    continue
            else:
                notificacion = Notificacion(
                    alerta_id=alerta.id,
                    usuario_id=usuario.id,
                    estado=EstadoNotificacion.FALLIDA,
                    fecha_envio=datetime.now(UTC),
                )
                sesion.add(notificacion)
                sesion.flush()

            if usuario.id not in por_usuario:
                por_usuario[usuario.id] = (usuario, [])

            por_usuario[usuario.id][1].append((alerta, notificacion))

    resultado = {"correos_enviados": 0, "correos_fallidos": 0, "notificaciones": 0}

    for usuario, avisos in por_usuario.values():
        resultado["notificaciones"] += len(avisos)

        lineas = [
            f"Hola {usuario.nombre}:",
            "",
            "Se han generado las siguientes alertas en SART:",
            "",
        ]

        for alerta, notificacion in avisos:
            lineas.extend(_detalle_alerta(sesion, alerta))
            lineas.extend([
                f"Acuse de recibo: {base}/acuse/{notificacion.token_acuse}",
                "",
                "-" * 45,
                "",
            ])

        asunto = f"SART: {len(avisos)} alerta(s) requieren atención"
        cuerpo = "\n".join(lineas)

        exito = False
        intentos_restantes = max(
            0,
            max_intentos - max(n.intentos for _, n in avisos),
        )

        for _ in range(intentos_restantes):
            for _, notificacion in avisos:
                notificacion.intentos += 1

            sesion.flush()

            try:
                transportador(usuario.correo, asunto, cuerpo)
                exito = True
                break
            except Exception:
                continue

        ahora = datetime.now(UTC)
        for _, notificacion in avisos:
            notificacion.fecha_envio = ahora
            notificacion.estado = (
                EstadoNotificacion.ENVIADA
                if exito
                else EstadoNotificacion.FALLIDA
            )

        if exito:
            resultado["correos_enviados"] += 1
        else:
            resultado["correos_fallidos"] += 1

    sesion.flush()
    return resultado
