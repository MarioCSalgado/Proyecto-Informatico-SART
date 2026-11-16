"""TC-06 (parte sin correo) · «Confirmar lectura» y plazos de RB-2 (RF-15).

El envío, el reenvío y el aviso al Subdirector necesitan el correo de RF-5 (tarea T4); aquí se prueba lo que no
depende de él: la página de acuse registra la confirmación solo al presionar el botón, una sola vez (RF-15 E1), y
la regla que decide a las 24 h el reenvío y a las 48 h el escalamiento. La página exige iniciar sesión y solo
el destinatario ve su notificación (pendientes #34, opción recomendada).
"""

from datetime import UTC, datetime, timedelta

import pytest
from conftest import CLAVE_DE_PRUEBA
from sqlalchemy import select
from sqlalchemy.orm import Session

from sart.db.modelos import Alerta, Auditoria, Notificacion, Zona
from sart.dominio.acuse import paso_rb2
from sart.dominio.valores import EstadoNotificacion, TipoAlerta

ENVIO = datetime(2026, 11, 16, 7, 30, tzinfo=UTC)
E = EstadoNotificacion


@pytest.fixture
def token(motor_memoria, crear_cuenta):
    usuario_id = crear_cuenta("jefa@demo.sart", "jefatura")
    crear_cuenta("otra@demo.sart", "jefatura")
    with Session(motor_memoria) as sesion:
        zona = Zona(nombre="Concepción")
        sesion.add(zona)
        sesion.flush()
        alerta = Alerta(
            tipo=TipoAlerta.AMBIENTAL, nivel="alerta", fecha_emision=ENVIO, mensaje="MP2,5 de 85 µg/m³",
            zona_id=zona.id, dia_pronosticado=ENVIO.date() + timedelta(days=1), valor_mp25=85.0,
        )
        sesion.add(alerta)
        sesion.flush()
        notificacion = Notificacion(alerta_id=alerta.id, usuario_id=usuario_id, estado=E.ENVIADA, fecha_envio=ENVIO)
        sesion.add(notificacion)
        sesion.commit()
        return notificacion.token_acuse


def _entrar(cliente, correo):
    cliente.post("/auth/sesion", json={"correo": correo, "contrasena": CLAVE_DE_PRUEBA})
    return cliente


def _notificacion(motor, token) -> Notificacion:
    with Session(motor) as sesion:
        return sesion.scalar(select(Notificacion).where(Notificacion.token_acuse == token))


def test_tc06_sin_sesion_401(cliente, token):
    assert cliente.get(f"/acuse/{token}").status_code == 401
    assert cliente.post(f"/acuse/{token}/confirmar").status_code == 401


def test_tc06_abrir_la_pagina_no_registra_el_acuse(cliente, token, motor_memoria):
    respuesta = _entrar(cliente, "jefa@demo.sart").get(f"/acuse/{token}")

    assert respuesta.status_code == 200
    assert respuesta.json()["estado"] == "enviada"
    assert respuesta.json()["alerta"]["mensaje"] == "MP2,5 de 85 µg/m³"
    assert _notificacion(motor_memoria, token).fecha_confirmacion is None


def test_tc06_confirmar_lectura_registra_fecha_y_auditoria(cliente, token, motor_memoria):
    respuesta = _entrar(cliente, "jefa@demo.sart").post(f"/acuse/{token}/confirmar")

    assert respuesta.status_code == 200
    assert respuesta.json()["estado"] == "confirmada"
    notificacion = _notificacion(motor_memoria, token)
    assert notificacion.estado is E.CONFIRMADA and notificacion.fecha_confirmacion is not None
    with Session(motor_memoria) as sesion:
        assert sesion.scalar(select(Auditoria).where(Auditoria.accion == "confirmar_lectura")) is not None


def test_rf15_e1_dos_veces_se_registra_una_sola(cliente, token, motor_memoria):
    _entrar(cliente, "jefa@demo.sart").post(f"/acuse/{token}/confirmar")
    primera = _notificacion(motor_memoria, token).fecha_confirmacion

    assert cliente.post(f"/acuse/{token}/confirmar").status_code == 200
    assert _notificacion(motor_memoria, token).fecha_confirmacion == primera
    with Session(motor_memoria) as sesion:
        assert len(sesion.scalars(select(Auditoria).where(Auditoria.accion == "confirmar_lectura")).all()) == 1


def test_tc06_otra_cuenta_o_token_inventado_404(cliente, token, motor_memoria):
    _entrar(cliente, "otra@demo.sart")

    assert cliente.get(f"/acuse/{token}").status_code == 404
    assert cliente.post(f"/acuse/{token}/confirmar").status_code == 404
    assert cliente.get("/acuse/inventado").status_code == 404
    assert _notificacion(motor_memoria, token).estado is E.ENVIADA


# ---------------------------------------------------------------------------
# RB-2: qué toca hacer con una notificación a cierta hora (plazos de parametros.yaml)
# ---------------------------------------------------------------------------
@pytest.mark.parametrize(
    ("estado", "horas", "esperado"),
    [
        (E.ENVIADA, 23.9, None),
        (E.ENVIADA, 24, "reenviar"),
        (E.REENVIADA, 47.9, None),
        (E.REENVIADA, 48, "escalar"),
        (E.ENVIADA, 50, "escalar"),  # 48 h desde la emisión original, aunque no se haya reenviado
        (E.CONFIRMADA, 50, None),
        (E.ESCALADA, 72, None),  # se escala una sola vez
        (E.FALLIDA, 50, None),  # RF-15 E2: no se reenvía ni se escala
    ],
)
def test_tc06_rb2_reenvio_24h_y_escalamiento_48h(estado, horas, esperado):
    assert paso_rb2(estado, ENVIO, ENVIO + timedelta(hours=horas), reenvio_horas=24, escalamiento_horas=48) == esperado
