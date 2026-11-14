"""Respaldo diario de la base: nombre, retención y herramienta (RNF-D-2). La restauración es TC-14."""

from datetime import datetime

import pytest

from sart.tareas import respaldo
from sart.tareas.respaldo import ErrorRespaldo, comando, nombre_respaldo, podar_respaldos

URL = "postgresql+psycopg://sart:clave-secreta@127.0.0.1:5433/sart"


def test_nombre_con_base_y_fecha_ordenable():
    assert nombre_respaldo("sart", datetime(2026, 11, 14, 4, 30, 5)) == "sart_20261114_043005.dump"


def test_podar_conserva_los_mas_recientes(tmp_path):
    for dia in range(1, 18):
        (tmp_path / f"sart_202611{dia:02d}_043000.dump").write_bytes(b"x")
    (tmp_path / "otro_archivo.txt").write_text("no se toca")

    borrados = podar_respaldos(tmp_path, conservar=14)

    assert [b.name for b in borrados] == [f"sart_202611{d:02d}_043000.dump" for d in (1, 2, 3)]
    assert len(list(tmp_path.glob("*.dump"))) == 14
    assert (tmp_path / "otro_archivo.txt").exists()


def test_con_docker_usa_el_pg_dump_del_contenedor(monkeypatch):
    """La versión del contenedor coincide con la de la base: no hay sorpresas de compatibilidad."""
    monkeypatch.setattr(respaldo, "docker_disponible", lambda: True)

    argv, entorno = comando("pg_dump", URL)

    assert argv[:6] == ["docker", "compose", "exec", "-T", "db", "pg_dump"]
    assert "clave-secreta" not in " ".join(argv)  # dentro del contenedor no hace falta la clave


def test_sin_docker_usa_pg_dump_local_con_la_clave_en_el_entorno(monkeypatch):
    monkeypatch.setattr(respaldo, "docker_disponible", lambda: False)
    monkeypatch.setattr(respaldo.shutil, "which", lambda nombre: f"/usr/bin/{nombre}")

    argv, entorno = comando("pg_dump", URL)

    assert argv[0] == "/usr/bin/pg_dump"
    assert ["-h", "127.0.0.1", "-p", "5433", "-U", "sart"] == argv[1:7]
    assert "clave-secreta" not in " ".join(argv)  # nunca en la línea de comandos (se vería en los procesos)
    assert entorno["PGPASSWORD"] == "clave-secreta"


def test_sin_ninguna_herramienta_da_error_claro(monkeypatch):
    monkeypatch.setattr(respaldo, "docker_disponible", lambda: False)
    monkeypatch.setattr(respaldo.shutil, "which", lambda nombre: None)

    with pytest.raises(ErrorRespaldo, match="pg_dump"):
        comando("pg_dump", URL)
