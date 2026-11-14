"""Tareas de RB-4 (semana incompleta) y RB-3 (recálculo de umbrales) sobre la base (RF-1, RF-3, RF-9)."""

from datetime import date, timedelta

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from sart.configuracion import RAIZ_REPOSITORIO
from sart.db.modelos import Base, CentroSalud, ConsultaSemanal, SemanaCarga, UmbralCentro, Usuario
from sart.db.supuestos import ajustar_parametro
from sart.db.umbrales import fijar_umbral_manual, umbral_vigente
from sart.dominio.roles import Rol
from sart.dominio.semanas import semana_epidemiologica
from sart.dominio.valores import OrigenUmbral
from sart.tareas.carga import cargar_catalogo
from sart.tareas.semanas_y_umbrales import marcar_semanas, recalcular_umbrales

ESTABLECIMIENTOS = RAIZ_REPOSITORIO / "datos" / "prueba" / "crudos" / "establecimientos.csv"
ULTIMA_COMPLETA = date(2026, 9, 27)
INCOMPLETA = date(2026, 10, 4)


@pytest.fixture
def sesion():
    """3 centros con 170 semanas de 100 consultas respiratorias (y 999 de COVID, que no cuentan), hasta el
    27/09/2026; la semana del 04/10/2026 trae solo 2 de los 3 centros (67 % < 90 %)."""
    motor = create_engine("sqlite://")
    Base.metadata.create_all(motor)
    with Session(motor) as sesion:
        cargar_catalogo(sesion, ESTABLECIMIENTOS)
        centros = sesion.scalars(select(CentroSalud.id).order_by(CentroSalud.codigo_deis)).all()[:3]
        semanas = [ULTIMA_COMPLETA - timedelta(weeks=i) for i in range(170)]
        for inicio in semanas:
            anio, semana = semana_epidemiologica(inicio)
            for centro in centros:
                sesion.add(_consulta(centro, anio, semana, "ira_alta", 100))
                sesion.add(_consulta(centro, anio, semana, "covid_identificado", 999))
        anio, semana = semana_epidemiologica(INCOMPLETA)
        for centro in centros[:2]:
            sesion.add(_consulta(centro, anio, semana, "ira_alta", 100))
        sesion.add(Usuario(nombre="Admin", correo="a@demo.sart", rol=Rol.ADMINISTRADOR, hash_contrasena="x"))
        sesion.commit()
        yield sesion
    motor.dispose()


def _consulta(centro, anio, semana, causa, cantidad):
    return ConsultaSemanal(
        centro_id=centro, anio=anio, semana=semana, causa=causa, grupo_edad="de_15_a_64", cantidad=cantidad
    )


def _marca(sesion, inicio) -> SemanaCarga:
    anio, semana = semana_epidemiologica(inicio)
    return sesion.get(SemanaCarga, (anio, semana))


def test_marcar_semanas_tc01(sesion):
    """RF-1 paso 4 y RB-4: la última semana publicada viene incompleta y se marca."""
    ultima = marcar_semanas(sesion)

    assert ultima == ULTIMA_COMPLETA
    assert _marca(sesion, INCOMPLETA).completa is False
    assert _marca(sesion, INCOMPLETA).centros_reportados == 2
    assert _marca(sesion, ULTIMA_COMPLETA).completa is True
    assert len(sesion.scalars(select(SemanaCarga)).all()) == 171


def test_recalcular_umbrales_rb3(sesion):
    resumen = recalcular_umbrales(sesion)

    assert resumen["guardados"] == 3
    assert resumen["hasta"] == ULTIMA_COMPLETA  # por defecto, hasta la última semana completa
    vigentes = sesion.scalars(select(UmbralCentro).where(UmbralCentro.vigente.is_(True))).all()
    assert len(vigentes) == 3
    for umbral in vigentes:
        assert umbral.origen is OrigenUmbral.CALCULADO
        assert (umbral.umbral_atencion, umbral.umbral_alerta) == (100, 100)  # sin el COVID
        assert umbral.anios_usados.endswith("(156 semanas)")


def test_el_recalculo_respeta_el_umbral_manual(sesion):
    """RF-9 y pendientes #32: la corrección del administrador se mantiene."""
    admin = sesion.scalars(select(Usuario)).one()
    centro = sesion.scalars(select(CentroSalud.id).order_by(CentroSalud.codigo_deis)).first()
    fijar_umbral_manual(sesion, centro, 80, 120, autor=admin, motivo="Ajuste acordado con la jefatura")

    resumen = recalcular_umbrales(sesion)

    assert resumen["manuales_respetados"] == 1
    assert umbral_vigente(sesion, centro).umbral_alerta == 120


def test_usa_los_parametros_vigentes_ajustados_por_el_administrador(sesion):
    """Opción a (pendientes #31): si el administrador cambia los años del umbral, el recálculo lo usa."""
    admin = sesion.scalars(select(Usuario)).one()
    ajustar_parametro(sesion, "umbrales.anios_umbral", 1, autor=admin, motivo="Prueba con un año")

    recalcular_umbrales(sesion)

    umbral = sesion.scalars(select(UmbralCentro).where(UmbralCentro.vigente.is_(True))).first()
    assert umbral.anios_usados.endswith("(52 semanas)")
