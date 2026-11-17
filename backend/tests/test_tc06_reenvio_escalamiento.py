"""TC-06 (parte con correo) · Reenvío a las 24 h y escalamiento al Subdirector a las 48 h (RF-15, RB-2).

Completa ``test_tc06_acuse.py`` (la página de acuse y la regla ``paso_rb2``) con la tarea que la aplica
usando el correo de RF-5: un transportador de prueba reemplaza al servidor SMTP. RB-2 rige para las alertas
enviadas a una jefatura; la notificación del Subdirector no se reenvía ni se escala. Una notificación
«fallida» no se reenvía ni se escala, y se avisa al administrador una sola vez (RF-15 E2).
"""

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from sart.db.modelos import Alerta, Auditoria, CentroSalud, Estacion, Notificacion, Pronostico, Usuario, Zona
from sart.dominio.roles import Rol
from sart.dominio.valores import EstadoNotificacion, FuenteEstacion, TipoAlerta, TipoCentro
from sart.tareas.seguimiento import seguir_notificaciones

E = EstadoNotificacion
ENVIO = datetime(2026, 11, 16, 7, 30, tzinfo=UTC)
URL = "https://sart.prueba"


class Buzon:
    """Transportador de prueba: guarda (destinatario, asunto, cuerpo); puede fallar a pedido."""

    def __init__(self, fallar: bool = False) -> None:
        self.enviados: list[tuple[str, str, str]] = []
        self.fallar = fallar

    def __call__(self, destinatario: str, asunto: str, cuerpo: str) -> None:
        if self.fallar:
            raise OSError("servidor de correo caído")
        self.enviados.append((destinatario, asunto, cuerpo))

    def para(self, correo: str) -> list[tuple[str, str, str]]:
        return [e for e in self.enviados if e[0] == correo]


@pytest.fixture
def red(motor_memoria):
    """Un centro con su jefatura, un subdirector y un administrador; una ALERTA de demanda sin confirmar."""
    with Session(motor_memoria) as sesion:
        zona = Zona(nombre="Concepción")
        sesion.add(zona)
        sesion.flush()
        estacion = Estacion(
            nombre="Kingston College", comuna="Concepción", zona_id=zona.id, fuente=FuenteEstacion.SINCA
        )
        sesion.add(estacion)
        sesion.flush()
        centro = CentroSalud(
            codigo_deis=100001,
            nombre="SAPU Lorenzo Arenas",
            tipo=TipoCentro.SAPU,
            comuna="Concepción",
            zona_id=zona.id,
            estacion_id=estacion.id,
        )
        jefa = Usuario(
            nombre="Jefa Lorenzo Arenas",
            correo="jefa@sart.prueba",
            rol=Rol.JEFATURA,
            hash_contrasena="x",
            centros=[centro],
        )
        sub = Usuario(
            nombre="Subdirector", correo="sub@sart.prueba", rol=Rol.SUBDIRECTOR, hash_contrasena="x"
        )
        admin = Usuario(
            nombre="Admin", correo="admin@sart.prueba", rol=Rol.ADMINISTRADOR, hash_contrasena="x"
        )
        sesion.add_all([centro, jefa, sub, admin])
        sesion.flush()
        pronostico = Pronostico(
            centro_id=centro.id,
            anio=2026,
            semana=47,
            valor=420.0,
            limite_inferior=380.0,
            limite_superior=470.0,
            version_modelo="prueba",
            fecha_corte=ENVIO.date(),
            vigente=True,
        )
        sesion.add(pronostico)
        sesion.flush()
        alerta = Alerta(
            tipo=TipoAlerta.DEMANDA,
            nivel="alerta",
            fecha_emision=ENVIO,
            mensaje="ALERTA de demanda",
            centro_id=centro.id,
            pronostico_id=pronostico.id,
        )
        sesion.add(alerta)
        sesion.flush()
        sesion.add_all(
            [
                Notificacion(
                    alerta_id=alerta.id, usuario_id=jefa.id, estado=E.ENVIADA, fecha_envio=ENVIO, intentos=1
                ),
                Notificacion(
                    alerta_id=alerta.id, usuario_id=sub.id, estado=E.ENVIADA, fecha_envio=ENVIO, intentos=1
                ),
            ]
        )
        sesion.commit()
    return motor_memoria


def _correr(motor, horas: float, buzon: Buzon) -> dict[str, int]:
    with Session(motor) as sesion:
        resultado = seguir_notificaciones(
            sesion, ahora=ENVIO + timedelta(hours=horas), url_base=URL, transportador=buzon
        )
        sesion.commit()
    return resultado


def _de(motor, correo: str) -> Notificacion:
    with Session(motor) as sesion:
        return sesion.scalar(
            select(Notificacion)
            .join(Usuario, Notificacion.usuario_id == Usuario.id)
            .where(Usuario.correo == correo)
        )


def _acciones(motor) -> list[str]:
    with Session(motor) as sesion:
        return list(sesion.scalars(select(Auditoria.accion).order_by(Auditoria.id)))


def test_tc06_antes_de_24_horas_no_pasa_nada(red):
    buzon = Buzon()
    _correr(red, 23.9, buzon)
    assert buzon.enviados == []
    assert _de(red, "jefa@sart.prueba").estado is E.ENVIADA


def test_tc06_a_las_24_horas_se_reenvia_una_vez_a_la_jefatura(red):
    buzon = Buzon()
    resultado = _correr(red, 24, buzon)

    assert resultado["reenviadas"] == 1
    [(destino, asunto, cuerpo)] = buzon.enviados  # ni el Subdirector ni el administrador reciben nada
    assert destino == "jefa@sart.prueba"
    assert "recordatorio" in asunto.lower()
    jefa = _de(red, "jefa@sart.prueba")
    assert f"{URL}/acuse/{jefa.token_acuse}" in cuerpo  # el mismo enlace de acuse de RF-5
    assert jefa.estado is E.REENVIADA
    assert jefa.fecha_reenvio is not None
    assert jefa.fecha_envio.replace(tzinfo=UTC) == ENVIO  # los plazos se cuentan desde la emisión original
    assert "reenviar_notificacion" in _acciones(red)

    _correr(red, 30, buzon)  # repetir la tarea no reenvía de nuevo
    assert len(buzon.enviados) == 1


def test_tc06_gherkin_escalamiento_sin_confirmacion(red):
    """Dado que la jefatura no confirmó la lectura en 48 horas, cuando se cumple el plazo, entonces el
    Subdirector asistencial recibe el aviso y el escalamiento queda registrado con fecha y hora."""
    buzon = Buzon()
    _correr(red, 24, buzon)
    resultado = _correr(red, 48, buzon)

    assert resultado["escaladas"] == 1
    [(_, asunto, cuerpo)] = buzon.para("sub@sart.prueba")
    assert "sin confirmar" in asunto.lower()
    assert "SAPU Lorenzo Arenas" in cuerpo
    jefa = _de(red, "jefa@sart.prueba")
    assert jefa.estado is E.ESCALADA
    assert jefa.fecha_escalamiento.replace(tzinfo=UTC) == ENVIO + timedelta(hours=48)
    assert _acciones(red).count("escalar_notificacion") == 1

    _correr(red, 72, buzon)  # una sola vez
    assert len(buzon.para("sub@sart.prueba")) == 1


def test_tc06_si_la_tarea_no_corrio_a_las_24_horas_escala_igual_a_las_48(red):
    buzon = Buzon()
    _correr(red, 50, buzon)
    assert _de(red, "jefa@sart.prueba").estado is E.ESCALADA
    assert len(buzon.para("sub@sart.prueba")) == 1


def test_tc06_confirmada_no_se_reenvia_ni_se_escala(red):
    with Session(red) as sesion:
        jefa = sesion.scalar(select(Notificacion).join(Usuario).where(Usuario.correo == "jefa@sart.prueba"))
        jefa.estado = E.CONFIRMADA
        jefa.fecha_confirmacion = ENVIO + timedelta(hours=2)
        sesion.commit()
    buzon = Buzon()
    _correr(red, 24, buzon)
    _correr(red, 48, buzon)
    assert buzon.enviados == []


def test_tc06_la_notificacion_del_subdirector_no_se_escala(red):
    buzon = Buzon()
    _correr(red, 48, buzon)
    assert _de(red, "sub@sart.prueba").estado is E.ENVIADA


def test_tc06_si_el_correo_falla_se_intenta_en_la_corrida_siguiente(red):
    _correr(red, 24, Buzon(fallar=True))
    assert _de(red, "jefa@sart.prueba").estado is E.ENVIADA
    buzon = Buzon()
    _correr(red, 25, buzon)
    assert _de(red, "jefa@sart.prueba").estado is E.REENVIADA
    assert len(buzon.enviados) == 1


def test_tc06_e2_fallida_no_se_reenvia_y_se_avisa_al_administrador_una_vez(red):
    with Session(red) as sesion:
        jefa = sesion.scalar(select(Notificacion).join(Usuario).where(Usuario.correo == "jefa@sart.prueba"))
        jefa.estado = E.FALLIDA
        jefa.intentos = 3  # notificaciones.reintentos_envio agotados en RF-5
        sesion.commit()
    buzon = Buzon()
    resultado = _correr(red, 48, buzon)

    assert resultado["fallidas_avisadas"] == 1
    [(destino, _, cuerpo)] = [e for e in buzon.enviados if e[0] != "sub@sart.prueba"]
    assert destino == "admin@sart.prueba"
    assert "SAPU Lorenzo Arenas" in cuerpo
    assert _de(red, "jefa@sart.prueba").estado is E.FALLIDA
    assert buzon.para("sub@sart.prueba") == []  # no se escala

    _correr(red, 72, buzon)
    assert len(buzon.para("admin@sart.prueba")) == 1


def test_tc06_sin_subdirector_no_se_marca_escalada(red):
    with Session(red) as sesion:
        sesion.delete(sesion.scalar(select(Usuario).where(Usuario.correo == "sub@sart.prueba")))
        sesion.commit()
    resultado = _correr(red, 48, Buzon())
    assert resultado["sin_subdirector"] == 1
    assert _de(red, "jefa@sart.prueba").estado is E.ENVIADA  # queda pendiente para la próxima corrida
