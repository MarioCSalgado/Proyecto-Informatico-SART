"""Asignar centros a una cuenta por comando (RF-9) mientras no exista la pantalla de administración."""

import io

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, selectinload

from sart import cuentas as cli
from sart.configuracion import RAIZ_REPOSITORIO
from sart.db.modelos import Base, Usuario
from sart.tareas.carga import cargar_catalogo

ESTABLECIMIENTOS = RAIZ_REPOSITORIO / "datos" / "prueba" / "crudos" / "establecimientos.csv"
CLAVE = "una clave suficientemente larga"


@pytest.fixture
def url_con_catalogo(tmp_path, monkeypatch):
    url = f"sqlite:///{(tmp_path / 'sart.db').as_posix()}"
    motor = create_engine(url)
    Base.metadata.create_all(motor)
    with Session(motor) as sesion:
        cargar_catalogo(sesion, ESTABLECIMIENTOS)
    motor.dispose()
    monkeypatch.setenv("DATABASE_URL", url)
    monkeypatch.setattr("sys.stdin", io.StringIO(CLAVE + "\n"))
    argumentos = ["crear", "--nombre", "Jefatura", "--correo", "j@demo.sart", "--rol", "jefatura"]
    assert cli.main([*argumentos, "--acepta-finalidad", "--contrasena-stdin"]) == 0
    return url


def _centros(url) -> list[int]:
    motor = create_engine(url)
    try:
        with Session(motor) as sesion:
            usuario = sesion.scalars(select(Usuario).options(selectinload(Usuario.centros))).one()
            return sorted(c.codigo_deis for c in usuario.centros)
    finally:
        motor.dispose()


def test_asignar_un_centro_por_su_codigo_deis(url_con_catalogo, capsys):
    capsys.readouterr()

    assert cli.main(["asignar-centro", "--correo", "j@demo.sart", "--centro", "100001"]) == 0
    assert "Centro de prueba 01" in capsys.readouterr().out
    assert _centros(url_con_catalogo) == [100001]


def test_asignar_dos_veces_no_duplica(url_con_catalogo):
    cli.main(["asignar-centro", "--correo", "j@demo.sart", "--centro", "100001"])
    cli.main(["asignar-centro", "--correo", "j@demo.sart", "--centro", "100001"])
    cli.main(["asignar-centro", "--correo", "j@demo.sart", "--centro", "100002"])

    assert _centros(url_con_catalogo) == [100001, 100002]


def test_centro_inexistente(url_con_catalogo, capsys):
    assert cli.main(["asignar-centro", "--correo", "j@demo.sart", "--centro", "1"]) == 1
    assert "No existe el centro" in capsys.readouterr().err
