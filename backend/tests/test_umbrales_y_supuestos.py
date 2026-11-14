"""Umbrales por centro (RB-3, RF-9) y supuestos ajustados (RF-9, opción a), con auditoría (RNF-S-4)."""

import pytest
from sqlalchemy import create_engine, event, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from sart.configuracion import RAIZ_REPOSITORIO
from sart.db.modelos import Auditoria, Base, CentroSalud, ParametroAjustado, UmbralCentro, Usuario
from sart.db.supuestos import ajustar_parametro, parametros_vigentes
from sart.db.umbrales import ErrorUmbral, fijar_umbral_manual, guardar_umbrales_calculados, umbral_vigente
from sart.dominio.roles import Rol
from sart.dominio.supuestos import ErrorAjuste
from sart.dominio.valores import OrigenUmbral
from sart.tareas.carga import cargar_catalogo

ESTABLECIMIENTOS = RAIZ_REPOSITORIO / "datos" / "prueba" / "crudos" / "establecimientos.csv"


@pytest.fixture
def sesion():
    motor = create_engine("sqlite://")
    event.listen(motor, "connect", lambda conexion, _: conexion.execute("PRAGMA foreign_keys=ON"))
    Base.metadata.create_all(motor)
    with Session(motor) as sesion:
        cargar_catalogo(sesion, ESTABLECIMIENTOS)
        sesion.add(Usuario(nombre="Admin", correo="a@demo.sart", rol=Rol.ADMINISTRADOR, hash_contrasena="x"))
        sesion.commit()
        yield sesion
    motor.dispose()


def _admin(sesion) -> Usuario:
    return sesion.scalars(select(Usuario)).one()


def _centros(sesion) -> list[CentroSalud]:
    return sesion.scalars(select(CentroSalud).order_by(CentroSalud.codigo_deis)).all()


def _auditorias(sesion, accion) -> list[Auditoria]:
    return sesion.scalars(select(Auditoria).where(Auditoria.accion == accion).order_by(Auditoria.id)).all()


# --- Umbrales -----------------------------------------------------------------
def test_guardar_calculados_deja_uno_vigente_por_centro(sesion):
    centro = _centros(sesion)[0]
    guardar_umbrales_calculados(sesion, {centro.id: (400.0, 500.0)}, anios_usados="2023–2025")
    guardar_umbrales_calculados(sesion, {centro.id: (410.0, 520.0)}, anios_usados="2024–2026")

    vigente = umbral_vigente(sesion, centro.id)
    assert (vigente.umbral_atencion, vigente.umbral_alerta, vigente.anios_usados) == (
        410.0,
        520.0,
        "2024–2026",
    )
    assert sesion.scalar(select(func.count()).select_from(UmbralCentro)) == 2  # se guarda la historia


def test_fijar_umbral_manual_queda_auditado(sesion):
    """RF-9: «Dado un cambio de umbral, cuando se guarda, entonces queda registrado»; RNF-S-4."""
    centro = _centros(sesion)[0]
    guardar_umbrales_calculados(sesion, {centro.id: (400.0, 500.0)}, anios_usados="2023–2025")

    fijar_umbral_manual(
        sesion, centro.id, 420.0, 510.0, autor=_admin(sesion), motivo="Ajuste acordado con jefatura"
    )

    vigente = umbral_vigente(sesion, centro.id)
    assert vigente.origen is OrigenUmbral.MANUAL
    [registro] = _auditorias(sesion, "cambio_umbral")
    assert registro.autor_rol == "administrador"
    assert registro.entidad_id == str(centro.id)
    assert registro.valor_anterior == {
        "umbral_atencion": 400.0,
        "umbral_alerta": 500.0,
        "origen": "calculado",
    }
    assert registro.valor_nuevo == {"umbral_atencion": 420.0, "umbral_alerta": 510.0, "origen": "manual"}
    assert registro.motivo == "Ajuste acordado con jefatura"


@pytest.mark.parametrize(
    ("atencion", "alerta", "motivo", "mensaje"),
    [(500.0, 400.0, "x", "menor"), (-1.0, 400.0, "x", "negativo"), (400.0, 500.0, "  ", "motivo")],
)
def test_umbral_manual_invalido(sesion, atencion, alerta, motivo, mensaje):
    with pytest.raises(ErrorUmbral, match=mensaje):
        fijar_umbral_manual(
            sesion, _centros(sesion)[0].id, atencion, alerta, autor=_admin(sesion), motivo=motivo
        )
    assert sesion.scalar(select(func.count()).select_from(UmbralCentro)) == 0


def test_el_recalculo_anual_no_pisa_un_umbral_manual(sesion):
    """La corrección del administrador se respeta hasta que él la quite (pendientes #21)."""
    manual, calculado = _centros(sesion)[:2]
    fijar_umbral_manual(sesion, manual.id, 420.0, 510.0, autor=_admin(sesion), motivo="Ajuste local")

    resumen = guardar_umbrales_calculados(
        sesion, {manual.id: (300.0, 350.0), calculado.id: (200.0, 260.0)}, anios_usados="2024–2026"
    )

    assert resumen == {"guardados": 1, "manuales_respetados": 1}
    assert umbral_vigente(sesion, manual.id).umbral_atencion == 420.0
    assert umbral_vigente(sesion, calculado.id).umbral_atencion == 200.0


def test_la_base_impide_dos_umbrales_vigentes_del_mismo_centro(sesion):
    centro_id = _centros(sesion)[0].id
    sesion.add_all(
        [
            UmbralCentro(
                centro_id=centro_id, umbral_atencion=1, umbral_alerta=2, origen=OrigenUmbral.CALCULADO
            ),
            UmbralCentro(
                centro_id=centro_id, umbral_atencion=1, umbral_alerta=3, origen=OrigenUmbral.CALCULADO
            ),
        ]
    )
    with pytest.raises(IntegrityError):
        sesion.commit()


# --- Supuestos (opción a) ---------------------------------------------------
def test_sin_ajustes_los_vigentes_son_los_del_yaml(sesion):
    assert parametros_vigentes(sesion)["regla_alerta"]["k_margen"] == 0.4


def test_ajustar_un_supuesto_rige_y_queda_auditado(sesion):
    ajustar_parametro(sesion, "regla_alerta.k_margen", 0.5, autor=_admin(sesion), motivo="Recalibración 2025")

    assert parametros_vigentes(sesion)["regla_alerta"]["k_margen"] == 0.5
    [registro] = _auditorias(sesion, "cambio_parametro")
    assert (registro.entidad_id, registro.valor_anterior, registro.valor_nuevo) == (
        "regla_alerta.k_margen",
        0.4,
        0.5,
    )
    assert registro.motivo == "Recalibración 2025"


def test_un_segundo_ajuste_reemplaza_al_primero_y_guarda_la_historia(sesion):
    ajustar_parametro(sesion, "regla_alerta.k_margen", 0.5, autor=_admin(sesion), motivo="Primero")
    ajustar_parametro(sesion, "regla_alerta.k_margen", 0.45, autor=_admin(sesion), motivo="Segundo")

    assert parametros_vigentes(sesion)["regla_alerta"]["k_margen"] == 0.45
    assert sesion.scalar(select(func.count()).select_from(ParametroAjustado)) == 2
    assert [r.valor_anterior for r in _auditorias(sesion, "cambio_parametro")] == [0.4, 0.5]


def test_ajuste_invalido_no_guarda_nada(sesion):
    with pytest.raises(ErrorAjuste):
        ajustar_parametro(sesion, "horarios.ingesta", "04:00", autor=_admin(sesion), motivo="No permitido")
    with pytest.raises(ErrorAjuste, match="motivo"):
        ajustar_parametro(sesion, "regla_alerta.k_margen", 0.5, autor=_admin(sesion), motivo="")

    assert sesion.scalar(select(func.count()).select_from(ParametroAjustado)) == 0
    assert sesion.scalar(select(func.count()).select_from(Auditoria)) == 0
