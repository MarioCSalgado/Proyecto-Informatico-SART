"""T4 → T5 → T8: envío simulado, acuse real e historial (RF-5, RF-15, RF-10).

Recorridos de TC-06 con lectura de TC-19, usando exclusivamente SQLite en memoria.
No sustituye la validación histórica de TC-19 con datos reales del invierno de 2025.
"""

import re
import smtplib
from datetime import UTC, datetime, timedelta

import pytest
from conftest import CLAVE_DE_PRUEBA, SECRETO_DE_PRUEBA
from sqlalchemy import select
from sqlalchemy.orm import Session

from sart.api import acuse
from sart.api.tokens import NOMBRE_COOKIE, emitir_token
from sart.db.alertas import alertas_por_notificar
from sart.db.modelos import (
    Auditoria,
    CentroSalud,
    ConsultaSemanal,
    DotacionSugerida,
    Estacion,
    Notificacion,
    Pronostico,
    SemanaCarga,
    UmbralCentro,
    Usuario,
    Zona,
)
from sart.db.supuestos import parametros_vigentes
from sart.dominio.alerta_demanda import pronostico_con_margen
from sart.dominio.roles import Rol
from sart.dominio.semanas import inicio_semana
from sart.dominio.valores import EstadoNotificacion, FuenteEstacion, OrigenUmbral, TipoCentro
from sart.tareas.notificaciones import notificar_alertas
from sart.tareas.seguimiento import seguir_notificaciones
from sart.tareas.semanal import _emitir_alerta

CORREOS = {
    Rol.JEFATURA: "jefatura@sart.prueba",
    Rol.SUBDIRECTOR: "subdirector@sart.prueba",
    Rol.ADMINISTRADOR: "administrador@sart.prueba",
}
EMISION = datetime(2025, 7, 7, 9, tzinfo=UTC)
URL = "https://sart.prueba"
SIN_ACCIONES = {
    "reenviadas": 0,
    "escaladas": 0,
    "fallidas_avisadas": 0,
    "correos_fallidos": 0,
    "sin_subdirector": 0,
}


@pytest.fixture
def smtp_bloqueado(monkeypatch):
    """Impide conexiones SMTP, incluso si T4 o T5 intentaran absorber la excepción."""
    def bloquear_smtp(*args, **kwargs):
        # pytest.fail no lo absorbe el manejo de Exception de los reintentos de T4.
        pytest.fail("Conexión SMTP real bloqueada en la integración T4 → T5 → T8", pytrace=False)

    monkeypatch.setattr(smtplib, "SMTP", bloquear_smtp)
    monkeypatch.setattr(smtplib, "SMTP_SSL", bloquear_smtp)


@pytest.fixture
def demanda(motor_memoria, crear_cuenta, smtp_bloqueado):
    """Alerta persistida con centro, pronóstico y jefatura; todavía sin notificaciones."""
    usuario_id = crear_cuenta(CORREOS[Rol.JEFATURA], "jefatura")
    valor_con_margen = pronostico_con_margen(545, 590, k=0.4, nivel_intervalo=0.9)
    with Session(motor_memoria) as sesion:
        zona = Zona(nombre="Concepción")
        estacion = Estacion(
            nombre="Estación de integración", comuna="Concepción", zona=zona, fuente=FuenteEstacion.SINCA
        )
        centro = CentroSalud(
            codigo_deis=100001,
            nombre="SAR de integración",
            tipo=TipoCentro.SAR,
            comuna="Concepción",
            zona=zona,
            estacion=estacion,
        )
        usuario = sesion.get(Usuario, usuario_id)
        usuario.centros.append(centro)
        sesion.flush()
        umbral = UmbralCentro(
            centro_id=centro.id,
            umbral_atencion=400,
            umbral_alerta=500,
            origen=OrigenUmbral.CALCULADO,
        )
        sesion.add(umbral)
        sesion.flush()
        pronostico = Pronostico(
            centro_id=centro.id,
            anio=2025,
            semana=28,
            valor=545,
            limite_inferior=500,
            limite_superior=590,
            version_modelo="integracion-t4-t5-t8",
            fecha_corte=inicio_semana(2025, 27),
            vigente=True,
            nivel="alerta",
            umbral_id=umbral.id,
            k_margen=0.4,
            valor_con_margen=valor_con_margen,
            dotacion=DotacionSugerida(
                profesionales=3,
                llegadas_hora_punta=7.1,
                espera_media_min=4.2,
                espera_con_uno_menos_min=55,
                supuestos={"supuestos_validados": False},
            ),
        )
        sesion.add(pronostico)
        sesion.flush()
        alerta = _emitir_alerta(sesion, pronostico, umbral, EMISION)
        alerta_id = alerta.id
        sesion.add_all([
            SemanaCarga(anio=2025, semana=28, centros_reportados=1, completa=True),
            ConsultaSemanal(
                centro_id=centro.id, anio=2025, semana=28, causa="ira_alta", grupo_edad="1_4", cantidad=600
            ),
        ])
        sesion.commit()
    return {"usuario_id": usuario_id, "alerta_id": alerta_id, "valor_con_margen": valor_con_margen}


def test_tc06_rf10_envio_acuse_e_historial_comparten_la_misma_notificacion(
    motor_memoria, cliente, demanda, smtp_bloqueado
):
    """El token enviado confirma una sola vez y T8 lee ese mismo acuse persistido."""
    enviados = []

    def transportador_simulado(destinatario, asunto, cuerpo):
        enviados.append((destinatario, asunto, cuerpo))

    usuario_id, alerta_id = demanda["usuario_id"], demanda["alerta_id"]
    correo = CORREOS[Rol.JEFATURA]
    with Session(motor_memoria) as sesion:
        pendientes = alertas_por_notificar(sesion, 2025, 28)
        assert [pendiente.id for pendiente in pendientes] == [alerta_id]
        resultado = notificar_alertas(
            sesion, pendientes, url_base=URL, transportador=transportador_simulado
        )
        sesion.commit()

    assert resultado == {"correos_enviados": 1, "correos_fallidos": 0, "notificaciones": 1}
    [(destinatario, asunto, cuerpo)] = enviados
    assert destinatario == correo
    assert "1 alerta(s)" in asunto
    assert "Centro: SAR de integración" in cuerpo
    assert "Pronóstico de consultas: 545.00" in cuerpo
    assert "Dotación sugerida: 3 profesionales" in cuerpo
    [token] = re.findall(r"https://sart\.prueba/acuse/([A-Za-z0-9_-]+)", cuerpo)
    with Session(motor_memoria) as sesion:
        [notificacion] = sesion.scalars(select(Notificacion)).all()
        assert notificacion.token_acuse == token
        assert notificacion.alerta_id == alerta_id
        assert notificacion.usuario_id == usuario_id
        assert notificacion.estado is EstadoNotificacion.ENVIADA
        assert notificacion.fecha_confirmacion is None
        notificacion_id = notificacion.id
        fecha_envio = notificacion.fecha_envio.replace(tzinfo=UTC)

    login = cliente.post("/auth/sesion", json={"correo": correo, "contrasena": CLAVE_DE_PRUEBA})
    assert login.status_code == 200
    consulta_auditoria = select(Auditoria).where(
        Auditoria.accion == "confirmar_lectura",
        Auditoria.entidad == "notificacion",
        Auditoria.entidad_id == str(notificacion_id),
    )
    abierto = cliente.get(f"/acuse/{token}")
    assert abierto.status_code == 200
    assert abierto.json()["estado"] == "enviada"
    assert abierto.json()["fecha_confirmacion"] is None
    assert abierto.json()["alerta"]["tipo"] == "demanda"
    assert abierto.json()["alerta"]["nivel"] == "alerta"
    assert abierto.json()["alerta"]["lugar"] == "SAR de integración"
    with Session(motor_memoria) as sesion:
        notificacion = sesion.get(Notificacion, notificacion_id)
        assert notificacion.estado is EstadoNotificacion.ENVIADA
        assert notificacion.fecha_confirmacion is None
        assert sesion.scalars(consulta_auditoria).all() == []

    confirmado = cliente.post(f"/acuse/{token}/confirmar")
    assert confirmado.status_code == 200
    assert confirmado.json()["estado"] == "confirmada"
    fecha_confirmacion = datetime.fromisoformat(confirmado.json()["fecha_confirmacion"]).replace(tzinfo=UTC)
    assert fecha_confirmacion >= fecha_envio
    with Session(motor_memoria) as sesion:
        [auditoria] = sesion.scalars(consulta_auditoria).all()
        auditoria_id = auditoria.id
        assert auditoria.autor_id == usuario_id
        assert auditoria.autor_rol == "jefatura"
    historial = cliente.get("/alertas/historial")
    assert historial.status_code == 200
    [fila] = historial.json()
    assert fila["id"] == alerta_id
    assert fila["centro"]["codigo_deis"] == 100001
    assert fila["centro"]["nombre"] == "SAR de integración"
    assert datetime.fromisoformat(fila["fecha_emision"]) == EMISION
    assert fila["nivel"] == "alerta"
    assert fila["pronostico"] == {
        "anio": 2025,
        "semana": 28,
        "inicio_semana": inicio_semana(2025, 28).isoformat(),
        "fecha_corte": inicio_semana(2025, 27).isoformat(),
        "valor": 545,
        "limite_inferior": 500,
        "limite_superior": 590,
        "vigente": True,
        "umbral_alerta": 500,
        "k_margen": 0.4,
        "valor_con_margen": demanda["valor_con_margen"],
    }
    assert fila["dotacion"]["profesionales"] == 3
    assert fila["dotacion"]["espera_media_min"] == 4.2
    assert fila["dotacion"]["por_validar"] is True
    assert fila["observacion"] == {"consultas": 600, "semana_alta": True}
    assert fila["notificaciones"] == {
        "tipo": "propia",
        "estado": "confirmada",
        "fecha_confirmacion": fecha_confirmacion.isoformat().replace("+00:00", "Z"),
    }

    repetido = cliente.post(f"/acuse/{token}/confirmar")
    assert repetido.status_code == 200
    assert repetido.json() == confirmado.json()
    with Session(motor_memoria) as sesion:
        [notificacion] = sesion.scalars(select(Notificacion)).all()
        assert notificacion.id == notificacion_id
        assert notificacion.estado is EstadoNotificacion.CONFIRMADA
        assert notificacion.fecha_confirmacion.replace(tzinfo=UTC) == fecha_confirmacion
        assert notificacion.fecha_envio.replace(tzinfo=UTC) == fecha_envio
        [auditoria] = sesion.scalars(consulta_auditoria).all()
        assert auditoria.id == auditoria_id
        assert auditoria.autor_id == usuario_id
        assert auditoria.autor_rol == "jefatura"
    final = cliente.get("/alertas/historial")
    assert final.status_code == 200
    assert final.json() == historial.json()


@pytest.fixture
def envio_para_seguimiento(motor_memoria, demanda, crear_cuenta, smtp_bloqueado):
    """Envía por T4 a jefatura y subdirector; el administrador no recibe este correo."""
    usuarios = {Rol.JEFATURA: demanda["usuario_id"]}
    for rol in (Rol.SUBDIRECTOR, Rol.ADMINISTRADOR):
        usuarios[rol] = crear_cuenta(CORREOS[rol], rol.value)
    correos = []

    def transportador(destinatario, asunto, cuerpo):
        correos.append((destinatario, asunto, cuerpo))

    with Session(motor_memoria) as sesion:
        pendientes = alertas_por_notificar(sesion, 2025, 28)
        assert [alerta.id for alerta in pendientes] == [demanda["alerta_id"]]
        resultado = notificar_alertas(sesion, pendientes, url_base=URL, transportador=transportador)
        sesion.commit()
        assert resultado == {"correos_enviados": 2, "correos_fallidos": 0, "notificaciones": 2}
        notificaciones = {
            rol: sesion.scalars(select(Notificacion).where(Notificacion.usuario_id == usuario_id)).one()
            for rol, usuario_id in usuarios.items() if rol is not Rol.ADMINISTRADOR
        }
        assert len(sesion.scalars(select(Notificacion)).all()) == 2
        fecha_envio = notificaciones[Rol.JEFATURA].fecha_envio.replace(tzinfo=UTC)
        plazos = parametros_vigentes(sesion)["notificaciones"]
        assert (plazos["reenvio_horas"], plazos["escalamiento_horas"]) == (24, 48)

    assert sorted(destino for destino, _, _ in correos) == sorted(
        CORREOS[rol] for rol in (Rol.JEFATURA, Rol.SUBDIRECTOR)
    )
    for rol, notificacion in notificaciones.items():
        [cuerpo] = [cuerpo for destino, _, cuerpo in correos if destino == CORREOS[rol]]
        [token] = re.findall(r"https://sart\.prueba/acuse/([A-Za-z0-9_-]+)", cuerpo)
        assert token == notificacion.token_acuse
        assert notificacion.estado is EstadoNotificacion.ENVIADA
        assert notificacion.fecha_confirmacion is None
    return {
        **demanda,
        "usuarios": usuarios,
        "notificaciones": notificaciones,
        "fecha_envio": fecha_envio,
        "correos": correos,
        "transportador": transportador,
    }


def _entrar_como(cliente, envio, rol):
    token = emitir_token(
        usuario_id=envio["usuarios"][rol], rol=rol,
        secreto=SECRETO_DE_PRUEBA, duracion=timedelta(minutes=5),
    )
    cliente.cookies.clear()
    cliente.cookies.set(NOMBRE_COOKIE, token)


def _comprobar_historial(cliente, envio, estado, fecha_confirmacion=None):
    """Lee la API real como jefatura y como ambos roles de red, sin exponer tokens ni correos."""
    for rol in Rol.JEFATURA, Rol.SUBDIRECTOR, Rol.ADMINISTRADOR:
        _entrar_como(cliente, envio, rol)
        respuesta = cliente.get("/alertas/historial")
        assert respuesta.status_code == 200
        [fila] = respuesta.json()
        assert fila["id"] == envio["alerta_id"]
        assert fila["centro"]["codigo_deis"] == 100001
        if rol is Rol.JEFATURA:
            assert fila["notificaciones"] == {
                "tipo": "propia", "estado": estado,
                "fecha_confirmacion": fecha_confirmacion.isoformat().replace("+00:00", "Z")
                if fecha_confirmacion else None,
            }
        else:
            resumen = fila["notificaciones"]
            assert resumen["tipo"] == "resumen"
            # El aviso de escalamiento no cambia la notificación original del subdirector.
            esperado = {"enviada": 1}
            esperado[estado] = esperado.get(estado, 0) + 1
            assert {fila["estado"]: fila["total"] for fila in resumen["estados"]} == esperado
            assert len(resumen["estados"]) == len(esperado)
        for correo in CORREOS.values():
            assert correo not in respuesta.text
        for notificacion in envio["notificaciones"].values():
            assert notificacion.token_acuse not in respuesta.text


def _seguir(motor, envio, horas):
    with Session(motor) as sesion:
        resultado = seguir_notificaciones(
            sesion, ahora=envio["fecha_envio"] + timedelta(hours=horas),
            url_base=URL, transportador=envio["transportador"],
        )
        sesion.commit()
        return resultado


def _auditorias_del_acuse(motor, envio):
    with Session(motor) as sesion:
        return sesion.scalars(
            select(Auditoria).where(
                Auditoria.entidad == "notificacion",
                Auditoria.entidad_id == str(envio["notificaciones"][Rol.JEFATURA].id),
            ).order_by(Auditoria.id)
        ).all()


def test_tc06_rf10_reenvio_y_escalamiento_reales_se_reflejan_sin_duplicados(
    motor_memoria, cliente, envio_para_seguimiento
):
    """T4 → T5 → T8: reenvío a las 24 h y escalamiento a las 48 h, desde el envío original."""
    envio = envio_para_seguimiento
    _comprobar_historial(cliente, envio, "enviada")
    assert _seguir(motor_memoria, envio, 23.9) == SIN_ACCIONES
    assert len(envio["correos"]) == 2
    assert _auditorias_del_acuse(motor_memoria, envio) == []

    assert _seguir(motor_memoria, envio, 24) == {**SIN_ACCIONES, "reenviadas": 1}
    destino, asunto, cuerpo = envio["correos"][-1]
    assert destino == CORREOS[Rol.JEFATURA]
    assert "recordatorio" in asunto.lower()
    jefatura = envio["notificaciones"][Rol.JEFATURA]
    assert f"{URL}/acuse/{jefatura.token_acuse}" in cuerpo
    _comprobar_historial(cliente, envio, "reenviada")
    with Session(motor_memoria) as sesion:
        notificacion = sesion.get(Notificacion, jefatura.id)
        assert notificacion.estado is EstadoNotificacion.REENVIADA
        assert notificacion.fecha_reenvio.replace(tzinfo=UTC) == envio["fecha_envio"] + timedelta(hours=24)
        assert notificacion.fecha_envio.replace(tzinfo=UTC) == envio["fecha_envio"]
        assert notificacion.fecha_confirmacion is None
    [reenvio] = _auditorias_del_acuse(motor_memoria, envio)
    assert (reenvio.accion, reenvio.valor_anterior, reenvio.valor_nuevo) == (
        "reenviar_notificacion", "enviada", "reenviada"
    )
    correos_tras_reenvio = list(envio["correos"])
    for horas in (24, 30, 47.9):
        assert _seguir(motor_memoria, envio, horas) == SIN_ACCIONES
    assert envio["correos"] == correos_tras_reenvio
    assert [r.id for r in _auditorias_del_acuse(motor_memoria, envio)] == [reenvio.id]
    _comprobar_historial(cliente, envio, "reenviada")

    assert _seguir(motor_memoria, envio, 48) == {**SIN_ACCIONES, "escaladas": 1}
    destino, asunto, cuerpo = envio["correos"][-1]
    assert destino == CORREOS[Rol.SUBDIRECTOR]
    assert "sin confirmar" in asunto.lower()
    assert "SAR de integración" in cuerpo
    _comprobar_historial(cliente, envio, "escalada")
    auditorias = _auditorias_del_acuse(motor_memoria, envio)
    assert [r.accion for r in auditorias] == ["reenviar_notificacion", "escalar_notificacion"]
    assert (auditorias[1].valor_anterior, auditorias[1].valor_nuevo) == ("reenviada", "escalada")
    correos_tras_escalamiento = list(envio["correos"])
    for horas in (48, 72):
        assert _seguir(motor_memoria, envio, horas) == SIN_ACCIONES
    assert envio["correos"] == correos_tras_escalamiento
    assert len(envio["correos"]) == 4
    assert [r.id for r in _auditorias_del_acuse(motor_memoria, envio)] == [r.id for r in auditorias]
    with Session(motor_memoria) as sesion:
        assert len(sesion.scalars(select(Notificacion)).all()) == 2
        notificacion = sesion.get(Notificacion, jefatura.id)
        assert notificacion.estado is EstadoNotificacion.ESCALADA
        assert notificacion.fecha_reenvio.replace(tzinfo=UTC) == envio["fecha_envio"] + timedelta(hours=24)
        assert notificacion.fecha_escalamiento.replace(tzinfo=UTC) == (
            envio["fecha_envio"] + timedelta(hours=48)
        )
        assert notificacion.fecha_envio.replace(tzinfo=UTC) == envio["fecha_envio"]
        assert notificacion.fecha_confirmacion is None
        subdirector = sesion.get(Notificacion, envio["notificaciones"][Rol.SUBDIRECTOR].id)
        assert subdirector.estado is EstadoNotificacion.ENVIADA
        assert subdirector.fecha_reenvio is None and subdirector.fecha_escalamiento is None
    _comprobar_historial(cliente, envio, "escalada")


@pytest.mark.parametrize("tras_reenvio", [False, True], ids=["antes_de_24h", "entre_24_y_48h"])
def test_tc06_rf10_confirmacion_por_api_detiene_el_seguimiento_y_conserva_el_historial(
    motor_memoria, cliente, envio_para_seguimiento, monkeypatch, tras_reenvio
):
    """El acuse real de T5 detiene las acciones pendientes y T8 conserva el estado confirmado."""
    envio = envio_para_seguimiento
    if tras_reenvio:
        assert _seguir(motor_memoria, envio, 24) == {**SIN_ACCIONES, "reenviadas": 1}
        _comprobar_historial(cliente, envio, "reenviada")
    momento = envio["fecha_envio"] + timedelta(hours=47 if tras_reenvio else 23)

    class RelojAcuse(datetime):
        @classmethod
        def now(cls, tz=None):
            return momento.astimezone(tz) if tz else momento.replace(tzinfo=None)

    monkeypatch.setattr(acuse, "datetime", RelojAcuse)
    _entrar_como(cliente, envio, Rol.JEFATURA)
    jefatura = envio["notificaciones"][Rol.JEFATURA]
    respuesta = cliente.post(f"/acuse/{jefatura.token_acuse}/confirmar")
    assert respuesta.status_code == 200
    assert respuesta.json()["estado"] == "confirmada"
    assert datetime.fromisoformat(respuesta.json()["fecha_confirmacion"]).replace(tzinfo=UTC) == momento
    _comprobar_historial(cliente, envio, "confirmada", momento)
    auditorias = _auditorias_del_acuse(motor_memoria, envio)
    assert [r.accion for r in auditorias] == (
        ["reenviar_notificacion", "confirmar_lectura"] if tras_reenvio else ["confirmar_lectura"]
    )
    correos_tras_confirmacion = list(envio["correos"])
    for horas in ((48, 48, 72) if tras_reenvio else (24, 24, 48, 48, 72)):
        assert _seguir(motor_memoria, envio, horas) == SIN_ACCIONES
    assert envio["correos"] == correos_tras_confirmacion
    assert len(envio["correos"]) == (3 if tras_reenvio else 2)
    assert [r.id for r in _auditorias_del_acuse(motor_memoria, envio)] == [r.id for r in auditorias]
    with Session(motor_memoria) as sesion:
        assert len(sesion.scalars(select(Notificacion)).all()) == 2
        notificacion = sesion.get(Notificacion, jefatura.id)
        assert notificacion.estado is EstadoNotificacion.CONFIRMADA
        assert notificacion.fecha_confirmacion.replace(tzinfo=UTC) == momento
        assert notificacion.fecha_envio.replace(tzinfo=UTC) == envio["fecha_envio"]
        assert notificacion.fecha_escalamiento is None
        if tras_reenvio:
            assert notificacion.fecha_reenvio.replace(tzinfo=UTC) == (
                envio["fecha_envio"] + timedelta(hours=24)
            )
        else:
            assert notificacion.fecha_reenvio is None
    _comprobar_historial(cliente, envio, "confirmada", momento)
