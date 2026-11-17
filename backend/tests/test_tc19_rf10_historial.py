"""RF-10, TC-19: historial de demanda con datos de prueba del invierno de 2025."""

from datetime import UTC, datetime, timedelta

import pytest
from conftest import SECRETO_DE_PRUEBA
from sqlalchemy.orm import Session

from sart.api.tokens import NOMBRE_COOKIE, emitir_token
from sart.db.modelos import (
    Alerta,
    CentroSalud,
    ConsultaSemanal,
    DotacionSugerida,
    Estacion,
    Pronostico,
    SemanaCarga,
    UmbralCentro,
    Usuario,
    Zona,
)
from sart.dominio.roles import Rol
from sart.dominio.semanas import inicio_semana
from sart.dominio.valores import FuenteEstacion, OrigenUmbral, TipoAlerta, TipoCentro

RUTA = "/alertas/historial"
ANIO = 2025
EMISION = datetime(2025, 7, 7, 9, tzinfo=UTC)


def _emitir(sesion, centro, umbral, semana, *, nivel="alerta", vigente=True):
    pronostico = Pronostico(
        centro_id=centro.id,
        anio=ANIO,
        semana=semana,
        valor=95 if not vigente else 130,
        limite_inferior=70,
        limite_superior=150,
        version_modelo="prueba",
        fecha_corte=inicio_semana(ANIO, semana) - timedelta(weeks=1),
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
    sesion.add(
        Alerta(
            tipo=TipoAlerta.DEMANDA,
            nivel=nivel,
            fecha_emision=EMISION,
            mensaje="Alerta de prueba",
            centro_id=centro.id,
            pronostico_id=pronostico.id,
        )
    )


@pytest.fixture
def historial(cliente, motor_memoria):
    with Session(motor_memoria) as sesion:
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
                centros=[a] if nombre == "jefatura" else [],
            )
            for nombre, rol in (
                ("jefatura", Rol.JEFATURA),
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

        _emitir(sesion, a, anterior, 28, vigente=False)
        _emitir(sesion, a, actual, 28, nivel="atencion")
        for semana in (29, 30, 31, 32):
            _emitir(sesion, a, anterior, semana)
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
        sesion.commit()
        tokens = {
            nombre: emitir_token(
                usuario_id=cuenta.id, rol=cuenta.rol, secreto=SECRETO_DE_PRUEBA, duracion=timedelta(minutes=5)
            )
            for nombre, cuenta in cuentas.items()
        }

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


def test_rf10_jefatura_no_puede_consultar_centros_ajenos(historial):
    api = historial("jefatura")
    assert api.get(RUTA, params={"codigo_deis": 100002}).status_code == 403
    assert api.get(RUTA, params={"codigo_deis": 999999}).status_code == 403
    assert historial("sin_centros").get(RUTA).json() == []


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
