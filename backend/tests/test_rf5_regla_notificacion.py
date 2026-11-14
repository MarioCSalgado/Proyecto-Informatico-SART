"""Qué alertas de demanda se entregan a RF-5 (RF-3 paso 4, RF-5 E2, pendientes #29, decidido el 14/11).

- Solo «ALERTA» genera notificación; «atención» se guarda y se muestra en la web (RF-7).
- Por centro y semana: cada lunes con ALERTA sale su correo, con su propio acuse y escalamiento (RB-2).
- Si se repite la corrida de la misma semana, solo se notifica si el nivel sube (atención → ALERTA).
"""

from datetime import UTC, date, datetime, timedelta

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from sart.db.alertas import alertas_por_notificar
from sart.db.modelos import ConsultaSemanal, Medicion, Notificacion, Pronostico, Usuario
from sart.db.umbrales import fijar_umbral_manual
from sart.dominio.alerta_demanda import debe_notificarse
from sart.dominio.roles import Rol
from sart.dominio.valores import EstadoNotificacion
from sart.tareas.semanal import correr_semanal
from sart.tareas.semanas_y_umbrales import recalcular_umbrales

LUNES = date(2026, 10, 5)


@pytest.mark.parametrize(
    ("nivel", "ya_notificado", "esperado"),
    [
        ("alerta", None, True),  # ALERTA nueva
        ("atencion", None, False),  # «atención» no notifica (#29)
        ("normal", None, False),
        ("alerta", "alerta", False),  # RF-5 E2: ya notificada con el mismo nivel
        ("alerta", "atencion", True),  # sube de nivel
        ("atencion", "alerta", False),  # baja: no se notifica
    ],
)
def test_debe_notificarse(nivel, ya_notificado, esperado):
    assert debe_notificarse(nivel, ya_notificado) is esperado


@pytest.fixture
def sesion(base_prueba):
    with Session(base_prueba) as sesion:
        recalcular_umbrales(sesion)
        sesion.add(Usuario(nombre="Admin", correo="a@demo.sart", rol=Rol.ADMINISTRADOR, hash_contrasena="x"))
        sesion.add(Usuario(nombre="Jefa", correo="j@demo.sart", rol=Rol.JEFATURA, hash_contrasena="x"))
        sesion.commit()
        correr_semanal(sesion, fecha=LUNES)
        yield sesion


def _pronostico(sesion, indice=0) -> Pronostico:
    return sesion.scalars(
        select(Pronostico).where(Pronostico.vigente.is_(True)).order_by(Pronostico.centro_id)
    ).all()[indice]


def _fijar(sesion, p, atencion, alerta):
    admin = sesion.scalar(select(Usuario).where(Usuario.rol == Rol.ADMINISTRADOR))
    fijar_umbral_manual(sesion, p.centro_id, atencion, alerta, autor=admin, motivo="prueba #29")


def _notificar(sesion, alerta):
    jefa = sesion.scalar(select(Usuario).where(Usuario.rol == Rol.JEFATURA))
    sesion.add(
        Notificacion(
            alerta_id=alerta.id,
            usuario_id=jefa.id,
            estado=EstadoNotificacion.ENVIADA,
            fecha_envio=datetime.now(UTC),
        )
    )
    sesion.commit()


def test_atencion_se_guarda_pero_no_se_notifica(sesion):
    p = _pronostico(sesion)
    _fijar(sesion, p, p.valor * 0.9, p.valor * 10)
    correr_semanal(sesion, fecha=LUNES)

    assert alertas_por_notificar(sesion, 2026, 40) == []


def test_alerta_nueva_se_notifica_y_repetir_la_corrida_no_la_duplica(sesion):
    p = _pronostico(sesion)
    _fijar(sesion, p, 1, 2)
    correr_semanal(sesion, fecha=LUNES)
    [alerta] = alertas_por_notificar(sesion, 2026, 40)
    assert alerta.centro_id == p.centro_id and alerta.nivel == "alerta"

    _notificar(sesion, alerta)
    correr_semanal(sesion, fecha=LUNES)  # misma semana, mismo nivel (RF-5 E2)

    assert alertas_por_notificar(sesion, 2026, 40) == []


def test_pasar_de_atencion_a_alerta_en_la_misma_semana_se_notifica(sesion):
    p = _pronostico(sesion)
    _fijar(sesion, p, p.valor * 0.9, p.valor * 10)
    correr_semanal(sesion, fecha=LUNES)  # atención (no se notifica)
    _fijar(sesion, p, 1, 2)
    correr_semanal(sesion, fecha=LUNES)  # sube a ALERTA

    [alerta] = alertas_por_notificar(sesion, 2026, 40)
    assert alerta.nivel == "alerta" and alerta.centro_id == p.centro_id


def test_una_notificacion_fallida_no_cuenta_como_notificada(sesion):
    """RF-5 E1: si el envío falló, la ALERTA sigue pendiente en la corrida siguiente."""
    p = _pronostico(sesion)
    _fijar(sesion, p, 1, 2)
    correr_semanal(sesion, fecha=LUNES)
    [alerta] = alertas_por_notificar(sesion, 2026, 40)
    jefa = sesion.scalar(select(Usuario).where(Usuario.rol == Rol.JEFATURA))
    sesion.add(
        Notificacion(
            alerta_id=alerta.id,
            usuario_id=jefa.id,
            estado=EstadoNotificacion.FALLIDA,
            fecha_envio=datetime.now(UTC),
        )
    )
    sesion.commit()
    correr_semanal(sesion, fecha=LUNES)

    assert len(alertas_por_notificar(sesion, 2026, 40)) == 1


def test_otra_semana_con_alerta_es_una_alerta_nueva(sesion):
    """Cada semana con ALERTA es una alerta nueva: lo notificado en la SE 40 no tapa la SE 41."""
    p = _pronostico(sesion)
    _fijar(sesion, p, 1, 2)
    correr_semanal(sesion, fecha=LUNES)
    [alerta] = alertas_por_notificar(sesion, 2026, 40)
    _notificar(sesion, alerta)
    # se publica la SE 40 completa (una copia de la SE 39) y corre el lunes siguiente
    for fila in sesion.scalars(
        select(ConsultaSemanal).where(ConsultaSemanal.anio == 2026, ConsultaSemanal.semana == 39)
    ).all():
        sesion.add(
            ConsultaSemanal(
                centro_id=fila.centro_id,
                anio=2026,
                semana=40,
                causa=fila.causa,
                grupo_edad=fila.grupo_edad,
                cantidad=fila.cantidad,
            )
        )
    # y sus mediciones (los datos de prueba de SINCA y Open-Meteo terminan el sábado 03/10)
    for m in sesion.scalars(
        select(Medicion).where(Medicion.fecha_hora >= datetime(2026, 9, 27, tzinfo=UTC))
    ).all():
        sesion.add(
            Medicion(
                estacion_id=m.estacion_id,
                fecha_hora=m.fecha_hora + timedelta(weeks=1),
                tipo=m.tipo,
                valor=m.valor,
                unidad=m.unidad,
                origen=m.origen,
                calidad=m.calidad,
            )
        )
    sesion.commit()
    correr_semanal(sesion, fecha=date(2026, 10, 12))

    assert alertas_por_notificar(sesion, 2026, 40) == []
    [nueva] = alertas_por_notificar(sesion, 2026, 41)
    assert nueva.centro_id == p.centro_id and nueva.id != alerta.id
