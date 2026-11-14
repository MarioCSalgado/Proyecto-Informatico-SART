"""Comando python -m sart.catalogo cargar: mediciones y log de corridas con aviso (RF-1, RF-4, RNF-M-3)."""

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from sart import catalogo as cli
from sart.configuracion import RAIZ_REPOSITORIO
from sart.db.modelos import Base, Corrida
from sart.dominio.valores import EstadoCorrida

PRUEBA = RAIZ_REPOSITORIO / "datos" / "prueba" / "crudos"
BASICOS = ["cargar", "--establecimientos", str(PRUEBA / "establecimientos.csv")]


@pytest.fixture
def url(tmp_path, monkeypatch):
    url = f"sqlite:///{(tmp_path / 'sart.db').as_posix()}"
    motor = create_engine(url)
    Base.metadata.create_all(motor)
    motor.dispose()
    monkeypatch.setenv("DATABASE_URL", url)
    return url


def _corridas(url) -> list[tuple[str, str, EstadoCorrida]]:
    motor = create_engine(url)
    try:
        with Session(motor) as sesion:
            return [
                (c.tarea, c.fuente, c.estado) for c in sesion.scalars(select(Corrida).order_by(Corrida.id))
            ]
    finally:
        motor.dispose()


def test_carga_de_mediciones_y_una_corrida_por_paso(url, capsys):
    codigo = cli.main(
        [
            *BASICOS,
            "--sinca",
            str(PRUEBA / "sinca"),
            "--clima",
            str(PRUEBA / "clima_openmeteo.csv"),
            "--pronostico-mp25",
            str(PRUEBA / "pronostico_mp25_openmeteo.csv"),
        ]
    )

    salida = capsys.readouterr().out
    assert codigo == 0
    assert "MP2,5 de SINCA:" in salida and "6 estaciones" in salida
    assert "Pronóstico de MP2,5 de Open-Meteo: 240 mediciones" in salida
    assert _corridas(url) == [
        ("carga_catalogo", "registro_establecimientos", EstadoCorrida.EXITOSA),
        ("carga_sinca", "SINCA", EstadoCorrida.EXITOSA),
        ("carga_clima", "Open-Meteo", EstadoCorrida.EXITOSA),
        ("carga_pronostico_mp25", "Open-Meteo", EstadoCorrida.EXITOSA),
    ]


def test_una_fuente_que_falla_dos_veces_seguidas_genera_aviso(url, tmp_path, capsys):
    """RNF-M-3: «aviso si una fuente falla 2 veces seguidas»."""
    roto = tmp_path / "roto.csv"
    roto.write_text("columna_equivocada\n1\n", encoding="utf-8")
    argumentos = [*BASICOS, "--clima", str(roto)]

    assert cli.main(argumentos) == 1
    primera = capsys.readouterr().err
    assert "No se completó la carga de clima" in primera
    assert "AVISO" not in primera

    assert cli.main(argumentos) == 1
    assert "AVISO (RNF-M-3): la fuente Open-Meteo falló 2 veces seguidas" in capsys.readouterr().err
    assert [c for c in _corridas(url) if c[0] == "carga_clima"] == [
        ("carga_clima", "Open-Meteo", EstadoCorrida.FALLIDA),
        ("carga_clima", "Open-Meteo", EstadoCorrida.FALLIDA),
    ]
