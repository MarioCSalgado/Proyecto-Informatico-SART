"""TC-18 · Contenido enviado al LLM y cifras del boletín (RF-8, RNF-S-5).

Criterio: 0 nombres o correos enviados; las cifras del texto coinciden con las del sistema y ningún nivel
cambia. El LLM se reemplaza por funciones de prueba: el proveedor todavía no está elegido (pendientes #12).
"""

import pytest

from sart.dominio.boletin import (
    ErrorDatosPersonales,
    FilaBoletin,
    boletin_plantilla,
    filas_desde_estado,
    problemas_del_texto,
    redactar_boletin,
)

ANIO, SEMANA = 2026, 47
FILAS = [
    FilaBoletin(
        centro="SAPU Lagunillas", nivel="alerta", pronostico=760, limite_superior=812, profesionales=4
    ),
    FilaBoletin(
        centro="SAR Chiguayante", nivel="atencion", pronostico=640, limite_superior=700, profesionales=3
    ),
    FilaBoletin(centro="SAPU Penco", nivel="normal", pronostico=310, limite_superior=350, profesionales=None),
]
CUENTAS = [("Ana Pérez", "ana.perez@ssconcepcion.cl"), ("Luis Soto", "luis@ssconcepcion.cl")]
BUEN_TEXTO = (
    "Boletín SE 47 de 2026.\n"
    "SAPU Lagunillas está en ALERTA: se esperan 760 consultas (hasta 812); se sugieren 4 profesionales.\n"
    "SAR Chiguayante queda en atención con 640 consultas.\n"
    "SAPU Penco sigue normal."
)


def _redactar(texto_del_llm: str):
    enviados: list[str] = []

    def llm(prompt: str) -> str:
        enviados.append(prompt)
        return texto_del_llm

    resultado = redactar_boletin(ANIO, SEMANA, FILAS, redactor=llm, cuentas=CUENTAS)
    return resultado, enviados


def test_tc18_no_se_envian_nombres_ni_correos_de_usuarios():
    (texto, origen), enviados = _redactar(BUEN_TEXTO)

    assert origen == "llm" and texto == BUEN_TEXTO
    prompt = enviados[0]
    assert "@" not in prompt
    assert all(nombre not in prompt and correo not in prompt for nombre, correo in CUENTAS)
    assert "760" in prompt and "SAPU Lagunillas" in prompt  # sí van las cifras agregadas


def test_tc18_si_el_prompt_llevara_un_nombre_no_se_envia():
    filas = [
        FilaBoletin(centro="Ana Pérez", nivel="normal", pronostico=1, limite_superior=2, profesionales=None)
    ]
    llamado = []

    with pytest.raises(ErrorDatosPersonales):
        redactar_boletin(ANIO, SEMANA, filas, redactor=llamado.append, cuentas=CUENTAS)
    assert llamado == []


def test_tc18_cifras_y_niveles_correctos_pasan():
    assert problemas_del_texto(BUEN_TEXTO, FILAS, anio=ANIO, semana=SEMANA) == []


@pytest.mark.parametrize(
    ("texto", "problema"),
    [
        ("SAPU Lagunillas está en ALERTA con 790 consultas.", "790"),  # cifra inventada
        ("SAR Chiguayante está en ALERTA.", "SAR Chiguayante"),  # sube un nivel
        ("SAPU Lagunillas sigue normal.", "SAPU Lagunillas"),  # baja un nivel
    ],
)
def test_tc18_cifra_inventada_o_nivel_cambiado_se_detecta(texto, problema):
    problemas = problemas_del_texto(texto, FILAS, anio=ANIO, semana=SEMANA)

    assert any(problema in p for p in problemas)


def test_tc18_texto_del_llm_que_cambia_un_nivel_se_reemplaza_por_la_plantilla():
    (texto, origen), _ = _redactar("SAR Chiguayante está en ALERTA con 640 consultas.")

    assert origen == "plantilla"
    assert texto == boletin_plantilla(ANIO, SEMANA, FILAS)


def test_rf8_sin_proveedor_de_llm_sale_la_plantilla_y_sus_cifras_cuadran():
    texto, origen = redactar_boletin(ANIO, SEMANA, FILAS, redactor=None, cuentas=CUENTAS)

    assert origen == "plantilla"
    assert problemas_del_texto(texto, FILAS, anio=ANIO, semana=SEMANA) == []
    assert "ALERTA" in texto and "760" in texto


def test_rf8_filas_salen_del_estado_guardado_de_rf7():
    """Las cifras del boletín son las que ya muestra la web (GET /centros/estado), no se recalculan (#39)."""
    estados = [
        {
            "centro": {"nombre": "SAPU Lagunillas"},
            "pronostico": {
                "anio": 2026,
                "semana": 47,
                "valor": 759.6,
                "limite_superior": 812.2,
                "nivel": "alerta",
            },
            "dotacion": {"profesionales": 4},
        },
        {"centro": {"nombre": "Sin pronóstico"}, "pronostico": None, "dotacion": None},
        {
            "centro": {"nombre": "Sin umbral"},
            "pronostico": {"anio": 2026, "semana": 47, "valor": 10, "limite_superior": 12, "nivel": None},
            "dotacion": None,
        },
    ]

    assert filas_desde_estado(estados) == (
        2026,
        47,
        [
            FilaBoletin(
                centro="SAPU Lagunillas", nivel="alerta", pronostico=760, limite_superior=812, profesionales=4
            )
        ],
    )
