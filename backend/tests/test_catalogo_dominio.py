"""Clasificación de establecimientos, causas y estaciones del catálogo (CI-3, RB-5, RF-1). Lógica pura."""

from sart.dominio.catalogo import clave_causa, estacion_de_comuna, normalizar, tipo_centro
from sart.dominio.valores import TipoCentro
from sart.parametros import cargar_parametros

PARAMETROS = cargar_parametros()
TIPOS = PARAMETROS["catalogo"]["tipos_establecimiento"]
CAUSAS = PARAMETROS["ingesta"]["causas"]
MAPA = PARAMETROS["catalogo"]["estacion_por_comuna"]


def test_normalizar_quita_tildes_mayusculas_y_espacios_de_mas():
    assert normalizar("  Servicio de  Atención\tPrimaria ") == "servicio de atencion primaria"


def test_tipo_de_centro_desde_la_glosa_del_registro():
    assert tipo_centro("Hospital", TIPOS) is TipoCentro.HOSPITAL
    assert tipo_centro("Servicio de Atención Primaria de Urgencia (SAPU)", TIPOS) is TipoCentro.SAPU
    assert tipo_centro("SERVICIO DE URGENCIA DE ALTA RESOLUCION (SAR)", TIPOS) is TipoCentro.SAR


def test_establecimientos_que_no_son_de_urgencia_no_tienen_tipo():
    assert tipo_centro("Posta de Salud Rural (PSR)", TIPOS) is None
    assert tipo_centro(None, TIPOS) is None


def test_causas_por_inicio_de_la_glosa():
    assert clave_causa("Infección respiratoria aguda alta (J00-J06)", CAUSAS) == "ira_alta"
    assert clave_causa("Neumonía (J12-J18)", CAUSAS) == "neumonia"
    assert clave_causa("Covid-19, virus identificado (U07.1)", CAUSAS) == "covid_identificado"


def test_hospitalizaciones_y_totales_no_se_cargan():
    assert clave_causa("Hospitalizaciones por causas respiratorias", CAUSAS) is None
    assert clave_causa("TOTAL CAUSA SISTEMA RESPIRATORIO", CAUSAS) is None


def test_estacion_por_comuna_sin_importar_tildes():
    assert estacion_de_comuna("Talcahuano", MAPA, "Kingston College") == "JUNJI"
    assert estacion_de_comuna("HUALPEN", MAPA, "Kingston College") == "JUNJI"


def test_comuna_sin_asignacion_usa_la_estacion_de_respaldo():
    """RB-5."""
    assert estacion_de_comuna("Florida", MAPA, "Kingston College") == "Kingston College"
