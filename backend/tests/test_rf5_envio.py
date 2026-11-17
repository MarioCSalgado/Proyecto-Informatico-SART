from datetime import UTC, date, datetime

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from sart.db.destinatarios import destinatarios_de_alerta
from sart.db.modelos import (
    Alerta,
    CentroSalud,
    Estacion,
    Pronostico,
    Usuario,
    Zona,
)
from sart.dominio.roles import Rol
from sart.dominio.valores import (
    FuenteEstacion,
    TipoAlerta,
    TipoCentro,
)


def _crear_pronostico(sesion, centro):
    pronostico = Pronostico(
        centro_id=centro.id,
        anio=2026,
        semana=47,
        valor=10.0,
        limite_inferior=8.0,
        limite_superior=12.0,
        version_modelo="prueba",
        fecha_corte=date.today(),
        vigente=True,
    )
    sesion.add(pronostico)
    sesion.flush()
    return pronostico

def _crear_estructura(sesion):
    zona_a = Zona(nombre="Zona A")
    zona_b = Zona(nombre="Zona B")
    sesion.add_all([zona_a, zona_b])
    sesion.flush()

    estacion_a = Estacion(
        nombre="Estación A",
        comuna="Comuna A",
        zona_id=zona_a.id,
        fuente=FuenteEstacion.SINCA,
    )
    estacion_b = Estacion(
        nombre="Estación B",
        comuna="Comuna B",
        zona_id=zona_b.id,
        fuente=FuenteEstacion.SINCA,
    )
    sesion.add_all([estacion_a, estacion_b])
    sesion.flush()

    centro_a = CentroSalud(
        codigo_deis=1001,
        nombre="Centro A",
        tipo=TipoCentro.HOSPITAL,
        comuna="Comuna A",
        zona_id=zona_a.id,
        estacion_id=estacion_a.id,
    )
    centro_b = CentroSalud(
        codigo_deis=1002,
        nombre="Centro B",
        tipo=TipoCentro.HOSPITAL,
        comuna="Comuna B",
        zona_id=zona_b.id,
        estacion_id=estacion_b.id,
    )

    jefatura_a = Usuario(
        nombre="Jefatura A",
        correo="jefatura.a@test.cl",
        rol=Rol.JEFATURA,
        hash_contrasena="hash",
        centros=[centro_a],
    )
    jefatura_b = Usuario(
        nombre="Jefatura B",
        correo="jefatura.b@test.cl",
        rol=Rol.JEFATURA,
        hash_contrasena="hash",
        centros=[centro_b],
    )
    subdirector = Usuario(
        nombre="Subdirector",
        correo="subdirector@test.cl",
        rol=Rol.SUBDIRECTOR,
        hash_contrasena="hash",
    )
    administrador = Usuario(
        nombre="Administrador",
        correo="admin@test.cl",
        rol=Rol.ADMINISTRADOR,
        hash_contrasena="hash",
    )

    sesion.add_all([
        centro_a, centro_b, jefatura_a, jefatura_b,
        subdirector, administrador,
    ])
    sesion.flush()

    return zona_a, zona_b, centro_a, centro_b, jefatura_a, jefatura_b, subdirector


def test_destinatarios_demanda_solo_centro_asignado(motor_memoria):
    with Session(motor_memoria) as sesion:
        _, _, centro_a, _, jefatura_a, _, subdirector = _crear_estructura(sesion)

        pronostico = _crear_pronostico(sesion, centro_a)

        alerta = Alerta(
            tipo=TipoAlerta.DEMANDA,
            nivel="alerta",
            fecha_emision=datetime.now(UTC),
            mensaje="Alerta de demanda",
            centro_id=centro_a.id,
            pronostico_id=pronostico.id,
        )
        sesion.add(alerta)
        sesion.flush()

        destinatarios = destinatarios_de_alerta(sesion, alerta)

        assert {u.id for u in destinatarios} == {
            jefatura_a.id,
            subdirector.id,
        }


def test_destinatarios_ambiental_por_zona(motor_memoria):
    with Session(motor_memoria) as sesion:
        zona_a, _, _, _, jefatura_a, _, subdirector = _crear_estructura(sesion)

        alerta = Alerta(
            tipo=TipoAlerta.AMBIENTAL,
            nivel="alerta",
            fecha_emision=datetime.now(UTC),
            mensaje="Alerta ambiental",
            zona_id=zona_a.id,
            fuente_ambiental="sinca",
            valor_mp25=30.0,
            dia_observado=date.today(),
        )
        sesion.add(alerta)
        sesion.flush()

        destinatarios = destinatarios_de_alerta(sesion, alerta)

        assert {u.id for u in destinatarios} == {
            jefatura_a.id,
            subdirector.id,
        }


def test_administrador_no_recibe_alertas(motor_memoria):
    with Session(motor_memoria) as sesion:
        _, _, centro_a, _, _, _, subdirector = _crear_estructura(sesion)

        pronostico = _crear_pronostico(sesion, centro_a)

        alerta = Alerta(
            tipo=TipoAlerta.DEMANDA,
            nivel="alerta",
            fecha_emision=datetime.now(UTC),
            mensaje="Alerta de demanda",
            centro_id=centro_a.id,
            pronostico_id=pronostico.id,
        )
        sesion.add(alerta)
        sesion.flush()

        destinatarios = destinatarios_de_alerta(sesion, alerta)

        assert all(u.rol != Rol.ADMINISTRADOR for u in destinatarios)
        assert subdirector.id in {u.id for u in destinatarios}


def test_envio_exitoso_registra_notificacion(motor_memoria):
    from datetime import UTC, datetime

    from sart.db.modelos import Notificacion
    from sart.dominio.valores import EstadoNotificacion
    from sart.tareas.notificaciones import notificar_alertas

    correos = []

    def transporte(destinatario, asunto, cuerpo):
        correos.append((destinatario, asunto, cuerpo))

    with Session(motor_memoria) as sesion:
        _, _, centro_a, _, jefatura_a, _, _ = _crear_estructura(sesion)
        pronostico = _crear_pronostico(sesion, centro_a)

        alerta = Alerta(
            tipo=TipoAlerta.DEMANDA,
            nivel="alerta",
            fecha_emision=datetime.now(UTC),
            mensaje="Alerta de prueba",
            centro_id=centro_a.id,
            pronostico_id=pronostico.id,
        )
        sesion.add(alerta)
        sesion.flush()

        resultado = notificar_alertas(
            sesion,
            [alerta],
            url_base="http://localhost:8000",
            transportador=transporte,
        )
        sesion.flush()

        notificacion = sesion.scalar(
            select(Notificacion).where(
                Notificacion.alerta_id == alerta.id,
                Notificacion.usuario_id == jefatura_a.id,
            )
        )

        assert resultado["correos_enviados"] == 2
        assert resultado["correos_fallidos"] == 0
        assert notificacion.estado == EstadoNotificacion.ENVIADA
        assert notificacion.token_acuse in correos[0][2] or any(
            notificacion.token_acuse in correo[2] for correo in correos
        )


def test_envio_fallido_realiza_tres_intentos(motor_memoria):
    from datetime import UTC, datetime

    from sart.db.modelos import Notificacion
    from sart.dominio.valores import EstadoNotificacion
    from sart.tareas.notificaciones import notificar_alertas

    intentos = []

    def transporte(destinatario, asunto, cuerpo):
        intentos.append(destinatario)
        raise RuntimeError("SMTP no disponible")

    with Session(motor_memoria) as sesion:
        _, _, centro_a, _, jefatura_a, _, _ = _crear_estructura(sesion)
        pronostico = _crear_pronostico(sesion, centro_a)

        alerta = Alerta(
            tipo=TipoAlerta.DEMANDA,
            nivel="alerta",
            fecha_emision=datetime.now(UTC),
            mensaje="Alerta de prueba",
            centro_id=centro_a.id,
            pronostico_id=pronostico.id,
        )
        sesion.add(alerta)
        sesion.flush()

        resultado = notificar_alertas(
            sesion,
            [alerta],
            url_base="http://localhost:8000",
            transportador=transporte,
        )
        sesion.flush()

        notificacion = sesion.scalar(
            select(Notificacion).where(
                Notificacion.alerta_id == alerta.id,
                Notificacion.usuario_id == jefatura_a.id,
            )
        )

        assert len(intentos) == 6
        assert intentos.count("jefatura.a@test.cl") == 3
        assert intentos.count("subdirector@test.cl") == 3
        assert resultado["correos_fallidos"] == 2
        assert notificacion.estado == EstadoNotificacion.FALLIDA



def test_repetir_envio_no_duplica_correo_ni_incluye_datos_de_pacientes(motor_memoria):
    from sart.db.modelos import Notificacion
    from sart.tareas.notificaciones import notificar_alertas

    correos = []

    def transporte(destinatario, asunto, cuerpo):
        correos.append((destinatario, asunto, cuerpo))

    with Session(motor_memoria) as sesion:
        _, _, centro_a, _, _, _, _ = _crear_estructura(sesion)
        pronostico = _crear_pronostico(sesion, centro_a)
        alerta = Alerta(
            tipo=TipoAlerta.DEMANDA,
            nivel="alerta",
            fecha_emision=datetime.now(UTC),
            mensaje="Paciente: PACIENTE-PRUEBA; RUT: 11.111.111-1",
            centro_id=centro_a.id,
            pronostico_id=pronostico.id,
        )
        sesion.add(alerta)
        sesion.flush()

        primer_envio = notificar_alertas(
            sesion, [alerta], url_base="http://localhost:8000", transportador=transporte
        )
        sesion.commit()

        segundo_envio = notificar_alertas(
            sesion, [alerta], url_base="http://localhost:8000", transportador=transporte
        )
        sesion.commit()

        assert primer_envio["correos_enviados"] == 2
        assert segundo_envio["correos_enviados"] == 0
        assert len(correos) == 2
        assert sesion.query(Notificacion).count() == 2
        for _, _, cuerpo in correos:
            assert "PACIENTE-PRUEBA" not in cuerpo
            assert "RUT:" not in cuerpo
            assert "Ficha clínica" not in cuerpo


def test_reintentos_usan_parametro_yaml(motor_memoria, monkeypatch):
    import sart.tareas.notificaciones as modulo

    monkeypatch.setattr(
        modulo,
        "cargar_parametros",
        lambda: {"notificaciones": {"reintentos_envio": 2}},
    )
    intentos = []

    def transporte(destinatario, asunto, cuerpo):
        intentos.append(destinatario)
        raise RuntimeError("SMTP no disponible")

    with Session(motor_memoria) as sesion:
        _, _, centro_a, _, _, _, _ = _crear_estructura(sesion)
        pronostico = _crear_pronostico(sesion, centro_a)
        alerta = Alerta(
            tipo=TipoAlerta.DEMANDA,
            nivel="alerta",
            fecha_emision=datetime.now(UTC),
            mensaje="Paciente: PACIENTE-PRUEBA; RUT: 11.111.111-1",
            centro_id=centro_a.id,
            pronostico_id=pronostico.id,
        )
        sesion.add(alerta)
        sesion.flush()

        resultado = modulo.notificar_alertas(
            sesion, [alerta], url_base="http://localhost:8000", transportador=transporte
        )

        assert len(intentos) == 4
        assert intentos.count("jefatura.a@test.cl") == 2
        assert intentos.count("subdirector@test.cl") == 2
        assert resultado["correos_fallidos"] == 2


def test_transporte_smtp_lee_credenciales_desde_entorno(monkeypatch):
    import sart.tareas.notificaciones as modulo

    enviados = {}

    class SMTPFalso:
        def __init__(self, host, puerto, timeout):
            enviados["conexion"] = (host, puerto, timeout)

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def starttls(self):
            enviados["tls"] = True

        def login(self, usuario, contrasena):
            enviados["login"] = (usuario, contrasena)

        def send_message(self, mensaje):
            enviados["mensaje"] = mensaje

    monkeypatch.setenv("SMTP_HOST", "smtp.test.local")
    monkeypatch.setenv("SMTP_PORT", "2525")
    monkeypatch.setenv("SMTP_FROM", "sart@test.local")
    monkeypatch.setenv("SMTP_USER", "usuario-test")
    monkeypatch.setenv("SMTP_PASSWORD", "clave-test")
    monkeypatch.setenv("SMTP_STARTTLS", "true")
    monkeypatch.setattr(modulo.smtplib, "SMTP", SMTPFalso)

    modulo.enviar_correo_smtp("destino@test.local", "Asunto de prueba", "Cuerpo de prueba")

    assert enviados["conexion"] == ("smtp.test.local", 2525, 30)
    assert enviados["tls"] is True
    assert enviados["login"] == ("usuario-test", "clave-test")
    assert enviados["mensaje"]["To"] == "destino@test.local"
    assert enviados["mensaje"]["From"] == "sart@test.local"



@pytest.mark.integracion
def test_smtp_mailpit_de_prueba(monkeypatch):
    import os
    import uuid

    host = os.getenv("SMTP_TEST_HOST")
    if not host:
        pytest.skip("Configure SMTP_TEST_HOST para probar contra Mailpit")
    from sart.tareas.notificaciones import enviar_correo_smtp

    monkeypatch.setenv("SMTP_HOST", host)
    monkeypatch.setenv("SMTP_PORT", os.getenv("SMTP_TEST_PORT", "1025"))
    monkeypatch.setenv("SMTP_FROM", "sart@localhost")
    monkeypatch.setenv("SMTP_USER", "")
    monkeypatch.setenv("SMTP_PASSWORD", "")
    monkeypatch.setenv("SMTP_STARTTLS", "false")
    destinatario = os.getenv("SMTP_TEST_TO", "test@localhost")
    asunto = f"SART prueba SMTP {uuid.uuid4()}"
    enviar_correo_smtp(destinatario, asunto, "Correo de prueba RF-5, sin datos de pacientes.")



def test_un_correo_por_usuario_solo_con_sus_centros(motor_memoria):
    from sart.tareas.notificaciones import notificar_alertas

    correos = []

    def transporte(destinatario, asunto, cuerpo):
        correos.append((destinatario, cuerpo))

    with Session(motor_memoria) as sesion:
        _, _, centro_a, centro_b, _, _, _ = _crear_estructura(sesion)
        pronostico_a = _crear_pronostico(sesion, centro_a)
        pronostico_b = _crear_pronostico(sesion, centro_b)
        alertas = [
            Alerta(
                tipo=TipoAlerta.DEMANDA,
                nivel="alerta",
                fecha_emision=datetime.now(UTC),
                mensaje="No enviar texto libre",
                centro_id=centro.id,
                pronostico_id=pronostico.id,
            )
            for centro, pronostico in (
                (centro_a, pronostico_a),
                (centro_b, pronostico_b),
            )
        ]
        sesion.add_all(alertas)
        sesion.flush()

        resultado = notificar_alertas(
            sesion, alertas, url_base="http://localhost:8000", transportador=transporte
        )

        por_destinatario = {destinatario: cuerpo for destinatario, cuerpo in correos}
        assert resultado["correos_enviados"] == 3
        assert len(correos) == 3
        assert "Centro: Centro A" in por_destinatario["jefatura.a@test.cl"]
        assert "Centro: Centro B" not in por_destinatario["jefatura.a@test.cl"]
        assert "Centro: Centro B" in por_destinatario["jefatura.b@test.cl"]
        assert "Centro: Centro A" not in por_destinatario["jefatura.b@test.cl"]
        assert "Centro: Centro A" in por_destinatario["subdirector@test.cl"]
        assert "Centro: Centro B" in por_destinatario["subdirector@test.cl"]
