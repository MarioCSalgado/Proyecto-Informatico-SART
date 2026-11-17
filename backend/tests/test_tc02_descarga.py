"""TC-02 / RF-1: descargas simuladas, reintentos, avisos y último dato válido; sin red."""

import copy
import json
from datetime import date
from io import BytesIO
from urllib.error import URLError
from urllib.parse import parse_qs, urlsplit

import pandas as pd
import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from sart.db.modelos import ConsultaSemanal, Corrida, Medicion
from sart.dominio.valores import EstadoCorrida
from sart.parametros import cargar_parametros
from sart.tareas.carga import cargar_catalogo
from sart.tareas.descarga import correr_descarga, descargar_http, url_sinca


@pytest.fixture
def parametros():
    p = copy.deepcopy(cargar_parametros())
    p["ingesta"]["reintentos_fuente"] = 1
    p["descarga"]["espera_reintento_segundos"] = 0
    # La prueba usa solo Kingston College, aunque el YAML liste más estaciones SINCA
    sinca = p["descarga"]["sinca"]["estaciones"]
    p["descarga"]["sinca"]["estaciones"] = {"Kingston College": sinca["Kingston College"]}
    return p


@pytest.fixture
def sesion(motor_memoria, tmp_path, parametros):
    registro = tmp_path / "establecimientos.csv"
    pd.DataFrame(
        [
            {
                "EstablecimientoCodigo": "100001",
                "EstablecimientoCodigoAntiguo": "09-001",
                "EstablecimientoGlosa": "Hospital de prueba",
                "ComunaGlosa": "Concepción",
                "TipoEstablecimientoGlosa": "Hospital",
                "Latitud": "-36,83",
                "Longitud": "-73,05",
            }
        ]
    ).to_csv(registro, sep=";", index=False)
    with Session(motor_memoria) as sesion:
        cargar_catalogo(sesion, registro, parametros)
        yield sesion


@pytest.fixture
def respuestas(parametros):
    archivo = BytesIO()
    pd.DataFrame(
        [
            {
                "EstablecimientoCodigo": "100001",
                "Anio": 2026,
                "SemanaEstadistica": 20,
                "Causa": "IRA Alta (J00-J06)",
                "NumTotal": 10,
                "NumMenor1Anio": 2,
                "Num1a4Anios": 2,
                "Num5a14Anios": 2,
                "Num15a64Anios": 2,
                "Num65oMas": 2,
            }
        ]
    ).to_parquet(archivo, index=False)
    sinca = (
        "FECHA (YYMMDD);HORA (HHMM);Registros validados;Registros preliminares;"
        "Registros no validados;\n260517;0000;20;;;\n"
    ).encode("latin-1")
    clima = json.dumps(
        {
            "daily": {
                "time": ["2026-05-17"],
                "temperature_2m_mean": [12],
                "temperature_2m_min": [7],
                "relative_humidity_2m_mean": [70],
            }
        }
    ).encode()
    mp = json.dumps(
        {"hourly": {"time": ["2026-05-18T00:00"], "pm2_5": [20], "pm10": [30]}}
    ).encode()
    return {
        "deis": archivo.getvalue(),
        "sinca": sinca,
        "clima": clima,
        "pronostico": mp,
    }


def _fuente(url, parametros):
    cfg = parametros["descarga"]
    if url == cfg["deis_url"]:
        return "deis"
    if "apub.tsindico2.cgi" in url:
        return "sinca"
    if url.startswith(cfg["open_meteo"]["clima_url"]):
        return "clima"
    return "pronostico"


def _cliente(respuestas, parametros, llamadas, fallos=None):
    def obtener(url, destino, **kwargs):
        fuente = _fuente(url, parametros)
        llamadas.append((fuente, url))
        if fallos and fuente in fallos:
            respuesta = fallos[fuente]()
        else:
            respuesta = respuestas[fuente]
        destino.write_bytes(respuesta)

    return obtener


def _correr(sesion, tmp_path, parametros, obtener):
    return correr_descarga(
        sesion,
        carpeta=tmp_path / "crudos",
        fecha=date(2026, 11, 17),
        parametros=parametros,
        obtener=obtener,
        esperar=lambda segundos: None,
    )


def test_tc02_cuatro_fuentes_cargadas_y_recarga_sin_duplicados(
    sesion, tmp_path, parametros, respuestas
):
    llamadas = []
    obtener = _cliente(respuestas, parametros, llamadas)
    primera = _correr(sesion, tmp_path, parametros, obtener)
    cantidades = (
        sesion.scalar(select(func.count()).select_from(ConsultaSemanal)),
        sesion.scalar(select(func.count()).select_from(Medicion)),
    )
    segunda = _correr(sesion, tmp_path, parametros, obtener)
    assert not primera.fallidas and not segunda.fallidas
    assert set(primera.cargadas) == {
        "DEIS",
        "SINCA/Kingston College",
        "Open-Meteo/clima",
        "Open-Meteo/pronostico",
    }
    assert cantidades == (
        sesion.scalar(select(func.count()).select_from(ConsultaSemanal)),
        sesion.scalar(select(func.count()).select_from(Medicion)),
    )
    assert sesion.scalar(select(func.sum(ConsultaSemanal.cantidad))) == 10
    assert sesion.scalar(select(func.count()).select_from(Corrida)) == 8
    assert set(sesion.scalars(select(Corrida.estado))) == {EstadoCorrida.EXITOSA}
    carpeta = tmp_path / "crudos"
    assert (carpeta / "at_urg_respiratorio_semanal.parquet").read_bytes() == respuestas[
        "deis"
    ]
    assert (carpeta / "clima_openmeteo.json").read_bytes() == respuestas["clima"]
    assert (carpeta / "pronostico_mp25_openmeteo.json").read_bytes() == respuestas[
        "pronostico"
    ]
    assert (carpeta / "sinca/Kingston College.csv").read_bytes() == respuestas["sinca"]
    sinca_url = next(url for fuente, url in llamadas if fuente == "sinca")
    query = parse_qs(urlsplit(sinca_url).query, keep_blank_values=True)
    assert query["from"] == ["090812"] and query["to"] == ["261115"]
    assert query["rsrc"] == [""] and query["macropath"] == [""]


def test_tc02_reintenta_error_transitorio_sin_contar_corrida_fallida(
    sesion, tmp_path, parametros, respuestas
):
    veces = []

    def fallar_una_vez():
        veces.append(1)
        if len(veces) == 1:
            raise URLError("caída temporal")
        return respuestas["deis"]

    llamadas = []
    resumen = _correr(
        sesion,
        tmp_path,
        parametros,
        _cliente(respuestas, parametros, llamadas, {"deis": fallar_una_vez}),
    )
    assert not resumen.fallidas
    assert len(veces) == 2
    assert set(sesion.scalars(select(Corrida.estado))) == {EstadoCorrida.EXITOSA}


def test_tc02_fuente_caida_conserva_ultimo_dato_y_avisa_tras_dos_corridas(
    sesion, tmp_path, parametros, respuestas
):
    llamadas = []
    _correr(sesion, tmp_path, parametros, _cliente(respuestas, parametros, llamadas))
    anterior = (tmp_path / "crudos/at_urg_respiratorio_semanal.parquet").read_bytes()

    def caer():
        raise URLError("fuente no disponible")

    fallido = _cliente(respuestas, parametros, llamadas, {"deis": caer})
    una = _correr(sesion, tmp_path, parametros, fallido)
    dos = _correr(sesion, tmp_path, parametros, fallido)
    assert "DEIS" in una.fallidas and not una.avisos
    assert "DEIS" in dos.fallidas and any("DEIS falló 2" in x for x in dos.avisos)
    assert "Open-Meteo/clima" in dos.cargadas
    assert (
        tmp_path / "crudos/at_urg_respiratorio_semanal.parquet"
    ).read_bytes() == anterior
    assert sesion.scalar(select(func.sum(ConsultaSemanal.cantidad))) == 10
    estados = list(
        sesion.scalars(
            select(Corrida.estado).where(Corrida.fuente == "DEIS").order_by(Corrida.id)
        )
    )
    assert estados == [
        EstadoCorrida.EXITOSA,
        EstadoCorrida.FALLIDA,
        EstadoCorrida.FALLIDA,
    ]


def test_tc02_columna_renombrada_no_reemplaza_archivo_ni_base(
    sesion, tmp_path, parametros, respuestas
):
    obtener = _cliente(respuestas, parametros, [])
    _correr(sesion, tmp_path, parametros, obtener)
    viejo = (tmp_path / "crudos/at_urg_respiratorio_semanal.parquet").read_bytes()
    tabla = pd.read_parquet(BytesIO(respuestas["deis"]))
    salida = BytesIO()
    tabla.rename(columns={"Num65oMas": "nueva_columna"}).to_parquet(salida, index=False)
    respuestas["deis"] = salida.getvalue()
    resultado = _correr(sesion, tmp_path, parametros, obtener)
    assert "Num65oMas" in resultado.fallidas["DEIS"]
    assert sesion.scalar(select(func.sum(ConsultaSemanal.cantidad))) == 10
    assert (
        tmp_path / "crudos/at_urg_respiratorio_semanal.parquet"
    ).read_bytes() == viejo


def test_tc02_sinca_solo_fecha_hora_no_reemplaza_csv_valido(
    sesion, tmp_path, parametros, respuestas
):
    obtener = _cliente(respuestas, parametros, [])
    _correr(sesion, tmp_path, parametros, obtener)
    viejo = (tmp_path / "crudos/sinca/Kingston College.csv").read_bytes()
    respuestas["sinca"] = b"FECHA (YYMMDD);HORA (HHMM);\n260517;0000;\n"
    resultado = _correr(sesion, tmp_path, parametros, obtener)
    assert "SINCA/Kingston College" in resultado.fallidas
    assert (tmp_path / "crudos/sinca/Kingston College.csv").read_bytes() == viejo
    assert "Open-Meteo/pronostico" in resultado.cargadas


def test_tc02_json_invalido_no_borra_clima_previo(
    sesion, tmp_path, parametros, respuestas
):
    obtener = _cliente(respuestas, parametros, [])
    _correr(sesion, tmp_path, parametros, obtener)
    viejo = (tmp_path / "crudos/clima_openmeteo.csv").read_bytes()
    respuestas["clima"] = b"<html>Error del servidor</html>"
    resultado = _correr(sesion, tmp_path, parametros, obtener)
    assert "Open-Meteo/clima" in resultado.fallidas
    assert (tmp_path / "crudos/clima_openmeteo.csv").read_bytes() == viejo
    assert "Open-Meteo/pronostico" in resultado.cargadas


def test_tc02_fallas_clima_no_se_ocultan_por_exito_del_pronostico(
    sesion, tmp_path, parametros, respuestas
):
    respuestas["clima"] = b"{}"
    obtener = _cliente(respuestas, parametros, [])
    _correr(sesion, tmp_path, parametros, obtener)
    segunda = _correr(sesion, tmp_path, parametros, obtener)
    assert any("Open-Meteo/clima falló 2" in x for x in segunda.avisos)
    assert not any("Open-Meteo/pronostico falló" in x for x in segunda.avisos)


def test_tc02_url_sinca_conserva_parametros_de_exportacion(parametros):
    original = parametros["descarga"]["sinca"]["estaciones"]["Kingston College"]
    resultado = url_sinca(original, desde=date(2009, 8, 12), hasta=date(2026, 11, 15))
    assert dict(parse_qs(urlsplit(resultado).query, keep_blank_values=True)) == dict(
        parse_qs(urlsplit(original).query, keep_blank_values=True)
    )


def test_tc02_http_limita_tamano_y_rechaza_archivo_vacio(tmp_path, monkeypatch):
    class Respuesta(BytesIO):
        def __enter__(self):
            return self

        def __exit__(self, *args):
            self.close()

    monkeypatch.setattr(
        "sart.tareas.descarga.urlopen", lambda *a, **kw: Respuesta(b"12345")
    )
    with pytest.raises(ValueError, match="máximo"):
        descargar_http(
            "https://fuente.test", tmp_path / "candidato", timeout=1, maximo_bytes=4
        )
    monkeypatch.setattr("sart.tareas.descarga.urlopen", lambda *a, **kw: Respuesta(b""))
    with pytest.raises(ValueError, match="vacío"):
        descargar_http(
            "https://fuente.test", tmp_path / "candidato", timeout=1, maximo_bytes=4
        )
