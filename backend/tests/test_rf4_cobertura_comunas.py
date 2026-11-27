"""RF-4: el pronóstico de MP2,5 de Open-Meteo llega a todas las comunas del escenario, un punto por comuna.

Antes había un solo punto (Concepción) y las otras nueve zonas quedaban en «datos insuficientes» cuando
RF-4 usa el pronóstico. Ahora cada comuna tiene su estación Open-Meteo en ``catalogo.estaciones`` y la
descarga pide todos los puntos en una sola consulta. El clima sigue saliendo del punto principal
(``estacion_principal``).
"""

import copy
import json
from datetime import UTC, date, datetime, time, timedelta
from zoneinfo import ZoneInfo

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from sart.db.modelos import Alerta, Estacion, Medicion, PronosticoAmbiental, Zona
from sart.dominio.valores import FuenteEstacion, OrigenMedicion, TipoAlerta, TipoMedicion
from sart.parametros import cargar_parametros
from sart.tareas.ambiental import correr_ambiental
from sart.tareas.descarga import puntos_pronostico, separar_puntos

PARAMETROS = cargar_parametros()
COMUNAS = PARAMETROS["escenario"]["comunas"]


def _estaciones_open_meteo(parametros):
    return {
        nombre: datos
        for nombre, datos in parametros["catalogo"]["estaciones"].items()
        if datos["fuente"] == FuenteEstacion.OPEN_METEO.value
    }


def test_rf4_cada_comuna_del_escenario_tiene_un_punto_open_meteo():
    comunas = [datos["comuna"] for datos in _estaciones_open_meteo(PARAMETROS).values()]
    assert sorted(comunas) == sorted(COMUNAS)  # una y solo una por comuna
    for datos in _estaciones_open_meteo(PARAMETROS).values():
        assert -37.5 < datos["latitud"] < -36.3 and -73.5 < datos["longitud"] < -72.5  # Gran Concepción


def test_rf4_el_punto_principal_es_una_estacion_open_meteo():
    principal = PARAMETROS["descarga"]["open_meteo"]["estacion_principal"]
    assert principal in _estaciones_open_meteo(PARAMETROS)


def test_rf4_puntos_pronostico_lista_el_principal_primero():
    puntos = puntos_pronostico(PARAMETROS)
    assert puntos[0][0] == PARAMETROS["descarga"]["open_meteo"]["estacion_principal"]
    assert len(puntos) == len(COMUNAS)


def _respuesta(valores):
    return [
        {"latitude": -36.8, "longitude": -73.0,
         "hourly": {"time": ["2026-05-18T00:00"], "pm2_5": [valor], "pm10": [valor]}}
        for valor in valores
    ]


def test_rf4_separar_puntos_respeta_el_orden_de_la_consulta(tmp_path):
    crudo = tmp_path / "pronostico.json"
    crudo.write_text(json.dumps(_respuesta([10, 20, 30])), encoding="utf-8")
    partes = separar_puntos(crudo, 3)
    assert [p["hourly"]["pm2_5"][0] for p in partes] == [10, 20, 30]


def test_rf4_separar_puntos_acepta_un_solo_punto_como_objeto(tmp_path):
    crudo = tmp_path / "pronostico.json"
    crudo.write_text(json.dumps(_respuesta([10])[0]), encoding="utf-8")
    assert len(separar_puntos(crudo, 1)) == 1


def test_rf4_separar_puntos_rechaza_si_faltan_puntos(tmp_path):
    crudo = tmp_path / "pronostico.json"
    crudo.write_text(json.dumps(_respuesta([10, 20])), encoding="utf-8")
    with pytest.raises(ValueError, match="3 puntos"):
        separar_puntos(crudo, 3)


@pytest.fixture
def sesion(base_prueba):
    with Session(base_prueba) as sesion:
        yield sesion


def _pronostico_dia(sesion, estacion, dia, valor):
    inicio = datetime.combine(dia, time.min, tzinfo=ZoneInfo(PARAMETROS["zona_horaria"])).astimezone(UTC)
    for hora in range(24):
        sesion.add(Medicion(estacion_id=estacion.id, fecha_hora=inicio + timedelta(hours=hora),
                            tipo=TipoMedicion.MP25, valor=valor, unidad="µg/m³",
                            origen=OrigenMedicion.PRONOSTICO))


def test_rf4_cada_zona_usa_el_pronostico_de_su_propio_punto(sesion, monkeypatch):
    """Coronel con 95 µg/m³ da «Alerta» solo en Coronel; las otras nueve comunas quedan en «normal»."""
    monkeypatch.setattr("sart.tareas.ambiental._sensibilidad_tc12", lambda *args: (True, 1.0))
    dia = date(2026, 1, 15)
    estaciones = sesion.scalars(select(Estacion).where(Estacion.fuente == FuenteEstacion.OPEN_METEO)).all()
    assert sorted(e.zona.nombre for e in estaciones) == sorted(COMUNAS)
    for estacion in estaciones:
        for d in range(5):
            valor = 95 if estacion.zona.nombre == "Coronel" else 20
            _pronostico_dia(sesion, estacion, dia + timedelta(days=d), valor)
    sesion.commit()

    resumen = correr_ambiental(sesion, fecha=dia)

    assert resumen.datos_insuficientes == []
    assert resumen.promedios_calculados == len(COMUNAS) * 5
    zonas = set(sesion.scalars(
        select(Zona.nombre).join(Alerta, Alerta.zona_id == Zona.id)
        .where(Alerta.tipo == TipoAlerta.AMBIENTAL)))
    assert zonas == {"Coronel"}


def test_rf4_cargar_pronostico_en_la_estacion_de_otra_comuna(sesion, tmp_path):
    from sart.tareas.carga import cargar_pronostico_mp25

    csv = tmp_path / "coronel.csv"
    csv.write_text("fecha_hora,pm2_5,pm10\n2026-05-18T00:00,42,50\n", encoding="utf-8")
    nombre = next(n for n, d in _estaciones_open_meteo(PARAMETROS).items() if d["comuna"] == "Coronel")
    emitido = datetime(2026, 5, 17, 12, tzinfo=UTC)

    cargar_pronostico_mp25(sesion, csv, emitido_en=emitido, estacion=nombre)

    estacion = sesion.scalar(select(Estacion).where(Estacion.nombre == nombre))
    guardado = sesion.scalar(select(PronosticoAmbiental).where(
        PronosticoAmbiental.estacion_id == estacion.id, PronosticoAmbiental.tipo == TipoMedicion.MP25))
    assert guardado.valor == 42


def test_rf4_descarga_carga_cada_punto_en_su_estacion(sesion, tmp_path):
    """La descarga pide los 10 puntos en una consulta y guarda cada serie en la estación de su comuna."""
    from sart.tareas.descarga import correr_descarga

    parametros = copy.deepcopy(PARAMETROS)
    parametros["ingesta"]["reintentos_fuente"] = 0
    puntos = puntos_pronostico(parametros)
    valores = [10 + i for i in range(len(puntos))]

    def obtener(url, destino, **kwargs):
        if url.startswith(parametros["descarga"]["open_meteo"]["pronostico_url"]):
            assert url.count("%2C") >= 2 * (len(puntos) - 1)  # latitudes y longitudes separadas por comas
            destino.write_text(json.dumps(_respuesta(valores)), encoding="utf-8")
        else:
            raise OSError("solo se prueba el pronóstico")

    correr_descarga(sesion, carpeta=tmp_path / "crudos", fecha=date(2026, 5, 17), parametros=parametros,
                    obtener=obtener, esperar=lambda s: None)

    for (nombre, _, _), valor in zip(puntos, valores, strict=True):
        estacion = sesion.scalar(select(Estacion).where(Estacion.nombre == nombre))
        guardado = sesion.scalar(select(PronosticoAmbiental).where(
            PronosticoAmbiental.estacion_id == estacion.id, PronosticoAmbiental.tipo == TipoMedicion.MP25))
        assert guardado is not None and guardado.valor == valor, nombre
