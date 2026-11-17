"""TC-15 · Esquema de la base, contrato OpenAPI y exportación CSV (RF-11, RNF-S-5, C-2).

Criterio: 0 registros de pacientes; contrato válido; CSV UTF-8 solo con los centros del usuario. Sobre
``datos/prueba``, con la corrida del lunes 05/10/2026 (como ``test_tc09_rf7_estado_centros.py``).
"""

import csv
import io
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
from sart.db.modelos import Auditoria, Base, CentroSalud, Usuario, UsuarioCentro
from sart.dominio.exportacion import COLUMNAS, FUENTE
from sart.dominio.roles import Rol
from sart.tareas.semanal import correr_semanal
from sart.tareas.semanas_y_umbrales import recalcular_umbrales

LUNES = date(2026, 10, 5)
PROPIO, AJENO = 100001, 100002
CORREOS = {Rol.JEFATURA: "j@demo.sart", Rol.SUBDIRECTOR: "s@demo.sart", Rol.ADMINISTRADOR: "a@demo.sart"}
# Palabras que delatarían datos de pacientes en el esquema o en el CSV (RNF-S-5). La dirección de un centro
# o de una estación es pública y no cuenta.
DE_PACIENTES = ("paciente", "rut", "run_", "nacimiento", "diagnostico", "ficha", "prevision", "sexo")


@pytest.fixture(scope="module")
def archivo_con_corrida(archivo_base_prueba, tmp_path_factory):
    ruta = tmp_path_factory.mktemp("exportacion") / "sart.db"
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


def _leer(respuesta) -> list[dict[str, str]]:
    assert respuesta.status_code == 200
    assert respuesta.headers["content-type"].startswith("text/csv")
    assert "attachment" in respuesta.headers["content-disposition"]
    assert respuesta.content.startswith(b"\xef\xbb\xbf")  # UTF-8 con BOM: Excel abre bien las tildes
    texto = respuesta.content.decode("utf-8-sig")
    return list(csv.DictReader(io.StringIO(texto), delimiter=";"))


# ---------------------------------------------------------------------------
# CSV solo con los centros del usuario
# ---------------------------------------------------------------------------
def test_tc15_sin_sesion_401(api):
    assert api.get("/exportar/centros.csv").status_code == 401


def test_tc15_la_jefatura_exporta_solo_sus_centros(api, motor):
    filas = _leer(_como(api, motor, Rol.JEFATURA).get("/exportar/centros.csv"))

    assert [f["codigo_deis"] for f in filas] == [str(PROPIO)]
    [fila] = filas
    assert list(fila) == COLUMNAS
    assert fila["semana_epidemiologica"] == "40"
    assert fila["nivel"] in {"normal", "atención", "ALERTA"}
    assert fila["fuente"] == FUENTE and "CC BY-NC" in FUENTE


def test_tc15_las_cifras_son_las_de_rf7(api, motor):
    cliente = _como(api, motor, Rol.JEFATURA)
    estado = cliente.get(f"/centros/{PROPIO}/estado").json()
    [fila] = _leer(cliente.get(f"/exportar/centros.csv?codigo_deis={PROPIO}"))

    assert float(fila["pronostico_consultas"].replace(",", ".")) == pytest.approx(
        estado["pronostico"]["valor"], abs=0.05
    )
    assert float(fila["limite_superior_90"].replace(",", ".")) == pytest.approx(
        estado["pronostico"]["limite_superior"], abs=0.05
    )


def test_tc15_centro_ajeno_403_y_queda_registrado(api, motor):
    cliente = _como(api, motor, Rol.JEFATURA)
    assert cliente.get(f"/exportar/centros.csv?codigo_deis={AJENO}").status_code == 403
    with Session(motor) as sesion:
        acciones = list(sesion.scalars(select(Auditoria.accion)))
    assert "acceso_denegado" in acciones


def test_tc15_el_subdirector_exporta_la_red_y_queda_en_la_auditoria(api, motor):
    filas = _leer(_como(api, motor, Rol.SUBDIRECTOR).get("/exportar/centros.csv"))
    assert len(filas) == 14
    with Session(motor) as sesion:
        registro = sesion.scalar(select(Auditoria).where(Auditoria.accion == "exportar_csv"))
    assert registro.valor_nuevo == {"centros": 14}
    assert registro.autor_rol == "subdirector"


def test_tc15_el_csv_no_trae_datos_de_pacientes_ni_de_cuentas(api, motor):
    texto = _como(api, motor, Rol.SUBDIRECTOR).get("/exportar/centros.csv").content.decode("utf-8-sig")
    encabezado = texto.splitlines()[0].lower()
    assert not any(p in encabezado for p in DE_PACIENTES)
    assert "@" not in texto and "Cuenta" not in texto


# ---------------------------------------------------------------------------
# Esquema y contrato
# ---------------------------------------------------------------------------
def test_tc15_el_esquema_no_tiene_columnas_de_pacientes():
    columnas = [f"{t.name}.{c.name}" for t in Base.metadata.tables.values() for c in t.columns]
    assert not [c for c in columnas if any(p in c.lower() for p in DE_PACIENTES)]
    assert not any("paciente" in t for t in Base.metadata.tables)


def test_tc15_contrato_openapi_valido():
    contrato = app.openapi()
    assert contrato["openapi"].startswith("3.")
    assert "/exportar/centros.csv" in contrato["paths"]
    assert "text/csv" in contrato["paths"]["/exportar/centros.csv"]["get"]["responses"]["200"]["content"]
    for ruta, metodos in contrato["paths"].items():
        for metodo, operacion in metodos.items():
            assert operacion.get("responses"), f"{metodo.upper()} {ruta} sin respuestas"
    for nombre in contrato.get("components", {}).get("schemas", {}):
        assert not any(p in nombre.lower() for p in DE_PACIENTES)
