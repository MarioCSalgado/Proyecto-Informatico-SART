"""T4 → T5 → T8: envío simulado, acuse real e historial (RF-5, RF-15, RF-10).

Recorrido principal de TC-06 con lectura de TC-19, usando exclusivamente SQLite en memoria.
No sustituye la validación histórica de TC-19 con datos reales del invierno de 2025.
"""

import re
import smtplib
from datetime import UTC, datetime

import pytest
from conftest import CLAVE_DE_PRUEBA
from sqlalchemy import select
from sqlalchemy.orm import Session

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
from sart.dominio.alerta_demanda import pronostico_con_margen
from sart.dominio.semanas import inicio_semana
from sart.dominio.valores import EstadoNotificacion, FuenteEstacion, OrigenUmbral, TipoCentro
from sart.tareas.notificaciones import notificar_alertas
from sart.tareas.semanal import _emitir_alerta


def test_tc06_rf10_envio_acuse_e_historial_comparten_la_misma_notificacion(
    motor_memoria, cliente, crear_cuenta, monkeypatch
):
    """El token enviado confirma una sola vez y T8 lee ese mismo acuse persistido."""
    def bloquear_smtp(*args, **kwargs):
        # pytest.fail no lo absorbe el manejo de Exception de los reintentos de T4.
        pytest.fail("Conexión SMTP real bloqueada en la integración T4 → T5 → T8", pytrace=False)

    monkeypatch.setattr(smtplib, "SMTP", bloquear_smtp)
    monkeypatch.setattr(smtplib, "SMTP_SSL", bloquear_smtp)
    enviados = []

    def transportador_simulado(destinatario, asunto, cuerpo):
        enviados.append((destinatario, asunto, cuerpo))

    correo = "jefatura@sart.prueba"
    usuario_id = crear_cuenta(correo, "jefatura")
    emision = datetime(2025, 7, 7, 9, tzinfo=UTC)
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
        alerta = _emitir_alerta(sesion, pronostico, umbral, emision)
        alerta_id = alerta.id
        sesion.add_all([
            SemanaCarga(anio=2025, semana=28, centros_reportados=1, completa=True),
            ConsultaSemanal(
                centro_id=centro.id, anio=2025, semana=28, causa="ira_alta", grupo_edad="1_4", cantidad=600
            ),
        ])
        pendientes = alertas_por_notificar(sesion, 2025, 28)
        assert [pendiente.id for pendiente in pendientes] == [alerta_id]
        resultado = notificar_alertas(
            sesion, pendientes, url_base="https://sart.prueba", transportador=transportador_simulado
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
    assert datetime.fromisoformat(fila["fecha_emision"]) == emision
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
        "valor_con_margen": valor_con_margen,
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
