"""Corrida semanal de los lunes (RF-2, RF-3, RF-6, RB-4, RNF-M-3, RNF-M-4, RNF-S-4) sobre ``datos/prueba``.

En los datos de prueba la última semana completa es la del 27/09/2026 (SE 39), así que la corrida del lunes
05/10/2026 pronostica la SE 40 (Gherkin de RF-2).
"""

import copy
from datetime import date

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from sart.db.modelos import (
    Alerta,
    Auditoria,
    CentroSalud,
    ConsultaSemanal,
    Corrida,
    DotacionSugerida,
    Pronostico,
    UmbralCentro,
    Usuario,
)
from sart.db.supuestos import ajustar_parametro, parametros_vigentes
from sart.db.umbrales import fijar_umbral_manual
from sart.dominio.alerta_demanda import pronostico_con_margen
from sart.dominio.pronostico_semanal import esta_desactualizado, semana_en_curso, semana_objetivo
from sart.dominio.roles import Rol
from sart.dominio.valores import EstadoCorrida, TipoCentro
from sart.tareas.semanal import TAREA, ErrorCorridaSemanal, correr_semanal
from sart.tareas.semanas_y_umbrales import recalcular_umbrales

FECHA_CORTE = date(2026, 9, 27)
LUNES = date(2026, 10, 5)
CENTROS_CON_HISTORIA = 14


@pytest.fixture
def sesion(base_prueba):
    with Session(base_prueba) as sesion:
        recalcular_umbrales(sesion)
        sesion.add(Usuario(nombre="Admin", correo="a@demo.sart", rol=Rol.ADMINISTRADOR, hash_contrasena="x"))
        sesion.commit()
        yield sesion


def _admin(sesion) -> Usuario:
    return sesion.scalar(select(Usuario).where(Usuario.rol == Rol.ADMINISTRADOR))


def _vigentes(sesion) -> list[Pronostico]:
    return sesion.scalars(
        select(Pronostico).where(Pronostico.vigente.is_(True)).order_by(Pronostico.centro_id)
    ).all()


# ---------------------------------------------------------------------------
# Lógica pura de fechas (RF-2, RF-3 E2)
# ---------------------------------------------------------------------------
def test_semana_objetivo_es_la_siguiente_a_la_fecha_de_corte():
    assert semana_objetivo(FECHA_CORTE) == date(2026, 10, 4)  # SE 40 de 2026


def test_semana_en_curso_y_pronostico_desactualizado():
    assert semana_en_curso(LUNES) == date(2026, 10, 4)
    assert semana_en_curso(date(2026, 10, 10)) == date(2026, 10, 4)  # sábado: misma semana
    assert not esta_desactualizado(date(2026, 10, 4), LUNES)
    assert esta_desactualizado(date(2026, 10, 4), date(2026, 10, 12))  # la SE 40 ya pasó


# ---------------------------------------------------------------------------
# RF-2: pronóstico de cada centro con historia
# ---------------------------------------------------------------------------
def test_rf2_todo_centro_con_historia_tiene_pronostico(sesion):
    resumen = correr_semanal(sesion, fecha=LUNES)

    assert (resumen.fecha_corte, resumen.anio, resumen.semana) == (FECHA_CORTE, 2026, 40)
    assert not resumen.desactualizado
    pronosticos = _vigentes(sesion)
    assert len(pronosticos) == CENTROS_CON_HISTORIA
    for p in pronosticos:
        assert (p.anio, p.semana, p.fecha_corte) == (2026, 40, FECHA_CORTE)
        assert 0 <= p.limite_inferior <= p.valor <= p.limite_superior
        assert p.version_modelo == "glm-quasipoisson/solo_rezagos/v1"


def test_rf2_correr_dos_veces_deja_un_solo_pronostico_vigente(sesion):
    correr_semanal(sesion, fecha=LUNES)
    correr_semanal(sesion, fecha=LUNES)

    todos = sesion.scalars(select(Pronostico)).all()
    assert len(todos) == 2 * CENTROS_CON_HISTORIA
    assert len(_vigentes(sesion)) == CENTROS_CON_HISTORIA
    assert len({p.centro_id for p in _vigentes(sesion)}) == CENTROS_CON_HISTORIA


def test_rf2_e1_centro_sin_historia_no_se_pronostica_y_se_informa(sesion):
    """Se borran las consultas de un centro salvo 20 semanas: queda con menos de 52 (RF-2 E1, RF-3 E1)."""
    centro = sesion.scalars(select(CentroSalud).order_by(CentroSalud.codigo_deis)).first()
    filas = sesion.scalars(select(ConsultaSemanal).where(ConsultaSemanal.centro_id == centro.id)).all()
    for fila in filas:
        if (fila.anio, fila.semana) < (2026, 20):
            sesion.delete(fila)
    sesion.commit()

    resumen = correr_semanal(sesion, fecha=LUNES)

    assert centro.id not in {p.centro_id for p in _vigentes(sesion)}
    assert centro.nombre in resumen.sin_historia
    assert centro.nombre in resumen.texto()


def test_rb4_la_semana_incompleta_no_se_usa(sesion):
    """Se publican 2 de 14 centros de la SE 40: queda incompleta, la fecha de corte sigue siendo la SE 39 y
    el pronóstico no cambia (no entra ni al ajuste ni a los rezagos)."""
    correr_semanal(sesion, fecha=LUNES)
    antes = {p.centro_id: p.valor for p in _vigentes(sesion)}
    for centro_id in list(antes)[:2]:
        sesion.add(
            ConsultaSemanal(
                centro_id=centro_id,
                anio=2026,
                semana=40,
                causa="ira_alta",
                grupo_edad="de_15_a_64",
                cantidad=5,
            )
        )
    sesion.commit()

    resumen = correr_semanal(sesion, fecha=LUNES)

    assert resumen.fecha_corte == FECHA_CORTE
    despues = {p.centro_id: p.valor for p in _vigentes(sesion)}
    assert despues == pytest.approx(antes)


def test_corrida_queda_en_el_log_rnf_m3(sesion):
    correr_semanal(sesion, fecha=LUNES)

    corrida = sesion.scalars(select(Corrida).where(Corrida.tarea == TAREA)).one()
    assert corrida.estado is EstadoCorrida.EXITOSA
    assert corrida.filas == CENTROS_CON_HISTORIA
    assert "SE 40" in corrida.mensaje


def test_con_pronostico_no_esta_disponible_y_la_corrida_queda_fallida(sesion):
    parametros = copy.deepcopy(parametros_vigentes(sesion))
    parametros["modelo"]["especificacion"] = "con_pronostico"

    with pytest.raises(ErrorCorridaSemanal, match="solo_rezagos"):
        correr_semanal(sesion, fecha=LUNES, parametros=parametros)

    corrida = sesion.scalars(select(Corrida).where(Corrida.tarea == TAREA)).one()
    assert corrida.estado is EstadoCorrida.FALLIDA
    assert sesion.scalars(select(Pronostico)).all() == []


# ---------------------------------------------------------------------------
# RF-3: nivel con el umbral vigente y el margen k
# ---------------------------------------------------------------------------
def _fijar(sesion, centro_id, atencion, alerta):
    fijar_umbral_manual(sesion, centro_id, atencion, alerta, autor=_admin(sesion), motivo="prueba RF-3")


def test_rf3_alerta_atencion_y_normal(sesion):
    correr_semanal(sesion, fecha=LUNES)
    alto, medio, bajo = _vigentes(sesion)[:3]
    _fijar(sesion, alto.centro_id, alto.valor * 0.5, alto.valor * 0.9)  # supera el p90 → ALERTA
    _fijar(sesion, medio.centro_id, medio.valor * 0.9, medio.valor * 10)  # solo supera el p75 → atención
    _fijar(sesion, bajo.centro_id, bajo.valor * 2, bajo.valor * 3)  # normal

    resumen = correr_semanal(sesion, fecha=LUNES)

    nivel = {p.centro_id: p for p in _vigentes(sesion)}
    assert nivel[alto.centro_id].nivel == "alerta"
    assert nivel[medio.centro_id].nivel == "atencion"
    assert nivel[bajo.centro_id].nivel == "normal"
    alertas = {
        a.centro_id: a
        for a in sesion.scalars(
            select(Alerta).where(Alerta.pronostico_id.in_([p.id for p in nivel.values()]))
        )
    }
    assert alertas[alto.centro_id].nivel == "alerta" and alertas[medio.centro_id].nivel == "atencion"
    assert bajo.centro_id not in alertas  # «normal» no genera alerta (§5.1)
    assert "ALERTA" in alertas[alto.centro_id].mensaje
    assert resumen.por_nivel["alerta"] >= 1 and resumen.alertas == len(alertas)


def test_rf3_alerta_solo_por_el_margen_y_cambio_de_k(sesion):
    """Como TC-17 pero de punta a punta: el p90 queda entre el pronóstico y el pronóstico con margen."""
    correr_semanal(sesion, fecha=LUNES)
    p = _vigentes(sesion)[0]
    k = parametros_vigentes(sesion)["regla_alerta"]["k_margen"]
    con_margen = pronostico_con_margen(p.valor, p.limite_superior, k=k, nivel_intervalo=0.9)
    _fijar(sesion, p.centro_id, p.valor * 0.5, (p.valor + con_margen) / 2)

    correr_semanal(sesion, fecha=LUNES)
    nuevo = next(x for x in _vigentes(sesion) if x.centro_id == p.centro_id)
    assert nuevo.nivel == "alerta"
    assert nuevo.k_margen == k and nuevo.valor_con_margen == pytest.approx(con_margen)
    assert nuevo.umbral_id == sesion.scalar(
        select(UmbralCentro.id).where(UmbralCentro.centro_id == p.centro_id, UmbralCentro.vigente.is_(True))
    )

    ajustar_parametro(sesion, "regla_alerta.k_margen", 0, autor=_admin(sesion), motivo="prueba TC-17")
    correr_semanal(sesion, fecha=LUNES)
    sin_margen = next(x for x in _vigentes(sesion) if x.centro_id == p.centro_id)
    assert sin_margen.nivel == "atencion" and sin_margen.k_margen == 0
    assert nuevo.nivel == "alerta"  # lo ya guardado no cambia


def test_rf3_e2_pronostico_desactualizado_no_emite_alertas(sesion):
    correr_semanal(sesion, fecha=LUNES)
    p = _vigentes(sesion)[0]
    _fijar(sesion, p.centro_id, 1, 2)  # quedaría en ALERTA

    resumen = correr_semanal(sesion, fecha=date(2026, 10, 19))  # lunes de la SE 42; la SE 40 ya pasó

    assert resumen.desactualizado and resumen.alertas == 0
    assert "desactualizado" in resumen.texto()
    vigente = next(x for x in _vigentes(sesion) if x.centro_id == p.centro_id)
    assert vigente.nivel == "alerta"  # el nivel se guarda y se muestra…
    assert sesion.scalars(select(Alerta).where(Alerta.pronostico_id == vigente.id)).all() == []  # …sin alerta


def test_rnf_s4_cada_alerta_queda_en_la_auditoria(sesion):
    correr_semanal(sesion, fecha=LUNES)
    p = _vigentes(sesion)[0]
    _fijar(sesion, p.centro_id, 1, 2)

    correr_semanal(sesion, fecha=LUNES)

    alerta = sesion.scalars(select(Alerta).where(Alerta.centro_id == p.centro_id)).one()
    registro = sesion.scalars(select(Auditoria).where(Auditoria.accion == "emision_alerta")).one()
    assert registro.autor_rol == "sistema" and registro.entidad_id == str(alerta.id)
    assert registro.valor_nuevo["nivel"] == "alerta"
    assert registro.valor_nuevo["dotacion"]["profesionales"] >= 1


# ---------------------------------------------------------------------------
# RF-6: dotación guardada con los supuestos usados
# ---------------------------------------------------------------------------
def test_rf6_dotacion_guardada_con_sus_supuestos(sesion):
    correr_semanal(sesion, fecha=LUNES)

    for p in _vigentes(sesion):
        d = sesion.get(DotacionSugerida, p.id)
        assert d.profesionales >= 1 and d.espera_media_min <= 30
        assert set(d.supuestos) == {
            "minutos_por_atencion",
            "factor_hora_punta",
            "horas_funcionamiento_semana",
            "espera_objetivo_min",
            "supuestos_validados",
        }
        assert d.supuestos["supuestos_validados"] is False  # RF-6 E1: «por validar»
        if d.profesionales > 1:
            assert d.espera_con_uno_menos_min is None or d.espera_con_uno_menos_min > d.espera_media_min


def test_rf6_la_dotacion_pasada_no_cambia_si_se_ajusta_un_supuesto(sesion):
    correr_semanal(sesion, fecha=LUNES)
    antes = {
        p.id: (d.profesionales, dict(d.supuestos))
        for p in _vigentes(sesion)
        if (d := sesion.get(DotacionSugerida, p.id))
    }

    ajustar_parametro(sesion, "dotacion.minutos_por_atencion", 40, autor=_admin(sesion), motivo="prueba RF-6")
    sesion.expire_all()

    for pronostico_id, (profesionales, supuestos) in antes.items():
        d = sesion.get(DotacionSugerida, pronostico_id)
        assert (d.profesionales, d.supuestos) == (profesionales, supuestos)
        assert d.supuestos["minutos_por_atencion"] == 15

    correr_semanal(sesion, fecha=LUNES)  # la corrida siguiente sí usa el ajuste
    nuevos = [sesion.get(DotacionSugerida, p.id) for p in _vigentes(sesion)]
    assert all(d.supuestos["minutos_por_atencion"] == 40 for d in nuevos)


def test_rf6_sur_sin_horas_definidas_queda_sin_dotacion_y_se_informa(sesion):
    """``dotacion.horas_funcionamiento_semana.SUR`` es null: hay pronóstico y nivel, pero no dotación."""
    centro = sesion.scalars(select(CentroSalud).order_by(CentroSalud.codigo_deis)).first()
    centro.tipo = TipoCentro.SUR
    sesion.commit()

    resumen = correr_semanal(sesion, fecha=LUNES)

    p = next(x for x in _vigentes(sesion) if x.centro_id == centro.id)
    assert p.nivel is not None
    assert sesion.get(DotacionSugerida, p.id) is None
    assert centro.nombre in resumen.sin_dotacion
    assert len(_vigentes(sesion)) == CENTROS_CON_HISTORIA


def test_rf2_corrida_real_pronostica_31_centros(archivo_base_real, tmp_path):
    import shutil

    from sqlalchemy import create_engine

    copia = tmp_path / "real.db"
    shutil.copyfile(archivo_base_real, copia)
    motor = create_engine(f"sqlite:///{copia.as_posix()}")
    try:
        with Session(motor) as sesion:
            recalcular_umbrales(sesion, hasta=FECHA_CORTE)
            correr_semanal(sesion, fecha=LUNES)
            assert len(_vigentes(sesion)) == 31
    finally:
        motor.dispose()
