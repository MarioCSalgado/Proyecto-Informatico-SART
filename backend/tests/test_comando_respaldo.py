"""Comando python -m sart.respaldo: la restauración reemplaza la base, así que exige --confirmar (RNF-D-2)."""

import pytest

from sart import respaldo as cli


@pytest.fixture(autouse=True)
def base_configurada(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg://sart:x@127.0.0.1:5433/sart")


@pytest.fixture
def restauraciones(monkeypatch) -> list:
    llamadas = []
    monkeypatch.setattr(cli, "restaurar_respaldo", lambda url, archivo: llamadas.append(archivo))
    return llamadas


def test_restaurar_sin_confirmar_no_toca_la_base(tmp_path, restauraciones, capsys):
    archivo = tmp_path / "sart_20261114_043000.dump"
    archivo.write_bytes(b"respaldo")

    assert cli.main(["restaurar", str(archivo)]) == 2

    assert "REEMPLAZA" in capsys.readouterr().err
    assert restauraciones == []


def test_restaurar_con_confirmar(tmp_path, restauraciones, capsys):
    archivo = tmp_path / "sart_20261114_043000.dump"
    archivo.write_bytes(b"respaldo")

    assert cli.main(["restaurar", str(archivo), "--confirmar"]) == 0

    assert restauraciones == [archivo]
    assert "volver a cargar las fuentes" in capsys.readouterr().out


def test_archivo_inexistente(tmp_path, restauraciones, capsys):
    assert cli.main(["restaurar", str(tmp_path / "no_esta.dump"), "--confirmar"]) == 1
    assert restauraciones == []
