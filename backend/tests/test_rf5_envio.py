from datetime import UTC, date, datetime

from sqlalchemy.orm import Session
from sqlalchemy import select

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
