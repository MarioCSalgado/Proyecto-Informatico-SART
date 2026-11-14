"""Reglas de calidad de §5.1 que la base hace cumplir (centros, consultas, mediciones, pronósticos, alertas,
notificaciones y auditoría). Corre en SQLite; la migración real se compara en test_migraciones.py."""

from datetime import UTC, date, datetime

import pytest
from sqlalchemy import create_engine, event, func, select
from sqlalchemy.exc import IntegrityError, StatementError
from sqlalchemy.orm import Session

from sart.db.modelos import (
    Alerta,
    Auditoria,
    Base,
    CentroSalud,
    ConsultaSemanal,
    Estacion,
    Medicion,
    Notificacion,
    Pronostico,
    Usuario,
    UsuarioCentro,
    Zona,
)
from sart.dominio.roles import Rol
from sart.dominio.valores import EstadoNotificacion, FuenteEstacion, TipoAlerta, TipoCentro, TipoMedicion

AHORA = datetime(2026, 11, 13, 9, tzinfo=UTC)


@pytest.fixture
def sesion():
    motor = create_engine("sqlite://")
    event.listen(motor, "connect", lambda conexion, _: conexion.execute("PRAGMA foreign_keys=ON"))
    Base.metadata.create_all(motor)
    with Session(motor) as sesion:
        zona = Zona(nombre="Concepción")
        estacion = Estacion(
            nombre="Kingston College", comuna="Concepción", zona=zona, fuente=FuenteEstacion.SINCA
        )
        centro = CentroSalud(
            codigo_deis=100001,
            codigo_antiguo=9001,
            nombre="Centro de prueba",
            tipo=TipoCentro.SAPU,
            comuna="Concepción",
            zona=zona,
            estacion=estacion,
        )
        usuario = Usuario(nombre="Jefatura", correo="j@demo.sart", rol=Rol.JEFATURA, hash_contrasena="x")
        sesion.add_all([centro, usuario])
        sesion.commit()
        yield sesion
    motor.dispose()


def _centro(sesion) -> CentroSalud:
    return sesion.scalars(select(CentroSalud)).one()


def _falla(sesion, objeto, error=IntegrityError):
    sesion.add(objeto)
    with pytest.raises(error):
        sesion.commit()
    sesion.rollback()


# --- Centro_Salud -----------------------------------------------------------
def test_tipo_de_centro_fuera_de_los_cuatro_se_rechaza(sesion):
    centro = _centro(sesion)
    _falla(
        sesion,
        CentroSalud(
            codigo_deis=2,
            nombre="X",
            tipo="CESFAM",
            comuna="Penco",
            zona_id=centro.zona_id,
            estacion_id=centro.estacion_id,
        ),
        StatementError,
    )


def test_codigo_deis_unico(sesion):
    centro = _centro(sesion)
    _falla(
        sesion,
        CentroSalud(
            codigo_deis=100001,
            nombre="Duplicado",
            tipo=TipoCentro.SAR,
            comuna="Penco",
            zona_id=centro.zona_id,
            estacion_id=centro.estacion_id,
        ),
    )


def test_centros_asignados_a_un_usuario_y_baja_en_cascada(sesion):
    """RF-9: centros asignados; RF-16 E2: al borrar la cuenta se borran sus asignaciones."""
    usuario = sesion.scalars(select(Usuario)).one()
    usuario.centros.append(_centro(sesion))
    sesion.commit()
    assert sesion.scalar(select(func.count()).select_from(UsuarioCentro)) == 1

    sesion.delete(usuario)
    sesion.commit()
    assert sesion.scalar(select(func.count()).select_from(UsuarioCentro)) == 0
    assert sesion.scalar(select(func.count()).select_from(CentroSalud)) == 1


# --- Consulta_semanal -------------------------------------------------------
def _consulta(centro_id, **cambios):
    datos = {
        "centro_id": centro_id,
        "anio": 2026,
        "semana": 40,
        "causa": "neumonia",
        "grupo_edad": "de_1_a_4",
        "cantidad": 7,
    }
    return ConsultaSemanal(**{**datos, **cambios})


def test_una_consulta_por_centro_semana_causa_y_edad(sesion):
    sesion.add(_consulta(_centro(sesion).id))
    sesion.commit()
    _falla(sesion, _consulta(_centro(sesion).id, cantidad=9))


@pytest.mark.parametrize("cambio", [{"semana": 0}, {"semana": 54}, {"cantidad": -1}])
def test_semana_entre_1_y_53_y_cantidad_no_negativa(sesion, cambio):
    _falla(sesion, _consulta(_centro(sesion).id, **cambio))


# --- Medición ---------------------------------------------------------------
def _medicion(sesion, **cambios):
    datos = {
        "estacion_id": _centro(sesion).estacion_id,
        "fecha_hora": AHORA,
        "tipo": TipoMedicion.MP25,
        "valor": 35.0,
        "unidad": "µg/m³",
    }
    return Medicion(**{**datos, **cambios})


def test_medicion_valida(sesion):
    sesion.add(_medicion(sesion))
    sesion.commit()
    assert sesion.scalars(select(Medicion)).one().origen.value == "observado"


@pytest.mark.parametrize(
    "cambio",
    [{"unidad": "°C"}, {"valor": -1.0}, {"tipo": TipoMedicion.HUMEDAD, "unidad": "%", "valor": 120.0}],
)
def test_unidad_compatible_y_valores_posibles(sesion, cambio):
    """§5.1: la unidad debe ser compatible con el tipo de medición."""
    _falla(sesion, _medicion(sesion, **cambio))


# --- Pronóstico -------------------------------------------------------------
def _pronostico(centro_id, **cambios):
    datos = {
        "centro_id": centro_id,
        "anio": 2026,
        "semana": 45,
        "valor": 545.0,
        "limite_inferior": 480.0,
        "limite_superior": 610.0,
        "version_modelo": "glm-qp-1",
        "fecha_corte": date(2026, 10, 31),
    }
    return Pronostico(**{**datos, **cambios})


@pytest.mark.parametrize("cambio", [{"valor": 0.0, "limite_inferior": 0.0}, {"valor": 700.0}])
def test_valor_positivo_y_dentro_de_su_intervalo(sesion, cambio):
    _falla(sesion, _pronostico(_centro(sesion).id, **cambio))


def test_un_solo_pronostico_vigente_por_centro_y_semana(sesion):
    """§5.1. Un pronóstico reemplazado (no vigente) puede convivir con el nuevo."""
    centro_id = _centro(sesion).id
    sesion.add_all([_pronostico(centro_id), _pronostico(centro_id, vigente=False, valor=500.0)])
    sesion.commit()

    _falla(sesion, _pronostico(centro_id, valor=560.0))


# --- Alerta -----------------------------------------------------------------
def test_alerta_de_demanda_va_con_centro_y_pronostico(sesion):
    centro_id = _centro(sesion).id
    pronostico = _pronostico(centro_id)
    sesion.add(pronostico)
    sesion.commit()

    sesion.add(
        Alerta(
            tipo=TipoAlerta.DEMANDA,
            nivel="alerta",
            fecha_emision=AHORA,
            mensaje="Sobre el p90",
            centro_id=centro_id,
            pronostico_id=pronostico.id,
        )
    )
    sesion.commit()
    _falla(
        sesion,
        Alerta(
            tipo=TipoAlerta.DEMANDA,
            nivel="alerta",
            fecha_emision=AHORA,
            mensaje="Sin centro",
            pronostico_id=pronostico.id,
        ),
    )
    _falla(
        sesion,
        Alerta(
            tipo=TipoAlerta.DEMANDA,
            nivel="normal",
            fecha_emision=AHORA,
            mensaje="Normal no alerta",
            centro_id=centro_id,
            pronostico_id=pronostico.id,
        ),
    )


def test_alerta_ambiental_va_con_zona_dia_y_valor(sesion):
    zona_id = _centro(sesion).zona_id
    sesion.add(
        Alerta(
            tipo=TipoAlerta.AMBIENTAL,
            nivel="preemergencia",
            fecha_emision=AHORA,
            mensaje="MP2,5",
            zona_id=zona_id,
            dia_pronosticado=date(2026, 11, 14),
            valor_mp25=120.0,
        )
    )
    sesion.commit()
    _falla(
        sesion,
        Alerta(
            tipo=TipoAlerta.AMBIENTAL,
            nivel="alerta",
            fecha_emision=AHORA,
            mensaje="Con centro",
            zona_id=zona_id,
            centro_id=_centro(sesion).id,
            dia_pronosticado=date(2026, 11, 14),
            valor_mp25=90.0,
        ),
    )
    _falla(
        sesion,
        Alerta(
            tipo=TipoAlerta.AMBIENTAL,
            nivel="atencion",
            fecha_emision=AHORA,
            mensaje="Nivel ajeno",
            zona_id=zona_id,
            dia_pronosticado=date(2026, 11, 14),
            valor_mp25=90.0,
        ),
    )


# --- Notificación y auditoría ----------------------------------------------
def _alerta_ambiental(sesion) -> Alerta:
    alerta = Alerta(
        tipo=TipoAlerta.AMBIENTAL,
        nivel="alerta",
        fecha_emision=AHORA,
        mensaje="MP2,5",
        zona_id=_centro(sesion).zona_id,
        dia_pronosticado=date(2026, 11, 14),
        valor_mp25=85.0,
    )
    sesion.add(alerta)
    sesion.commit()
    return alerta


def test_sin_avisos_duplicados_y_confirmada_con_fecha(sesion):
    alerta = _alerta_ambiental(sesion)
    usuario = sesion.scalars(select(Usuario)).one()
    sesion.add(
        Notificacion(
            alerta_id=alerta.id, usuario_id=usuario.id, estado=EstadoNotificacion.ENVIADA, fecha_envio=AHORA
        )
    )
    sesion.commit()

    _falla(
        sesion,
        Notificacion(
            alerta_id=alerta.id, usuario_id=usuario.id, estado=EstadoNotificacion.REENVIADA, fecha_envio=AHORA
        ),
    )
    notificacion = sesion.scalars(select(Notificacion)).one()
    notificacion.estado = EstadoNotificacion.CONFIRMADA
    with pytest.raises(IntegrityError):
        sesion.commit()


def test_la_baja_de_la_cuenta_no_borra_el_historial(sesion):
    """RF-16 E2: se conservan notificaciones y auditoría, sin el usuario."""
    alerta = _alerta_ambiental(sesion)
    usuario = sesion.scalars(select(Usuario)).one()
    sesion.add_all(
        [
            Notificacion(
                alerta_id=alerta.id,
                usuario_id=usuario.id,
                estado=EstadoNotificacion.ENVIADA,
                fecha_envio=AHORA,
            ),
            Auditoria(
                autor_id=usuario.id,
                autor_rol="jefatura",
                accion="confirmacion",
                entidad="notificacion",
                valor_nuevo={"estado": "confirmada"},
            ),
        ]
    )
    sesion.commit()

    sesion.delete(usuario)
    sesion.commit()
    sesion.expire_all()

    assert sesion.scalars(select(Notificacion)).one().usuario_id is None
    auditoria = sesion.scalars(select(Auditoria)).one()
    assert auditoria.autor_id is None
    assert auditoria.autor_rol == "jefatura"
    assert auditoria.valor_nuevo == {"estado": "confirmada"}
