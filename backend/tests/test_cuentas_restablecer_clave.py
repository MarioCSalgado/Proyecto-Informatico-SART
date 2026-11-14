"""Restablecer la contraseña de una cuenta por comando (RF-9, RNF-S-1; pendientes #23)."""

import io

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from sart import cuentas as cli
from sart.db.modelos import Auditoria, Base, Usuario
from sart.dominio.contrasenas import verificar

CORREO = "jefatura@demo.sart"


@pytest.fixture
def url(tmp_path, monkeypatch):
    url = f"sqlite:///{(tmp_path / 'sart.db').as_posix()}"
    motor = create_engine(url)
    Base.metadata.create_all(motor)
    motor.dispose()
    monkeypatch.setenv("DATABASE_URL", url)
    monkeypatch.setattr("sys.stdin", io.StringIO("clave original larga\n"))
    argumentos = ["crear", "--nombre", "Jefatura", "--correo", CORREO, "--rol", "jefatura"]
    assert cli.main([*argumentos, "--acepta-finalidad", "--contrasena-stdin"]) == 0
    return url


def _usuario_y_auditoria(url) -> tuple[Usuario, list[Auditoria]]:
    motor = create_engine(url)
    try:
        with Session(motor) as sesion:
            usuario = sesion.scalars(select(Usuario)).one()
            auditoria = sesion.scalars(select(Auditoria)).all()
            sesion.expunge_all()
            return usuario, auditoria
    finally:
        motor.dispose()


def test_restablecer_cambia_la_clave_y_queda_auditado(url, monkeypatch, capsys):
    monkeypatch.setattr("sys.stdin", io.StringIO("clave nueva de prueba\n"))

    assert cli.main(["restablecer-clave", "--correo", CORREO, "--contrasena-stdin"]) == 0

    usuario, auditoria = _usuario_y_auditoria(url)
    assert verificar(usuario.hash_contrasena, "clave nueva de prueba")
    assert not verificar(usuario.hash_contrasena, "clave original larga")
    assert [(a.accion, a.entidad_id, a.autor_rol) for a in auditoria] == [
        ("restablecer_clave", str(usuario.id), "sistema")
    ]
    assert "clave nueva" not in str(auditoria[0].valor_nuevo)  # nunca se guarda la clave
    assert CORREO in capsys.readouterr().out


def test_clave_corta_se_rechaza_y_no_cambia_nada(url, monkeypatch, capsys):
    """RNF-S-1: largo mínimo de cuentas.largo_minimo_contrasena (12)."""
    monkeypatch.setattr("sys.stdin", io.StringIO("prueba123\n"))

    assert cli.main(["restablecer-clave", "--correo", CORREO, "--contrasena-stdin"]) == 1

    assert "12 caracteres" in capsys.readouterr().err
    usuario, auditoria = _usuario_y_auditoria(url)
    assert verificar(usuario.hash_contrasena, "clave original larga")
    assert auditoria == []


def test_correo_sin_cuenta(url, monkeypatch, capsys):
    monkeypatch.setattr("sys.stdin", io.StringIO("clave nueva de prueba\n"))

    assert cli.main(["restablecer-clave", "--correo", "nadie@demo.sart", "--contrasena-stdin"]) == 1
    assert "No existe" in capsys.readouterr().err
