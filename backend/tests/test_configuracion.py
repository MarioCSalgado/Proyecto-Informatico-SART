"""Configuración de entorno: la API lee el .env sola, sin --env-file (RNF-P-1)."""

from pathlib import Path

from sart import configuracion
from sart.configuracion import obtener_configuracion
from sart.parametros import ruta_parametros


def _escribir_env(tmp_path, monkeypatch, contenido: str) -> None:
    archivo = tmp_path / ".env"
    archivo.write_text(contenido, encoding="utf-8")
    monkeypatch.setattr(configuracion, "ARCHIVO_ENV", archivo)


def test_lee_las_variables_del_archivo_env(tmp_path, monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.delenv("JWT_SECRET", raising=False)
    _escribir_env(
        tmp_path,
        monkeypatch,
        "POSTGRES_USER=sart\nDATABASE_URL=postgresql+psycopg://a:b@localhost:5433/sart\nJWT_SECRET=x\n",
    )

    config = obtener_configuracion()

    assert config.database_url == "postgresql+psycopg://a:b@localhost:5433/sart"
    assert config.jwt_secret == "x"


def test_la_variable_de_entorno_gana_al_archivo(tmp_path, monkeypatch):
    _escribir_env(tmp_path, monkeypatch, "DATABASE_URL=postgresql+psycopg://desde-archivo/sart\n")
    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg://desde-entorno/sart")

    assert obtener_configuracion().database_url == "postgresql+psycopg://desde-entorno/sart"


def test_sin_archivo_ni_variables_queda_vacia(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.delenv("JWT_SECRET", raising=False)
    monkeypatch.delenv("SART_PARAMETROS", raising=False)

    config = obtener_configuracion()

    assert config.database_url is None
    assert config.jwt_secret is None
    assert config.sart_parametros is None


def test_sart_parametros_relativo_se_resuelve_desde_la_raiz(tmp_path, monkeypatch):
    """RNF-M-4: ``SART_PARAMETROS=config/parametros.yaml`` en el .env apunta a la raíz del repo."""
    monkeypatch.delenv("SART_PARAMETROS", raising=False)
    _escribir_env(tmp_path, monkeypatch, "SART_PARAMETROS=config/parametros.yaml\n")

    esperado = Path(configuracion.RAIZ_REPOSITORIO) / "config" / "parametros.yaml"
    assert ruta_parametros() == esperado
