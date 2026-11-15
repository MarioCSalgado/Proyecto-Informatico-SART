"""TC-09 · Acceso por rol (RNF-S-2) y RF-7 · Estado de los centros, sobre ``datos/prueba``.

La corrida semanal del lunes 05/10/2026 deja un pronóstico de la SE 40 para los 14 centros. La jefatura tiene
asignado el centro 100001; el subdirector y el administrador ven todos. Las sesiones se arman con el token
directamente (el MFA del administrador ya está probado en ``test_auth_mfa.py``).
"""

import shutil
from datetime import date, timedelta

import pytest
from conftest import SECRETO_DE_PRUEBA
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from sart.api.app import app
from sart.api.centros import fecha_de_hoy
from sart.api.dependencias import obtener_sesion_db
from sart.api.tokens import NOMBRE_COOKIE, emitir_token
from sart.db.modelos import (
    Auditoria,
    CentroSalud,
    Medicion,
    Pronostico,
    UmbralCentro,
    Usuario,
    UsuarioCentro,
)
from sart.db.umbrales import fijar_umbral_manual
from sart.dominio.roles import Rol
from sart.tareas.semanal import correr_semanal
from sart.tareas.semanas_y_umbrales import recalcular_umbrales

LUNES = date(2026, 10, 5)
PROPIO, AJENO = 100001, 100002
CORREOS = {Rol.JEFATURA: "j@demo.sart", Rol.SUBDIRECTOR: "s@demo.sart", Rol.ADMINISTRADOR: "a@demo.sart"}


@pytest.fixture(scope="module")
def archivo_con_corrida(archivo_base_prueba, tmp_path_factory):
    ruta = tmp_path_factory.mktemp("estado") / "sart.db"
    shutil.copyfile(archivo_base_prueba, ruta)
    motor = create_engine(f"sqlite:///{ruta.as_posix()}")
    with Session(motor) as sesion:
        recalcular_umbrales(sesion)
        correr_semanal(sesion, fecha=LUNES)
        for rol, correo in CORREOS.items():
            sesion.add(Usuario(nombre=f"Cuenta {rol.value}", correo=correo, rol=rol, hash_contrasena="x"))
        sesion.commit()
        jefa = sesion.scalar(select(Usuario).where(Usuario.rol == Rol.JEFATURA))
        propio = sesion.scalar(select(CentroSalud).where(CentroSalud.codigo_deis == PROPIO))
        sesion.add(UsuarioCentro(usuario_id=jefa.id, centro_id=propio.id))
        sesion.commit()
    motor.dispose()
    return ruta


@pytest.fixture
def motor(archivo_con_corrida, tmp_path):
    copia = tmp_path / "sart.db"
    shutil.copyfile(archivo_con_corrida, copia)
    motor = create_engine(f"sqlite:///{copia.as_posix()}")
    yield motor
    motor.dispose()


@pytest.fixture
def api(motor, monkeypatch):
    monkeypatch.setenv("JWT_SECRET", SECRETO_DE_PRUEBA)

    def sesion_de_prueba():
        with Session(motor) as sesion:
            yield sesion

    app.dependency_overrides[obtener_sesion_db] = sesion_de_prueba
    app.dependency_overrides[fecha_de_hoy] = lambda: LUNES
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.pop(obtener_sesion_db, None)
        app.dependency_overrides.pop(fecha_de_hoy, None)


def _como(api, motor, rol: Rol) -> TestClient:
    with Session(motor) as sesion:
        usuario = sesion.scalar(select(Usuario).where(Usuario.correo == CORREOS[rol]))
        token = emitir_token(
            usuario_id=usuario.id, rol=rol, secreto=SECRETO_DE_PRUEBA, duracion=timedelta(hours=1)
        )
    api.cookies.set(NOMBRE_COOKIE, token)
    return api


# ---------------------------------------------------------------------------
# TC-09: 0 accesos indebidos
# ---------------------------------------------------------------------------
def test_tc09_sin_sesion_401(api):
    assert api.get("/centros/estado").status_code == 401
    assert api.get(f"/centros/{PROPIO}/estado").status_code == 401


def test_tc09_la_jefatura_ve_solo_sus_centros(api, motor):
    respuesta = _como(api, motor, Rol.JEFATURA).get("/centros/estado")

    assert respuesta.status_code == 200
    assert [c["centro"]["codigo_deis"] for c in respuesta.json()] == [PROPIO]
    assert api.get(f"/centros/{PROPIO}/estado").status_code == 200


def test_tc09_rf7_e2_centro_ajeno_403_y_queda_registrado(api, motor):
    cliente = _como(api, motor, Rol.JEFATURA)

    assert cliente.get(f"/centros/{AJENO}/estado").status_code == 403
    assert cliente.get("/centros/999999/estado").status_code == 403  # no revela si el centro existe

    with Session(motor) as sesion:
        registros = sesion.scalars(select(Auditoria).where(Auditoria.accion == "acceso_denegado")).all()
    assert [r.entidad_id for r in registros] == [str(AJENO), "999999"]
    assert all(r.autor_rol == "jefatura" for r in registros)


@pytest.mark.parametrize("rol", [Rol.SUBDIRECTOR, Rol.ADMINISTRADOR])
def test_tc09_subdirector_y_administrador_ven_todos(api, motor, rol):
    cliente = _como(api, motor, rol)

    assert len(cliente.get("/centros/estado").json()) == 14
    assert cliente.get(f"/centros/{AJENO}/estado").status_code == 200
    assert cliente.get("/centros/999999/estado").status_code == 404


# ---------------------------------------------------------------------------
# RF-7: qué se muestra
# ---------------------------------------------------------------------------
def test_rf7_estado_con_pronostico_intervalo_umbrales_dotacion_y_mp25(api, motor):
    estado = _como(api, motor, Rol.JEFATURA).get(f"/centros/{PROPIO}/estado").json()

    p = estado["pronostico"]
    assert (p["anio"], p["semana"], p["fecha_corte"], p["inicio_semana"]) == (
        2026,
        40,
        "2026-09-27",
        "2026-10-04",
    )
    assert p["limite_inferior"] <= p["valor"] <= p["limite_superior"]
    assert p["nivel"] in ("normal", "atencion", "alerta")
    assert p["desactualizado"] is False and p["datos_antiguos"] is False
    assert p["umbrales"]["alerta"] >= p["umbrales"]["atencion"] > 0
    assert estado["dotacion"]["profesionales"] >= 1 and estado["dotacion"]["por_validar"] is True
    assert estado["mp25"]["estado"] == "ok" and estado["mp25"]["nivel"]["clave"]
    semanas = estado["ultimas_semanas"]
    assert len(semanas) == 12 and semanas[-1]["inicio"] == "2026-09-27"
    assert all(s["nivel_observado"] in ("normal", "atencion", "alerta") for s in semanas)


def test_rnf_s5_sin_datos_de_pacientes_ni_de_cuentas(api, motor):
    """Solo cifras agregadas y datos del centro: ninguna clave de persona en la respuesta."""
    texto = _como(api, motor, Rol.SUBDIRECTOR).get("/centros/estado").text.lower()
    for prohibida in ("paciente", "rut", "correo", "usuario", "nombre_usuario", "@"):
        assert prohibida not in texto


def test_rf7_la_red_va_ordenada_alerta_atencion_normal(api, motor):
    with Session(motor) as sesion:
        admin = sesion.scalar(select(Usuario).where(Usuario.rol == Rol.ADMINISTRADOR))
        vigentes = sesion.scalars(select(Pronostico).where(Pronostico.vigente.is_(True))).all()
        p = vigentes[5]
        fijar_umbral_manual(sesion, p.centro_id, 1, 2, autor=admin, motivo="prueba RF-7")
        correr_semanal(sesion, fecha=LUNES)

    niveles = [
        c["pronostico"]["nivel"] for c in _como(api, motor, Rol.SUBDIRECTOR).get("/centros/estado").json()
    ]
    assert niveles[0] == "alerta"
    orden = {"alerta": 0, "atencion": 1, "normal": 2}
    assert [orden[n] for n in niveles] == sorted(orden[n] for n in niveles)


def test_rf7_muestra_los_umbrales_usados_no_los_vigentes(api, motor):
    """#39: si el administrador cambia el umbral después de la corrida, lo informado no cambia."""
    cliente = _como(api, motor, Rol.SUBDIRECTOR)
    antes = cliente.get(f"/centros/{PROPIO}/estado").json()["pronostico"]["umbrales"]
    with Session(motor) as sesion:
        admin = sesion.scalar(select(Usuario).where(Usuario.rol == Rol.ADMINISTRADOR))
        centro = sesion.scalar(select(CentroSalud).where(CentroSalud.codigo_deis == PROPIO))
        fijar_umbral_manual(sesion, centro.id, 5, 6, autor=admin, motivo="prueba #39")
        assert (
            sesion.scalar(
                select(UmbralCentro.umbral_alerta).where(
                    UmbralCentro.centro_id == centro.id, UmbralCentro.vigente.is_(True)
                )
            )
            == 6
        )

    assert cliente.get(f"/centros/{PROPIO}/estado").json()["pronostico"]["umbrales"] == antes


def test_rf7_e1_y_rf3_e2_avisos_con_datos_viejos(api, motor):
    app.dependency_overrides[fecha_de_hoy] = lambda: date(2026, 11, 14)
    p = _como(api, motor, Rol.JEFATURA).get(f"/centros/{PROPIO}/estado").json()["pronostico"]

    assert p["datos_antiguos"] is True  # E1: más de 8 días desde el cierre de la semana de corte
    assert p["desactualizado"] is True  # RF-3 E2: la SE 40 ya no es la semana en curso


def test_rf7_e3_rb5_sin_mediciones_recientes_datos_insuficientes(api, motor):
    with Session(motor) as sesion:
        for m in sesion.scalars(select(Medicion).where(Medicion.tipo == "mp25")).all():
            if m.fecha_hora.date() >= date(2026, 9, 25):
                sesion.delete(m)
        sesion.commit()

    mp = _como(api, motor, Rol.JEFATURA).get(f"/centros/{PROPIO}/estado").json()["mp25"]

    assert mp["estado"] == "datos_insuficientes"
    assert mp["fecha"] is not None and mp["fecha"] < "2026-09-28"  # la última medición válida


def test_rf7_centro_sin_pronostico_igual_aparece(api, motor):
    with Session(motor) as sesion:
        centro = sesion.scalar(select(CentroSalud).where(CentroSalud.codigo_deis == PROPIO))
        for p in sesion.scalars(select(Pronostico).where(Pronostico.centro_id == centro.id)).all():
            sesion.delete(p)
        sesion.commit()

    estado = _como(api, motor, Rol.JEFATURA).get(f"/centros/{PROPIO}/estado").json()

    assert estado["pronostico"] is None and estado["dotacion"] is None
    assert len(estado["ultimas_semanas"]) == 12  # la historia observada se muestra igual
