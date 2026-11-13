"""Prueba de humo del esqueleto: GET /salud responde aunque no haya base de datos."""

from fastapi.testclient import TestClient

from sart.api.app import app


def test_salud_responde_sin_base_de_datos(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    respuesta = TestClient(app).get("/salud")

    assert respuesta.status_code == 200
    cuerpo = respuesta.json()
    assert cuerpo["componentes"]["parametros"] == "ok"
    assert cuerpo["componentes"]["base_de_datos"].startswith("sin configurar")
    assert cuerpo["estado"] == "degradado"


def test_salud_informa_base_inalcanzable(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg://nadie@127.0.0.1:1/nada")
    cuerpo = TestClient(app).get("/salud").json()

    assert cuerpo["componentes"]["base_de_datos"].startswith("sin conexión")
    assert cuerpo["estado"] == "degradado"
