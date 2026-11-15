"""Comando python -m sart.demo preparar: el escenario de prueba local en un paso (datos, pronóstico y
cuentas).

Las cuentas, la clave y el código MFA son los del video del 14/11, para que todo el equipo tenga lo mismo.
Solo funciona en un entorno local (COOKIE_SEGURA=false), igual que el código MFA fijo (pendientes #49).
"""

import pytest
from conftest import DATOS_PRUEBA
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from sart.db.modelos import Base, Pronostico, Usuario
from sart.demo import CENTRO_JEFATURA, CLAVE_DEMO, CUENTAS_DEMO, main, preparar_cuentas_demo
from sart.dominio.contrasenas import verificar
from sart.dominio.roles import Rol
from sart.tareas.carga import cargar_catalogo


@pytest.fixture
def con_catalogo(motor_memoria):
    with Session(motor_memoria) as sesion:
        cargar_catalogo(sesion, DATOS_PRUEBA / "establecimientos.csv")
    return motor_memoria


def _cuentas(motor) -> dict[str, Usuario]:
    with Session(motor) as sesion:
        usuarios = sesion.scalars(select(Usuario)).all()
        for u in usuarios:
            _ = [c.codigo_deis for c in u.centros]  # carga los centros antes de cerrar la sesión
        return {u.correo: u for u in usuarios}


def test_crea_las_tres_cuentas_del_video(con_catalogo):
    with Session(con_catalogo) as sesion:
        preparar_cuentas_demo(sesion)

    cuentas = _cuentas(con_catalogo)
    assert set(cuentas) == {correo for _, correo, _ in CUENTAS_DEMO}
    assert {u.rol for u in cuentas.values()} == {Rol.JEFATURA, Rol.SUBDIRECTOR, Rol.ADMINISTRADOR}
    for usuario in cuentas.values():
        assert verificar(usuario.hash_contrasena, CLAVE_DEMO)
    jefatura = next(u for u in cuentas.values() if u.rol is Rol.JEFATURA)
    assert [c.codigo_deis for c in jefatura.centros] == [CENTRO_JEFATURA]
    admin = next(u for u in cuentas.values() if u.rol is Rol.ADMINISTRADOR)
    assert admin.mfa_activado_en is not None  # puede entrar con el código fijo de desarrollo


def test_repetir_no_duplica_ni_cambia_claves(con_catalogo):
    with Session(con_catalogo) as sesion:
        preparar_cuentas_demo(sesion)
        jefatura = sesion.scalar(select(Usuario).where(Usuario.rol == Rol.JEFATURA))
        jefatura.hash_contrasena = "hash que el usuario cambió"
        sesion.commit()

    with Session(con_catalogo) as sesion:
        resumen = preparar_cuentas_demo(sesion)

    cuentas = _cuentas(con_catalogo)
    assert len(cuentas) == 3
    assert (
        next(u for u in cuentas.values() if u.rol is Rol.JEFATURA).hash_contrasena
        == "hash que el usuario cambió"
    )
    assert any("ya existía" in linea for linea in resumen)


def test_se_niega_fuera_de_un_entorno_local(monkeypatch, capsys):
    monkeypatch.setenv("COOKIE_SEGURA", "true")
    monkeypatch.setenv("DATABASE_URL", "sqlite://")

    assert main(["preparar"]) == 1
    assert "COOKIE_SEGURA" in capsys.readouterr().err


def test_preparar_deja_el_escenario_completo(tmp_path, monkeypatch, capsys):
    url = f"sqlite:///{(tmp_path / 'sart.db').as_posix()}"
    motor = create_engine(url)
    Base.metadata.create_all(motor)
    monkeypatch.setenv("DATABASE_URL", url)
    monkeypatch.setenv("COOKIE_SEGURA", "false")
    monkeypatch.setenv("MFA_CODIGO_DESARROLLO", "123456")

    assert main(["preparar"]) == 0

    salida = capsys.readouterr().out
    assert "jefatura.capturas@demo.sart" in salida and CLAVE_DEMO in salida and "123456" in salida
    with Session(motor) as sesion:
        assert len(sesion.scalars(select(Pronostico).where(Pronostico.vigente.is_(True))).all()) == 14
        assert len(sesion.scalars(select(Usuario)).all()) == 3
    motor.dispose()
