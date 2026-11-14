"""Comando python -m sart.catalogo recalcular-umbrales (RB-3, una vez al año; corrida en el log, RNF-M-3)."""

from datetime import date, timedelta

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from sart import catalogo as cli
from sart.configuracion import RAIZ_REPOSITORIO
from sart.db.modelos import Base, CentroSalud, ConsultaSemanal, Corrida, UmbralCentro
from sart.dominio.semanas import semana_epidemiologica
from sart.dominio.valores import EstadoCorrida
from sart.tareas.carga import cargar_catalogo

ESTABLECIMIENTOS = RAIZ_REPOSITORIO / "datos" / "prueba" / "crudos" / "establecimientos.csv"


@pytest.fixture
def url(tmp_path, monkeypatch):
    url = f"sqlite:///{(tmp_path / 'sart.db').as_posix()}"
    motor = create_engine(url)
    Base.metadata.create_all(motor)
    with Session(motor) as sesion:
        cargar_catalogo(sesion, ESTABLECIMIENTOS)
    motor.dispose()
    monkeypatch.setenv("DATABASE_URL", url)
    return url


def _con_consultas(url, semanas=80):
    motor = create_engine(url)
    with Session(motor) as sesion:
        centro = sesion.scalars(select(CentroSalud.id)).first()
        for i in range(semanas):
            anio, semana = semana_epidemiologica(date(2026, 9, 27) - timedelta(weeks=i))
            sesion.add(
                ConsultaSemanal(
                    centro_id=centro,
                    anio=anio,
                    semana=semana,
                    causa="neumonia",
                    grupo_edad="de_1_a_4",
                    cantidad=50 + i % 10,
                )
            )
        sesion.commit()
    motor.dispose()


def _en_la_base(url):
    motor = create_engine(url)
    try:
        with Session(motor) as sesion:
            umbrales = sesion.scalars(select(UmbralCentro)).all()
            corridas = [(c.tarea, c.estado) for c in sesion.scalars(select(Corrida))]
            return len(umbrales), corridas
    finally:
        motor.dispose()


def test_recalcula_y_deja_la_corrida(url, capsys):
    _con_consultas(url)

    assert cli.main(["recalcular-umbrales"]) == 0

    assert "Umbrales recalculados hasta 2026-SE39: 1 centros" in capsys.readouterr().out
    assert _en_la_base(url) == (1, [("recalculo_umbrales", EstadoCorrida.EXITOSA)])


def test_sin_consultas_explica_el_problema(url, capsys):
    assert cli.main(["recalcular-umbrales"]) == 1

    assert "No hay semanas completas" in capsys.readouterr().err
    assert _en_la_base(url) == (0, [("recalculo_umbrales", EstadoCorrida.FALLIDA)])
