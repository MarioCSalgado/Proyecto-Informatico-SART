"""Fixtures comunes de las pruebas del backend."""

import pytest

from sart import configuracion


@pytest.fixture(autouse=True)
def sin_env_del_desarrollador(tmp_path, monkeypatch):
    """Aísla las pruebas del ``.env`` real del repositorio (RNF-P-1).

    Cada prueba ve un ``.env`` inexistente; la que necesite uno lo escribe y apunta ``ARCHIVO_ENV`` a él.
    """
    monkeypatch.setattr(configuracion, "ARCHIVO_ENV", tmp_path / "no_existe.env")
