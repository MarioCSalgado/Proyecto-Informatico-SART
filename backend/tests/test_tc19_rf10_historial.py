"""RF-10, TC-19: historial de demanda con datos de prueba del invierno de 2025."""

import re
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from conftest import SECRETO_DE_PRUEBA
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session

from sart.api.app import app
from sart.api.dependencias import obtener_sesion_db
from sart.api.tokens import NOMBRE_COOKIE, emitir_token
from sart.db.modelos import (
    Alerta,
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
from sart.dominio.roles import Rol
from sart.dominio.semanas import inicio_semana
from sart.dominio.valores import EstadoNotificacion, FuenteEstacion, OrigenUmbral, TipoAlerta, TipoCentro

RUTA = "/alertas/historial"
ANIO = 2025
EMISION = datetime(2025, 7, 7, 9, tzinfo=UTC)


def _emitir(sesion, centro, umbral, semana, *, anio=ANIO, nivel="alerta", vigente=True):
    pronostico = Pronostico(
        centro_id=centro.id,
        anio=anio,
        semana=semana,
        valor=95 if not vigente else 130,
        limite_inferior=70,
        limite_superior=150,
        version_modelo="prueba",
        fecha_corte=inicio_semana(anio, semana) - timedelta(weeks=1),
        vigente=vigente,
        nivel=nivel if umbral else None,
        umbral_id=umbral.id if umbral else None,
        k_margen=0.4 if umbral else None,
        valor_con_margen=108 if umbral else None,
    )
    if not vigente:
        pronostico.dotacion = DotacionSugerida(
            profesionales=3,
            llegadas_hora_punta=7.1,
            espera_media_min=4.2,
            espera_con_uno_menos_min=55,
            supuestos={"supuestos_validados": False},
        )
    sesion.add(pronostico)
    sesion.flush()
    alerta = Alerta(
        tipo=TipoAlerta.DEMANDA,
        nivel=nivel,
        fecha_emision=EMISION,
        mensaje="Alerta de prueba",
        centro_id=centro.id,
        pronostico_id=pronostico.id,
    )
    sesion.add(alerta)
    return alerta


def _preparar_historial(motor):
    with Session(motor) as sesion:
        zona = Zona(nombre="Concepción")
        estacion = Estacion(
            nombre="Estación de prueba", comuna="Concepción", zona=zona, fuente=FuenteEstacion.SINCA
        )
        a, b = [
            CentroSalud(
                codigo_deis=codigo,
                nombre=f"Centro {codigo}",
                tipo=TipoCentro.SAR,
                comuna="Concepción",
                zona=zona,
                estacion=estacion,
            )
            for codigo in (100001, 100002)
        ]
        cuentas = {
            nombre: Usuario(
                nombre=nombre,
                correo=f"{nombre}@demo.sart",
                rol=rol,
                hash_contrasena="x",
                centros=[a] if nombre in {"jefatura", "otra_jefatura"} else [],
            )
            for nombre, rol in (
                ("jefatura", Rol.JEFATURA),
                ("otra_jefatura", Rol.JEFATURA),
                ("sin_centros", Rol.JEFATURA),
                ("subdirector", Rol.SUBDIRECTOR),
                ("administrador", Rol.ADMINISTRADOR),
            )
        }
        sesion.add_all([a, b, *cuentas.values()])
        sesion.flush()
        anterior = UmbralCentro(
            centro_id=a.id,
            umbral_atencion=80,
            umbral_alerta=100,
            origen=OrigenUmbral.CALCULADO,
            vigente=False,
        )
        actual = UmbralCentro(
            centro_id=a.id, umbral_atencion=150, umbral_alerta=200, origen=OrigenUmbral.CALCULADO
        )
        umbral_b = UmbralCentro(
            centro_id=b.id, umbral_atencion=70, umbral_alerta=90, origen=OrigenUmbral.CALCULADO
        )
        sesion.add_all([anterior, actual, umbral_b])
        sesion.flush()

        alertas = {28: _emitir(sesion, a, anterior, 28, vigente=False)}
        _emitir(sesion, a, actual, 28, nivel="atencion")
        for semana in (29, 30, 31, 32):
            alertas[semana] = _emitir(sesion, a, anterior, semana)
        _emitir(sesion, a, None, 33)
        _emitir(sesion, b, umbral_b, 28)
        sesion.add(
            Alerta(
                tipo=TipoAlerta.AMBIENTAL,
                nivel="alerta",
                fecha_emision=EMISION,
                mensaje="MP2,5",
                zona_id=zona.id,
                dia_pronosticado=EMISION.date(),
                valor_mp25=95,
            )
        )
        for semana, completa in ((28, True), (29, True), (30, False), (31, True), (33, True)):
            sesion.add(SemanaCarga(anio=ANIO, semana=semana, centros_reportados=2, completa=completa))
        for centro, semana, causa, total in (
            (a, 28, "ira_alta", 95),
            (a, 28, "influenza", 15),
            (a, 28, "covid_identificado", 1000),
            (a, 29, "ira_alta", 100),
            (a, 30, "ira_alta", 300),
            (a, 32, "ira_alta", 300),
            (a, 33, "ira_alta", 120),
            (b, 28, "ira_alta", 0),
        ):
            sesion.add(
                ConsultaSemanal(
                    centro_id=centro.id,
                    anio=ANIO,
                    semana=semana,
                    causa=causa,
                    grupo_edad="1_4",
                    cantidad=total,
                )
            )
        sesion.flush()
        jefatura = cuentas["jefatura"].id
        subdirector = cuentas["subdirector"].id
        estado = EstadoNotificacion
        for semana, usuario_id, nivel in (
            (28, jefatura, estado.ENVIADA),
            (28, subdirector, estado.CONFIRMADA),
            (28, cuentas["otra_jefatura"].id, estado.FALLIDA),
            (28, None, estado.CONFIRMADA),  # Se conserva el historial tras la baja de la cuenta.
            (29, jefatura, estado.CONFIRMADA),
            (30, jefatura, estado.REENVIADA),
            (30, subdirector, estado.ESCALADA),
            (31, jefatura, estado.ESCALADA),
            (32, subdirector, estado.FALLIDA),
        ):
            sesion.add(
                Notificacion(
                    alerta_id=alertas[semana].id,
                    usuario_id=usuario_id,
                    estado=nivel,
                    fecha_envio=EMISION,
                    fecha_confirmacion=EMISION + timedelta(hours=2) if nivel == estado.CONFIRMADA else None,
                    fecha_reenvio=EMISION + timedelta(hours=24) if nivel == estado.REENVIADA else None,
                    fecha_escalamiento=EMISION + timedelta(hours=48) if nivel == estado.ESCALADA else None,
                    token_acuse=f"token-privado-{semana}-{usuario_id}",
                )
            )
        sesion.commit()
        return {
            nombre: emitir_token(
                usuario_id=cuenta.id, rol=cuenta.rol, secreto=SECRETO_DE_PRUEBA, duracion=timedelta(minutes=5)
            )
            for nombre, cuenta in cuentas.items()
        }


@pytest.fixture
def historial(cliente, motor_memoria):
    tokens = _preparar_historial(motor_memoria)

    def entrar(nombre):
        cliente.cookies.set(NOMBRE_COOKIE, tokens[nombre])
        return cliente

    return entrar


def test_tc19_muestra_cada_alerta_con_su_pronostico_y_umbral_original(historial):
    respuesta = historial("jefatura").get(RUTA)
    assert respuesta.status_code == 200
    filas = respuesta.json()
    assert [fila["pronostico"]["semana"] for fila in filas] == [33, 32, 31, 30, 29, 28, 28]
    (reemplazada,) = [fila for fila in filas if fila["pronostico"]["vigente"] is False]
    assert reemplazada["centro"]["codigo_deis"] == 100001
    assert reemplazada["fecha_emision"] == "2025-07-07T09:00:00Z"
    assert reemplazada["pronostico"]["inicio_semana"] == inicio_semana(ANIO, 28).isoformat()
    assert reemplazada["pronostico"]["valor"] == 95
    assert reemplazada["pronostico"]["umbral_alerta"] == 100
    assert reemplazada["dotacion"]["profesionales"] == 3
    assert reemplazada["dotacion"]["espera_media_min"] == 4.2
    assert reemplazada["observacion"] == {"consultas": 110, "semana_alta": True}

    (atencion,) = [fila for fila in filas if fila["nivel"] == "atencion"]
    assert atencion["pronostico"]["umbral_alerta"] == 200
    assert atencion["dotacion"] is None
    assert atencion["observacion"] == {"consultas": 110, "semana_alta": False}
    por_semana = {fila["pronostico"]["semana"]: fila["observacion"] for fila in filas}
    assert por_semana[29] == {"consultas": 100, "semana_alta": False}
    for semana in (30, 31, 32):
        assert por_semana[semana] == {"consultas": None, "semana_alta": None}
    assert por_semana[33] == {"consultas": 120, "semana_alta": None}


def test_rf10_filtra_por_centro_semanas_objetivo_y_nivel(historial):
    api = historial("subdirector")
    respuesta = api.get(
        RUTA,
        params={
            "codigo_deis": 100001,
            "desde": inicio_semana(ANIO, 29) + timedelta(days=2),
            "hasta": inicio_semana(ANIO, 30),
            "nivel": "alerta",
        },
    )
    assert respuesta.status_code == 200
    assert [fila["pronostico"]["semana"] for fila in respuesta.json()] == [30, 29]
    assert all(fila["centro"]["codigo_deis"] == 100001 for fila in respuesta.json())

    atenciones = api.get(RUTA, params={"nivel": "atencion"}).json()
    assert [fila["nivel"] for fila in atenciones] == ["atencion"]
    assert api.get(RUTA, params={"hasta": inicio_semana(ANIO, 27)}).json() == []


def test_rf10_sin_sesion_da_401(cliente):
    assert cliente.get(RUTA).status_code == 401


def test_rf10_filtra_por_anio_epidemiologico_al_cruzar_diciembre(historial, motor_memoria):
    with Session(motor_memoria) as sesion:
        centro = sesion.scalar(select(CentroSalud).where(CentroSalud.codigo_deis == 100001))
        umbral = sesion.scalar(
            select(UmbralCentro).where(UmbralCentro.centro_id == centro.id, UmbralCentro.vigente.is_(True))
        )
        _emitir(sesion, centro, umbral, 52, anio=2024)
        for semana in (1, 2, 3):
            _emitir(sesion, centro, umbral, semana)
        sesion.commit()

    respuesta = historial("jefatura").get(RUTA, params={"desde": "2024-12-31", "hasta": "2025-01-06"})
    assert respuesta.status_code == 200
    assert [(fila["pronostico"]["anio"], fila["pronostico"]["semana"]) for fila in respuesta.json()] == [
        (2025, 2),
        (2025, 1),
    ]


def test_rnf_s2_historial_no_expone_referencias_de_otro_centro(historial, motor_memoria):
    with Session(motor_memoria) as sesion:
        centro = sesion.scalar(select(CentroSalud).where(CentroSalud.codigo_deis == 100001))
        alerta_ajena = sesion.scalar(select(Alerta).where(Alerta.centro_id != centro.id))
        pronostico_ajeno = sesion.get(Pronostico, alerta_ajena.pronostico_id)
        # Las FK individuales admiten estas referencias, aun cuando los centros no coinciden.
        alerta = _emitir(sesion, centro, None, 34)
        pronostico = sesion.get(Pronostico, alerta.pronostico_id)
        pronostico.umbral_id = pronostico_ajeno.umbral_id
        sesion.add(
            Alerta(
                tipo=TipoAlerta.DEMANDA,
                nivel="alerta",
                fecha_emision=EMISION,
                mensaje="Referencia cruzada de prueba",
                centro_id=centro.id,
                pronostico_id=pronostico_ajeno.id,
            )
        )
        sesion.commit()

    respuesta = historial("jefatura").get(RUTA)
    assert respuesta.status_code == 200
    filas = respuesta.json()
    assert len(filas) == 8  # Siete válidas más la alerta local con umbral inutilizable.
    (sin_umbral,) = [fila for fila in filas if fila["pronostico"]["semana"] == 34]
    assert sin_umbral["pronostico"]["umbral_alerta"] is None


def test_rnf_s2_historial_no_cachea_resultados_de_una_sesion(historial):
    jefatura = historial("jefatura").get(RUTA)
    assert jefatura.headers["Cache-Control"] == "no-store"
    assert {fila["centro"]["codigo_deis"] for fila in jefatura.json()} == {100001}

    red = historial("subdirector").get(RUTA)
    assert red.headers["Cache-Control"] == "no-store"
    assert {fila["centro"]["codigo_deis"] for fila in red.json()} == {100001, 100002}


def test_rf10_jefatura_no_puede_consultar_centros_ajenos_y_se_audita(historial, motor_memoria):
    api = historial("jefatura")
    assert api.get(RUTA, params={"codigo_deis": 100001}).status_code == 200
    for codigo in (100002, 999999):
        respuesta = api.get(RUTA, params={"codigo_deis": codigo})
        assert respuesta.status_code == 403
        assert respuesta.json() == {"detail": "Este centro no está asignado a su cuenta."}
    assert historial("sin_centros").get(RUTA).json() == []

    with Session(motor_memoria) as sesion:
        autor_id = sesion.scalar(select(Usuario.id).where(Usuario.nombre == "jefatura"))
        registros = list(sesion.scalars(select(Auditoria).order_by(Auditoria.id)))
        assert [registro.entidad_id for registro in registros] == ["100002", "999999"]
        for registro in registros:
            assert registro.autor_id == autor_id
            assert registro.autor_rol == Rol.JEFATURA.value
            assert registro.accion == "acceso_denegado"
            assert registro.entidad == "centro_salud"
            assert registro.motivo == "RF-10: centro no asignado"
            assert registro.valor_anterior is None
            assert registro.valor_nuevo is None


def test_rf10_jefatura_ve_solo_su_notificacion_por_alerta(historial):
    respuesta = historial("jefatura").get(RUTA)
    assert respuesta.status_code == 200
    filas = respuesta.json()
    estados = {
        fila["pronostico"]["semana"]: fila["notificaciones"] for fila in filas if fila["nivel"] == "alerta"
    }
    assert estados[28] == {"tipo": "propia", "estado": "enviada", "fecha_confirmacion": None}
    assert estados[29] == {
        "tipo": "propia",
        "estado": "confirmada",
        "fecha_confirmacion": "2025-07-07T11:00:00Z",
    }
    assert estados[30]["estado"] == "reenviada"
    assert estados[31]["estado"] == "escalada"
    assert estados[32] == estados[33] == {"tipo": "propia", "estado": None, "fecha_confirmacion": None}
    (atencion,) = [fila for fila in filas if fila["nivel"] == "atencion"]
    assert atencion["notificaciones"] == {"tipo": "no_aplica"}
    assert "token-privado" not in respuesta.text and "@demo.sart" not in respuesta.text

    respuesta = historial("otra_jefatura").get(RUTA, params={"nivel": "alerta"})
    (alerta,) = [fila for fila in respuesta.json() if fila["pronostico"]["semana"] == 28]
    assert alerta["notificaciones"] == {"tipo": "propia", "estado": "fallida", "fecha_confirmacion": None}


@pytest.mark.parametrize("rol", ["subdirector", "administrador"])
def test_rf10_resumen_por_alerta_para_roles_de_red(historial, rol):
    respuesta = historial(rol).get(RUTA, params={"codigo_deis": 100001})
    assert respuesta.status_code == 200
    filas = respuesta.json()
    assert len(filas) == len({fila["id"] for fila in filas}) == 7
    estados = {
        fila["pronostico"]["semana"]: fila["notificaciones"] for fila in filas if fila["nivel"] == "alerta"
    }
    assert estados[28] == {
        "tipo": "resumen",
        "estados": [
            {"estado": "enviada", "total": 1},
            {"estado": "fallida", "total": 1},
            {"estado": "confirmada", "total": 2},
        ],
    }
    assert estados[30] == {
        "tipo": "resumen",
        "estados": [
            {"estado": "reenviada", "total": 1},
            {"estado": "escalada", "total": 1},
        ],
    }
    assert estados[33] == {"tipo": "resumen", "estados": []}
    assert "token-privado" not in respuesta.text and "@demo.sart" not in respuesta.text


@pytest.mark.parametrize("rol", ["subdirector", "administrador"])
def test_rf10_roles_de_red_ven_todos_los_centros(historial, rol):
    api = historial(rol)
    filas = api.get(RUTA).json()
    assert len(filas) == 8
    assert {fila["centro"]["codigo_deis"] for fila in filas} == {100001, 100002}
    assert api.get(RUTA, params={"codigo_deis": 999999}).status_code == 404
    (cero,) = api.get(RUTA, params={"codigo_deis": 100002}).json()
    assert cero["observacion"] == {"consultas": 0, "semana_alta": False}


@pytest.mark.parametrize(
    "filtros",
    [
        {"desde": "2025-07-25", "hasta": "2025-07-01"},
        {"desde": "2025-02-30"},
        {"nivel": "normal"},
    ],
)
def test_rf10_rechaza_filtros_invalidos(historial, filtros):
    assert historial("subdirector").get(RUTA, params=filtros).status_code == 422


@pytest.mark.integracion
def test_tc19_historial_en_postgresql(crear_base_temporal, monkeypatch):
    """RF-10, TC-19: ejecuta la consulta histórica sobre el esquema migrado de PostgreSQL."""
    url = crear_base_temporal()
    destino = make_url(url)
    nombre = destino.database or ""
    assert destino.get_backend_name() == "postgresql"
    assert re.fullmatch(r"sart_prueba_[0-9a-f]{8}", nombre), "Se requiere una base temporal de pytest"

    motor = create_engine(url)
    try:
        # Verificar el destino efectivo antes de aplicar migraciones o cargar datos.
        with motor.connect() as conexion:
            assert conexion.scalar(text("SELECT current_database()")) == nombre

        config = Config(str(Path(__file__).resolve().parents[1] / "alembic.ini"))
        config.attributes["url"] = url
        command.upgrade(config, "head")
        tokens = _preparar_historial(motor)

        def sesion_de_prueba():
            with Session(motor) as sesion:
                yield sesion

        monkeypatch.setenv("DATABASE_URL", url)
        monkeypatch.setenv("JWT_SECRET", SECRETO_DE_PRUEBA)
        monkeypatch.setitem(app.dependency_overrides, obtener_sesion_db, sesion_de_prueba)

        with TestClient(app) as api:
            api.cookies.set(NOMBRE_COOKIE, tokens["subdirector"])
            respuesta = api.get(
                RUTA,
                params={
                    "codigo_deis": 100001,
                    "desde": "2025-07-07",  # Dentro de la SE 28: el rango se aplica a semanas objetivo.
                    "hasta": "2025-07-20",
                },
            )
            assert respuesta.status_code == 200
            filas = respuesta.json()
            assert [fila["pronostico"]["semana"] for fila in filas] == [30, 29, 28, 28]
            assert {fila["centro"]["codigo_deis"] for fila in filas} == {100001}
            sin_observacion, igualdad, vigente, reemplazada = filas
            assert sin_observacion["observacion"] == {"consultas": None, "semana_alta": None}
            assert igualdad["observacion"] == {"consultas": 100, "semana_alta": False}
            assert vigente["pronostico"]["vigente"] is True
            assert vigente["pronostico"]["umbral_alerta"] == 200
            assert vigente["observacion"] == {"consultas": 110, "semana_alta": False}
            assert reemplazada["pronostico"]["vigente"] is False
            assert reemplazada["pronostico"]["valor"] == 95
            assert reemplazada["pronostico"]["umbral_alerta"] == 100
            assert reemplazada["observacion"] == {"consultas": 110, "semana_alta": True}
            assert reemplazada["notificaciones"]["estados"] == [
                {"estado": "enviada", "total": 1},
                {"estado": "fallida", "total": 1},
                {"estado": "confirmada", "total": 2},
            ]

            respuesta = api.get(RUTA, params={"codigo_deis": 100002})
            assert respuesta.status_code == 200
            (cero,) = respuesta.json()
            assert cero["observacion"] == {"consultas": 0, "semana_alta": False}

            api.cookies.set(NOMBRE_COOKIE, tokens["jefatura"])
            respuesta = api.get(RUTA)
            assert respuesta.status_code == 200
            filas = respuesta.json()
            assert {fila["centro"]["codigo_deis"] for fila in filas} == {100001}
            (reemplazada,) = [fila for fila in filas if not fila["pronostico"]["vigente"]]
            assert reemplazada["notificaciones"] == {
                "tipo": "propia",
                "estado": "enviada",
                "fecha_confirmacion": None,
            }
            assert api.get(RUTA, params={"codigo_deis": 100002}).status_code == 403
            assert api.get(RUTA, params={"codigo_deis": "9" * 61}).status_code == 403

            # El esquema migrado conserva el aviso sin destinatario al dar de baja la cuenta.
            with Session(motor) as sesion:
                destinataria = sesion.scalar(select(Usuario).where(Usuario.nombre == "otra_jefatura"))
                sesion.delete(destinataria)
                jefatura_id = sesion.scalar(select(Usuario.id).where(Usuario.nombre == "jefatura"))
                notificacion = sesion.scalar(
                    select(Notificacion).where(
                        Notificacion.alerta_id == reemplazada["id"], Notificacion.usuario_id == jefatura_id
                    )
                )
                # Los mismos dos campos que actualiza el acuse de T5.
                notificacion.estado = EstadoNotificacion.CONFIRMADA
                notificacion.fecha_confirmacion = EMISION + timedelta(hours=3)
                sesion.commit()

            filtros = {"codigo_deis": 100001, "desde": "2025-07-06", "hasta": "2025-07-06", "nivel": "alerta"}
            api.cookies.set(NOMBRE_COOKIE, tokens["otra_jefatura"])
            assert api.get(RUTA, params=filtros).status_code == 401
            api.cookies.set(NOMBRE_COOKIE, tokens["jefatura"])
            (propia,) = api.get(RUTA, params=filtros).json()
            assert propia["notificaciones"] == {
                "tipo": "propia",
                "estado": "confirmada",
                "fecha_confirmacion": "2025-07-07T12:00:00Z",
            }
            api.cookies.set(NOMBRE_COOKIE, tokens["subdirector"])
            (red,) = api.get(RUTA, params=filtros).json()
            assert red["notificaciones"]["estados"] == [
                {"estado": "fallida", "total": 1},
                {"estado": "confirmada", "total": 3},
            ]

        with Session(motor) as sesion:
            registros = list(
                sesion.scalars(
                    select(Auditoria).where(Auditoria.accion == "acceso_denegado").order_by(Auditoria.id)
                )
            )
            assert [registro.entidad_id for registro in registros] == ["100002", None]
    finally:
        motor.dispose()
