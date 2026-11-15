"""Comando python -m sart.tareas semanal (RF-2, RF-3, RF-6; corrida en el log, RNF-M-3)."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from sart.db.modelos import Corrida, Pronostico
from sart.tareas.__main__ import main
from sart.tareas.semanal import TAREA


def test_semanal_con_prueba_pronostica_la_se_40(base_prueba, monkeypatch, capsys):
    monkeypatch.setenv("DATABASE_URL", base_prueba.url.render_as_string(hide_password=False))

    assert main(["semanal", "--prueba"]) == 0

    salida = capsys.readouterr().out
    assert "SE 40 de 2026" in salida and "desactualizado" not in salida
    assert "ALERTA por notificar (RF-5): 0." in salida
    # sin recalcular-umbrales antes, los centros no se clasifican y se avisa (RF-3 E1)
    assert "Sin umbral vigente" in salida
    with Session(base_prueba) as sesion:
        assert len(sesion.scalars(select(Pronostico)).all()) == 14
        assert sesion.scalars(select(Corrida).where(Corrida.tarea == TAREA)).one().filas == 14


def test_semanal_sin_base_de_datos(monkeypatch, capsys):
    monkeypatch.delenv("DATABASE_URL", raising=False)  # la CI la define para todo el job

    assert main(["semanal"]) == 1
    assert "DATABASE_URL" in capsys.readouterr().err
