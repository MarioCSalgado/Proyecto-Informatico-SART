"""RF-4/RF-5: la corrida ambiental entrega sus alertas al envío real de T4."""

import re
import smtplib
from datetime import UTC, date, datetime, time, timedelta
from functools import partial
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, delete, select, text, update
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session

from sart.db.modelos import Alerta, CentroSalud, Estacion, Medicion, Notificacion, Usuario, Zona
from sart.dominio.roles import Rol
from sart.dominio.valores import (
    EstadoNotificacion,
    FuenteEstacion,
    OrigenMedicion,
    TipoAlerta,
    TipoCentro,
    TipoMedicion,
)
from sart.parametros import cargar_parametros
from sart.tareas import __main__ as comando
from sart.tareas.ambiental import correr_ambiental
from sart.tareas.notificaciones import notificar_alertas

DIA = date(2026, 10, 10)
MOTORES = ["sqlite", pytest.param("postgresql", marks=pytest.mark.integracion)]


@pytest.fixture(autouse=True)
def sin_smtp_real(monkeypatch):
    """Impide abrir SMTP incluso si se omite accidentalmente el transportador."""
    conexiones = []

    def bloquear(*args, **kwargs):
        conexiones.append(True)
        raise AssertionError("RF-4/RF-5: SMTP real bloqueado en la prueba")

    monkeypatch.setattr(smtplib, "SMTP", bloquear)
    monkeypatch.setattr(smtplib, "SMTP_SSL", bloquear)
    yield
    assert conexiones == [], "Se intentó abrir una conexión SMTP real"


@pytest.fixture
def motor_ambiental(request):
    """RF-4/RF-5: reutiliza SQLite o migra PostgreSQL solo tras verificar la base temporal."""
    if getattr(request, "param", "sqlite") == "sqlite":
        yield request.getfixturevalue("motor_memoria")
        return

    assert request.param == "postgresql"
    crear_base_temporal = request.getfixturevalue("crear_base_temporal")
    url = crear_base_temporal()
    destino = make_url(url)
    nombre = destino.database or ""
    assert destino.get_backend_name() == "postgresql"
    assert re.fullmatch(r"sart_prueba_[0-9a-f]{8}", nombre), "Se requiere una base temporal de pytest"
    motor = create_engine(url, connect_args={"connect_timeout": 5})
    try:
        # No migrar ni insertar antes de verificar la conexión efectiva.
        with motor.connect() as conexion:
            assert conexion.scalar(text("SELECT current_database()")) == nombre
            version = conexion.scalar(text("SHOW server_version"))
        print(f"RF-4/RF-5: destino temporal verificado {destino.host}:{destino.port}/{nombre}; PG {version}")
        config = Config(str(Path(__file__).resolve().parents[1] / "alembic.ini"))
        config.attributes["url"] = url
        command.upgrade(config, "head")
        yield motor
    finally:
        motor.dispose()


@pytest.fixture
def escenario(motor_ambiental, monkeypatch):
    """Dos zonas controladas; la jefatura afectada tiene dos centros en la misma zona."""
    parametros = cargar_parametros()
    parametros["escenario"]["comunas"] = ["Zona afectada", "Zona ajena"]
    parametros["escenario"]["estacion_respaldo"] = "SINCA afectada"
    parametros["catalogo"]["estacion_por_comuna"] = {
        "Zona afectada": "SINCA afectada", "Zona ajena": "SINCA ajena",
    }
    inicio = datetime.combine(DIA, time.min, tzinfo=ZoneInfo(parametros["zona_horaria"]))
    with Session(motor_ambiental) as sesion:
        zonas = [Zona(nombre=nombre) for nombre in parametros["escenario"]["comunas"]]
        sesion.add_all(zonas)
        sesion.flush()
        estaciones = [
            Estacion(nombre=nombre, comuna=zona.nombre, zona_id=zona.id, fuente=fuente)
            for nombre, zona, fuente in (
                ("SINCA afectada", zonas[0], FuenteEstacion.SINCA),
                ("SINCA ajena", zonas[1], FuenteEstacion.SINCA),
                ("Open-Meteo afectada", zonas[0], FuenteEstacion.OPEN_METEO),
            )
        ]
        sesion.add_all(estaciones)
        sesion.flush()
        centros = [
            CentroSalud(
                codigo_deis=1001 + indice, nombre=f"Centro {indice}", tipo=TipoCentro.SAPU,
                comuna=zonas[zona].nombre, zona_id=zonas[zona].id,
                estacion_id=estaciones[zona].id,
            )
            for indice, zona in enumerate((0, 0, 1))
        ]
        sesion.add_all([
            Usuario(nombre="Jefatura afectada", correo="afectada@example.test", rol=Rol.JEFATURA,
                    hash_contrasena="no-se-usa-login", centros=centros[:2]),
            Usuario(nombre="Jefatura ajena", correo="ajena@example.test", rol=Rol.JEFATURA,
                    hash_contrasena="no-se-usa-login", centros=centros[2:]),
            Usuario(nombre="Subdirección", correo="subdireccion@example.test", rol=Rol.SUBDIRECTOR,
                    hash_contrasena="no-se-usa-login"),
            Usuario(nombre="Administración", correo="admin@example.test", rol=Rol.ADMINISTRADOR,
                    hash_contrasena="no-se-usa-login"),
        ])
        sesion.add_all([
            Medicion(
                estacion_id=estaciones[2].id,
                fecha_hora=(inicio + timedelta(hours=hora)).astimezone(UTC),
                tipo=TipoMedicion.MP25, valor=95.0, unidad="µg/m³", origen=OrigenMedicion.PRONOSTICO,
            )
            for hora in range(24)
        ])
        # El camino SINCA usa un dato reciente por zona; la zona ajena queda normal.
        sesion.add_all([
            Medicion(
                estacion_id=estaciones[indice].id, fecha_hora=inicio.astimezone(UTC),
                tipo=TipoMedicion.MP25, valor=valor, unidad="µg/m³", origen=OrigenMedicion.OBSERVADO,
            )
            for indice, valor in enumerate((95.0, 45.0))
        ])
        sesion.commit()

    monkeypatch.setattr("sart.tareas.ambiental.parametros_vigentes", lambda sesion: parametros)
    monkeypatch.setattr("sart.tareas.ambiental._sensibilidad_tc12", lambda *args: (True, 1.0))
    monkeypatch.setenv("DATABASE_URL", motor_ambiental.url.render_as_string(hide_password=False))
    monkeypatch.setattr(comando, "crear_motor", lambda: motor_ambiental)
    if motor_ambiental.dialect.name == "sqlite":
        # SQLite en memoria debe sobrevivir al comando para verificar la persistencia.
        # PostgreSQL conserva dispose real: la lectura posterior abre otra conexión.
        monkeypatch.setattr(motor_ambiental, "dispose", lambda: None)
    correos = []

    def transportar(destinatario, asunto, cuerpo):
        correos.append((destinatario, asunto, cuerpo))

    monkeypatch.setenv("SART_URL_PUBLICA", "http://sart.example.test")
    monkeypatch.setattr(comando, "notificar_alertas", partial(notificar_alertas, transportador=transportar))
    return motor_ambiental, correos


def _ejecutar():
    return comando.main(["ambiental", "--fecha", DIA.isoformat()])


def _comprobar_envio(motor, correos, fuente):
    with Session(motor) as sesion:
        alerta = sesion.scalars(select(Alerta)).one()
        assert alerta.tipo == TipoAlerta.AMBIENTAL
        assert alerta.fuente_ambiental == fuente
        assert alerta.nivel == "alerta"
        assert alerta.valor_mp25 == pytest.approx(95.0)
        assert alerta.zona_id == sesion.scalar(select(Zona.id).where(Zona.nombre == "Zona afectada"))
        assert alerta.fecha_emision is not None
        assert (alerta.dia_pronosticado if fuente == "pronostico" else alerta.dia_observado) == DIA
        if motor.dialect.name == "postgresql":
            assert alerta.fecha_emision.tzinfo is not None
        filas = sesion.execute(
            select(Notificacion, Usuario.correo)
            .join(Usuario, Usuario.id == Notificacion.usuario_id)
        ).all()
        assert len(filas) == 2
        assert {correo for _, correo in filas} == {"afectada@example.test", "subdireccion@example.test"}
        por_destinatario = {destino: cuerpo for destino, _, cuerpo in correos}
        assert len(correos) == len(por_destinatario) == 2
        for notificacion, correo in filas:
            assert notificacion.alerta_id == alerta.id
            assert notificacion.estado == EstadoNotificacion.ENVIADA
            assert notificacion.fecha_envio is not None
            if motor.dialect.name == "postgresql":
                assert notificacion.fecha_envio.tzinfo is not None
            assert notificacion.intentos == 1
            cuerpo = por_destinatario[correo]
            assert "Zona: Zona afectada" in cuerpo
            assert "Zona ajena" not in cuerpo
            assert "95.0 µg/m³" in cuerpo
            assert (
                "Fuente: Open-Meteo (pronóstico ambiental)"
                if fuente == "pronostico"
                else "Fuente: SINCA (observación utilizada como respaldo, no es un pronóstico)"
            ) in cuerpo
            assert DIA.isoformat() in cuerpo
            assert f"http://sart.example.test/acuse/{notificacion.token_acuse}" in cuerpo


@pytest.mark.parametrize("fuente", ["pronostico", "sinca"])
@pytest.mark.parametrize("motor_ambiental", MOTORES, indirect=True)
def test_rf4_rf5_comando_genera_envia_y_persiste(escenario, monkeypatch, fuente):
    motor, correos = escenario
    if fuente == "sinca":
        monkeypatch.setattr("sart.tareas.ambiental._sensibilidad_tc12", lambda *args: (False, 0.0))
    assert _ejecutar() == 0
    _comprobar_envio(motor, correos, fuente)


@pytest.mark.parametrize("fuente", ["pronostico", "sinca"])
def test_rf4_rf5_contenido_ambiental_controlado_y_con_acuse(escenario, monkeypatch, fuente):
    motor, correos = escenario
    if fuente == "sinca":
        monkeypatch.setattr("sart.tareas.ambiental._sensibilidad_tc12", lambda *args: (False, 0.0))
    with Session(motor) as sesion:
        correr_ambiental(sesion, fecha=DIA)
        alerta = sesion.scalars(select(Alerta)).one()
        # El correo debe usar campos estructurados y texto controlado, no el mensaje libre.
        alerta.mensaje = "TEXTO-LIBRE-QUE-NO-DEBE-SALIR-EN-EL-CORREO"
        sesion.commit()
    assert _ejecutar() == 0
    _comprobar_envio(motor, correos, fuente)
    for _, asunto, cuerpo in correos:
        assert asunto == "SART: 1 alerta(s) requieren atención"
        assert "Se han generado las siguientes alertas en SART:" in cuerpo
        assert "Tipo: ambiental" in cuerpo
        assert "Nivel: alerta" in cuerpo
        assert "Emitida: " in cuerpo
        assert cuerpo.count(
            "Este aviso de SART no constituye una declaración oficial de episodio crítico."
        ) == 1
        assert "TEXTO-LIBRE-QUE-NO-DEBE-SALIR-EN-EL-CORREO" not in cuerpo
        assert "Pronóstico de consultas:" not in cuerpo
        assert "Dotación sugerida:" not in cuerpo
        if fuente == "pronostico":
            assert "Fuente: Open-Meteo (pronóstico ambiental)" in cuerpo
            assert f"Día pronosticado: {DIA}" in cuerpo
            assert "Día observado:" not in cuerpo
            assert "Fuente: SINCA" not in cuerpo
        else:
            assert "Fuente: SINCA (observación utilizada como respaldo, no es un pronóstico)" in cuerpo
            assert f"Día observado: {DIA}" in cuerpo
            assert "Día pronosticado:" not in cuerpo
            assert "Fuente: Open-Meteo" not in cuerpo


@pytest.mark.parametrize("fuente", ["pronostico", "sinca"])
@pytest.mark.parametrize("motor_ambiental", MOTORES, indirect=True)
def test_rf4_rf5_repetir_comando_no_duplica_notificaciones(escenario, monkeypatch, fuente):
    motor, correos = escenario
    if fuente == "sinca":
        monkeypatch.setattr("sart.tareas.ambiental._sensibilidad_tc12", lambda *args: (False, 0.0))
    assert _ejecutar() == 0
    with Session(motor) as sesion:
        originales = [
            (n.id, n.token_acuse, n.fecha_envio, n.intentos)
            for n in sesion.scalars(select(Notificacion).order_by(Notificacion.id))
        ]
        assert len(originales) == 2
    assert _ejecutar() == 0
    _comprobar_envio(motor, correos, fuente)
    with Session(motor) as sesion:
        assert [
            (n.id, n.token_acuse, n.fecha_envio, n.intentos)
            for n in sesion.scalars(select(Notificacion).order_by(Notificacion.id))
        ] == originales


@pytest.mark.parametrize("fuente", ["pronostico", "sinca"])
@pytest.mark.parametrize("motor_ambiental", MOTORES, indirect=True)
def test_rf4_rf5_recupera_alerta_de_la_corrida_guardada_sin_notificar(escenario, monkeypatch, fuente):
    motor, correos = escenario
    if fuente == "sinca":
        monkeypatch.setattr("sart.tareas.ambiental._sensibilidad_tc12", lambda *args: (False, 0.0))
    with Session(motor) as sesion:
        assert correr_ambiental(sesion, fecha=DIA).alertas == 1
        alerta = sesion.scalars(select(Alerta)).one()
        original = (alerta.id, alerta.fecha_emision, alerta.valor_mp25)
        assert sesion.scalars(select(Notificacion)).all() == []
    assert correos == []
    assert _ejecutar() == 0
    _comprobar_envio(motor, correos, fuente)
    with Session(motor) as sesion:
        alerta = sesion.scalars(select(Alerta)).one()
        assert (alerta.id, alerta.fecha_emision, alerta.valor_mp25) == original


@pytest.mark.parametrize("fuente", ["pronostico", "sinca"])
def test_rf4_rf5_sin_alertas_no_intenta_notificar(escenario, monkeypatch, fuente):
    motor, correos = escenario
    if fuente == "sinca":
        monkeypatch.setattr("sart.tareas.ambiental._sensibilidad_tc12", lambda *args: (False, 0.0))
    with Session(motor) as sesion:
        sesion.execute(update(Medicion).values(valor=45.0))
        sesion.commit()
    monkeypatch.delenv("SART_URL_PUBLICA")
    assert _ejecutar() == 0
    assert correos == []
    with Session(motor) as sesion:
        assert sesion.scalars(select(Alerta)).all() == []
        assert sesion.scalars(select(Notificacion)).all() == []


def test_rf4_rf5_sin_datos_no_intenta_notificar(escenario, monkeypatch):
    motor, correos = escenario
    with Session(motor) as sesion:
        sesion.execute(delete(Medicion))
        sesion.commit()
    monkeypatch.delenv("SART_URL_PUBLICA")
    assert _ejecutar() == 0
    assert correos == []
    with Session(motor) as sesion:
        assert sesion.scalars(select(Alerta)).all() == []
        assert sesion.scalars(select(Notificacion)).all() == []


def test_rf4_rf5_recuperacion_no_barre_el_historico(escenario):
    motor, correos = escenario
    with Session(motor) as sesion:
        zona = sesion.scalars(select(Zona).where(Zona.nombre == "Zona afectada")).one()
        anterior = Alerta(
            tipo=TipoAlerta.AMBIENTAL, nivel="alerta", zona_id=zona.id,
            fuente_ambiental="pronostico", dia_pronosticado=DIA - timedelta(days=30),
            valor_mp25=95.0, mensaje="Alerta fuera de la corrida de prueba",
            fecha_emision=datetime(2026, 9, 9, tzinfo=UTC),
        )
        sesion.add(anterior)
        sesion.commit()
        anterior_id = anterior.id
    assert _ejecutar() == 0
    assert len(correos) == 2
    with Session(motor) as sesion:
        assert sesion.scalars(select(Notificacion).where(Notificacion.alerta_id == anterior_id)).all() == []
        notificaciones = sesion.scalars(select(Notificacion)).all()
        assert len(notificaciones) == 2
        assert all(n.estado == EstadoNotificacion.ENVIADA for n in notificaciones)


def test_rf4_rf5_recupera_solo_el_destinatario_sin_notificar(escenario):
    motor, correos = escenario
    with Session(motor) as sesion:
        correr_ambiental(sesion, fecha=DIA)
        alerta = sesion.scalars(select(Alerta)).one()
        jefatura = sesion.scalars(select(Usuario).where(Usuario.correo == "afectada@example.test")).one()
        enviada = Notificacion(
            alerta_id=alerta.id, usuario_id=jefatura.id, estado=EstadoNotificacion.ENVIADA,
            fecha_envio=datetime(2026, 10, 9, 12, tzinfo=UTC), intentos=1,
        )
        sesion.add(enviada)
        sesion.commit()
        sesion.refresh(enviada)
        original = (enviada.id, enviada.fecha_envio, enviada.token_acuse, enviada.intentos)
    assert _ejecutar() == 0
    assert [destino for destino, _, _ in correos] == ["subdireccion@example.test"]
    with Session(motor) as sesion:
        enviada = sesion.get(Notificacion, original[0])
        assert (enviada.id, enviada.fecha_envio, enviada.token_acuse, enviada.intentos) == original
        assert len(sesion.scalars(select(Notificacion)).all()) == 2
