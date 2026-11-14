"""Datos de referencia para la web: escala de MP2,5 de RB-1 y comunas del escenario (RNF-M-4).

La web no escribe estos valores en su código: los pide a la API, que los lee de config/parametros.yaml.
"""

import pytest
from conftest import CLAVE_DE_PRUEBA

from sart.dominio.mp25 import niveles_mp25
from sart.parametros import cargar_parametros

UMBRALES = cargar_parametros()["mp25_niveles"]


def test_cinco_niveles_de_rb1_contiguos():
    """RB-1 y TC-05: Normal ≤ 50, sobre la norma 51–79, Alerta 80–109, Preemergencia 110–169, Emergencia."""
    niveles = [(n.clave, n.nombre, n.desde, n.hasta) for n in niveles_mp25(UMBRALES)]

    assert niveles == [
        ("normal", "Normal", 0, 50),
        ("sobre_la_norma", "Sobre la norma", 51, 79),
        ("alerta", "Alerta", 80, 109),
        ("preemergencia", "Preemergencia", 110, 169),
        ("emergencia", "Emergencia", 170, None),
    ]


def test_umbrales_desordenados_dan_error_claro():
    with pytest.raises(ValueError, match="mp25_niveles"):
        niveles_mp25({**UMBRALES, "alerta_desde": 200})


def test_referencias_exigen_sesion(cliente):
    assert cliente.get("/referencias").status_code == 401


def test_referencias_con_sesion(cliente, crear_cuenta):
    crear_cuenta("jefatura@demo.sart", "jefatura")
    cliente.post("/auth/sesion", json={"correo": "jefatura@demo.sart", "contrasena": CLAVE_DE_PRUEBA})

    cuerpo = cliente.get("/referencias").json()

    assert cuerpo["mp25_niveles"][1] == {
        "clave": "sobre_la_norma",
        "nombre": "Sobre la norma",
        "desde": 51,
        "hasta": 79,
    }
    assert cuerpo["mp25_niveles"][-1]["hasta"] is None
    assert cuerpo["comunas"] == cargar_parametros()["escenario"]["comunas"]
