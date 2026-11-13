"""Comandos para activar, confirmar y reiniciar el MFA de un administrador (RNF-S-1)."""

import io
import re

import pyotp
import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from sart import cuentas as cli
from sart.db.modelos import Base, Usuario

ADMIN = "admin@demo.sart"
CLAVE = "una clave suficientemente larga"


@pytest.fixture
def url_sqlite(tmp_path, monkeypatch):
    url = f"sqlite:///{(tmp_path / 'sart.db').as_posix()}"
    motor = create_engine(url)
    Base.metadata.create_all(motor)
    motor.dispose()
    monkeypatch.setenv("DATABASE_URL", url)
    return url


def _crear(rol, correo=ADMIN, monkeypatch=None):
    monkeypatch.setattr("sys.stdin", io.StringIO(CLAVE + "\n"))
    argumentos = ["crear", "--nombre", "Cuenta", "--correo", correo, "--rol", rol]
    assert cli.main([*argumentos, "--acepta-finalidad", "--contrasena-stdin"]) == 0


def _usuario(url, correo=ADMIN) -> Usuario:
    motor = create_engine(url)
    try:
        with Session(motor) as sesion:
            usuario = sesion.scalars(select(Usuario).where(Usuario.correo == correo)).one()
            sesion.expunge(usuario)
            return usuario
    finally:
        motor.dispose()


def _secreto_impreso(salida: str) -> str:
    return re.search(r"secret=([A-Z2-7]+)", salida).group(1)


def test_activar_y_confirmar(url_sqlite, monkeypatch, capsys):
    _crear("administrador", monkeypatch=monkeypatch)
    capsys.readouterr()

    assert cli.main(["activar-mfa", "--correo", ADMIN]) == 0
    salida = capsys.readouterr().out
    secreto = _secreto_impreso(salida)
    assert "confirmar-mfa" in salida
    assert _usuario(url_sqlite).mfa_activado_en is None

    assert cli.main(["confirmar-mfa", "--correo", ADMIN, "--codigo", pyotp.TOTP(secreto).now()]) == 0
    assert _usuario(url_sqlite).mfa_activado_en is not None


def test_confirmar_con_codigo_malo_no_activa(url_sqlite, monkeypatch, capsys):
    _crear("administrador", monkeypatch=monkeypatch)
    cli.main(["activar-mfa", "--correo", ADMIN])
    secreto = _secreto_impreso(capsys.readouterr().out)
    malo = "000000" if pyotp.TOTP(secreto).now() != "000000" else "111111"

    assert cli.main(["confirmar-mfa", "--correo", ADMIN, "--codigo", malo]) == 1
    assert "incorrecto" in capsys.readouterr().err.lower()
    assert _usuario(url_sqlite).mfa_activado_en is None


def test_activar_dos_veces_exige_reiniciar(url_sqlite, monkeypatch, capsys):
    _crear("administrador", monkeypatch=monkeypatch)
    cli.main(["activar-mfa", "--correo", ADMIN])
    secreto = _secreto_impreso(capsys.readouterr().out)
    cli.main(["confirmar-mfa", "--correo", ADMIN, "--codigo", pyotp.TOTP(secreto).now()])
    capsys.readouterr()

    assert cli.main(["activar-mfa", "--correo", ADMIN]) == 1
    assert "reiniciar-mfa" in capsys.readouterr().err

    assert cli.main(["reiniciar-mfa", "--correo", ADMIN]) == 0
    usuario = _usuario(url_sqlite)
    assert usuario.mfa_secreto is None and usuario.mfa_activado_en is None
    assert cli.main(["activar-mfa", "--correo", ADMIN]) == 0


def test_mfa_solo_para_administradores(url_sqlite, monkeypatch, capsys):
    """RNF-S-1: MFA solo para administradores."""
    _crear("jefatura", correo="jefatura@demo.sart", monkeypatch=monkeypatch)
    capsys.readouterr()

    assert cli.main(["activar-mfa", "--correo", "jefatura@demo.sart"]) == 1
    assert "administrador" in capsys.readouterr().err


def test_correo_sin_cuenta(url_sqlite, capsys):
    assert cli.main(["activar-mfa", "--correo", "nadie@demo.sart"]) == 1
    assert "No existe" in capsys.readouterr().err
