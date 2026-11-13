"""TC-16 · Alta de cuenta sin aceptación registrada de la finalidad de §5.3 (RF-16).

Escenario: Alta sin aceptación
  Dado un funcionario que no ha aceptado la finalidad declarada en §5.3
  Cuando el administrador intenta crear su cuenta
  Entonces el sistema no la crea
  Y no almacena su nombre ni su correo
"""

import io
from datetime import UTC, datetime

import pytest
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session

from sart import cuentas as cli
from sart.db.cuentas import dar_de_alta
from sart.db.modelos import AceptacionFinalidad, Base, Usuario
from sart.dominio.contrasenas import verificar
from sart.dominio.cuentas import Aceptacion, ErrorAltaCuenta, SinAceptacion
from sart.parametros import cargar_parametros

NOMBRE = "Funcionaria Sin Aceptar"
CORREO = "sin.aceptar@demo.sart"
CLAVE = "una clave suficientemente larga"


@pytest.fixture
def url_sqlite(tmp_path, monkeypatch):
    url = f"sqlite:///{(tmp_path / 'sart.db').as_posix()}"
    motor = create_engine(url)
    Base.metadata.create_all(motor)
    motor.dispose()
    monkeypatch.setenv("DATABASE_URL", url)
    return url


def _nada_guardado(url: str) -> bool:
    motor = create_engine(url)
    try:
        with Session(motor) as sesion:
            usuarios = sesion.scalar(select(func.count()).select_from(Usuario))
            aceptaciones = sesion.scalar(select(func.count()).select_from(AceptacionFinalidad))
    finally:
        motor.dispose()
    return usuarios == 0 and aceptaciones == 0


def _vigente() -> str:
    return cargar_parametros()["cuentas"]["version_texto_finalidad"]


def test_tc16_sin_aceptacion_no_se_crea_ni_se_guarda_nada(url_sqlite):
    motor = create_engine(url_sqlite)
    try:
        with Session(motor) as sesion, pytest.raises(SinAceptacion):
            dar_de_alta(
                sesion, nombre=NOMBRE, correo=CORREO, rol="jefatura", contrasena=CLAVE, aceptacion=None
            )
    finally:
        motor.dispose()

    assert _nada_guardado(url_sqlite)


def test_tc16_por_comando_sin_acepta_finalidad(url_sqlite, monkeypatch, capsys):
    monkeypatch.setattr("sys.stdin", io.StringIO(CLAVE + "\n"))

    codigo = cli.main(
        ["crear", "--nombre", NOMBRE, "--correo", CORREO, "--rol", "jefatura", "--contrasena-stdin"]
    )

    assert codigo != 0
    assert "acepta" in capsys.readouterr().err.lower()
    assert _nada_guardado(url_sqlite)


def test_con_aceptacion_se_crea_la_cuenta_con_su_constancia(url_sqlite):
    """RF-16 flujo principal: la aceptación queda con fecha, hora y versión del texto."""
    aceptacion = Aceptacion(version_texto=_vigente(), aceptada_en=datetime(2026, 11, 13, 9, tzinfo=UTC))
    motor = create_engine(url_sqlite)
    try:
        with Session(motor) as sesion:
            usuario = dar_de_alta(
                sesion, nombre=NOMBRE, correo=CORREO, rol="jefatura", contrasena=CLAVE, aceptacion=aceptacion
            )
            assert usuario.id is not None
            assert verificar(usuario.hash_contrasena, CLAVE)
            assert usuario.aceptaciones[0].version_texto == _vigente()
    finally:
        motor.dispose()


def test_por_comando_con_acepta_finalidad(url_sqlite, monkeypatch, capsys):
    monkeypatch.setattr("sys.stdin", io.StringIO(CLAVE + "\n"))

    codigo = cli.main(
        [
            "crear",
            "--nombre",
            NOMBRE,
            "--correo",
            CORREO,
            "--rol",
            "subdirector",
            "--acepta-finalidad",
            "--contrasena-stdin",
        ]
    )

    assert codigo == 0
    assert CORREO in capsys.readouterr().out
    assert not _nada_guardado(url_sqlite)


def test_correo_repetido_da_error_claro_y_no_duplica(url_sqlite):
    aceptacion = Aceptacion(version_texto=_vigente(), aceptada_en=datetime.now(UTC))
    motor = create_engine(url_sqlite)
    try:
        with Session(motor) as sesion:
            dar_de_alta(
                sesion, nombre=NOMBRE, correo=CORREO, rol="jefatura", contrasena=CLAVE, aceptacion=aceptacion
            )
            with pytest.raises(ErrorAltaCuenta, match="Ya existe"):
                dar_de_alta(
                    sesion,
                    nombre="Otra",
                    correo=CORREO.upper(),
                    rol="jefatura",
                    contrasena=CLAVE,
                    aceptacion=aceptacion,
                )
            assert sesion.scalar(select(func.count()).select_from(Usuario)) == 1
    finally:
        motor.dispose()
