"""Carga del catálogo (zonas, estaciones y centros) y de las consultas del DEIS (CI-3, RF-1).

Los archivos de datos/prueba son sintéticos: 56 establecimientos, de los cuales 14 son centros de urgencia de
las 10 comunas del escenario; el resto (Chillán, Los Ángeles y 40 postas de Florida) queda fuera.
"""

import io
from pathlib import Path

import pandas as pd
import pytest
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session

from sart import catalogo as cli
from sart.configuracion import RAIZ_REPOSITORIO
from sart.db.modelos import Base, CentroSalud, ConsultaSemanal, Estacion, SemanaCarga, Zona
from sart.dominio.valores import FuenteEstacion, TipoCentro
from sart.tareas.carga import cargar_catalogo, cargar_consultas

PRUEBA = RAIZ_REPOSITORIO / "datos" / "prueba" / "crudos"
ESTABLECIMIENTOS = PRUEBA / "establecimientos.csv"
CONSULTAS = PRUEBA / "at_urg_respiratorio_semanal.parquet"


@pytest.fixture
def sesion():
    motor = create_engine("sqlite://")
    Base.metadata.create_all(motor)
    with Session(motor) as sesion:
        yield sesion
    motor.dispose()


@pytest.fixture
def consultas_recortadas(tmp_path) -> Path:
    """Dos semanas de 2026 y un establecimiento fuera del catálogo, para que la prueba sea rápida."""
    datos = pd.read_parquet(CONSULTAS)
    recorte = datos[(datos["Anio"] == 2026) & datos["SemanaEstadistica"].isin([38, 39])].copy()
    ajeno = recorte.iloc[[0]].assign(IdEstablecimiento=999999)
    ruta = tmp_path / "consultas.parquet"
    pd.concat([recorte, ajeno]).to_parquet(ruta)
    return ruta


def test_catalogo_carga_los_centros_de_urgencia_del_escenario(sesion):
    resumen = cargar_catalogo(sesion, ESTABLECIMIENTOS)

    centros = sesion.scalars(select(CentroSalud)).all()
    assert len(centros) == resumen.centros == 14
    assert resumen.omitidos_fuera_del_escenario == 42  # Chillán, Los Ángeles y 40 postas de Florida
    assert resumen.omitidos_por_tipo == 0
    assert {c.tipo for c in centros} == {TipoCentro.HOSPITAL, TipoCentro.SAPU, TipoCentro.SAR}


def test_establecimientos_del_escenario_que_no_son_de_urgencia_se_omiten(sesion, tmp_path):
    registro = ESTABLECIMIENTOS.read_text(encoding="latin-1")
    cesfam = (
        "200001;8001;CESFAM de prueba;Región del Biobío;Penco;Centro de Salud Familiar (CESFAM);-36,7;-72,9\n"
    )
    ruta = tmp_path / "establecimientos.csv"
    ruta.write_text(registro + cesfam, encoding="latin-1")

    resumen = cargar_catalogo(sesion, ruta)

    assert resumen.centros == 14
    assert resumen.omitidos_por_tipo == 1


def test_una_zona_por_comuna_y_estaciones_del_catalogo(sesion):
    cargar_catalogo(sesion, ESTABLECIMIENTOS)

    assert sesion.scalar(select(func.count()).select_from(Zona)) == 10
    estaciones = {e.nombre: e for e in sesion.scalars(select(Estacion))}
    assert len(estaciones) == 7
    assert estaciones["Kingston College"].es_respaldo is True  # RB-5
    assert sum(e.es_respaldo for e in estaciones.values()) == 1
    assert estaciones["Open-Meteo Concepción"].fuente is FuenteEstacion.OPEN_METEO
    assert estaciones["JUNJI"].zona.nombre == "Hualpén"


def test_cada_centro_queda_con_su_zona_y_la_estacion_de_su_comuna(sesion):
    """CI-3: estación asignada por comuna (catalogo.estacion_por_comuna)."""
    cargar_catalogo(sesion, ESTABLECIMIENTOS)

    talcahuano = sesion.scalars(select(CentroSalud).where(CentroSalud.comuna == "Talcahuano")).all()
    assert talcahuano
    assert all(c.estacion.nombre == "JUNJI" and c.zona.nombre == "Talcahuano" for c in talcahuano)
    concepcion = sesion.scalars(select(CentroSalud).where(CentroSalud.codigo_deis == 100001)).one()
    assert concepcion.codigo_antiguo == 9001
    assert concepcion.latitud == pytest.approx(-36.8)


def test_cargar_el_catalogo_dos_veces_no_duplica(sesion):
    cargar_catalogo(sesion, ESTABLECIMIENTOS)
    cargar_catalogo(sesion, ESTABLECIMIENTOS)

    assert sesion.scalar(select(func.count()).select_from(CentroSalud)) == 14
    assert sesion.scalar(select(func.count()).select_from(Zona)) == 10


def test_consultas_en_formato_largo_que_suman_lo_mismo_que_el_archivo(sesion, consultas_recortadas):
    """RF-1: un registro por centro, semana, causa y grupo de edad; los totales coinciden con el DEIS."""
    cargar_catalogo(sesion, ESTABLECIMIENTOS)

    resumen = cargar_consultas(sesion, consultas_recortadas)

    original = pd.read_parquet(consultas_recortadas)
    del_catalogo = set(sesion.scalars(select(CentroSalud.codigo_antiguo)))
    respiratorias = original[
        ~original["Causa"].str.startswith("Hospitalizaciones")
        & original["IdEstablecimiento"].isin(del_catalogo)
    ]
    total_guardado = sesion.scalar(select(func.sum(ConsultaSemanal.cantidad)))
    assert total_guardado == respiratorias["Total"].sum()
    assert resumen.filas == sesion.scalar(select(func.count()).select_from(ConsultaSemanal))
    assert resumen.establecimientos_sin_catalogo == 3  # Chillán, Los Ángeles y el agregado 999999
    assert resumen.causas_omitidas == {"Hospitalizaciones por causas respiratorias": 28}
    grupos = set(sesion.scalars(select(ConsultaSemanal.grupo_edad).distinct()))
    assert grupos == {"menores_1", "de_1_a_4", "de_5_a_14", "de_15_a_64", "de_65_y_mas"}


def test_cada_carga_marca_las_semanas_completas(sesion, consultas_recortadas):
    """RB-4 y RF-1 paso 4 (TC-01): al cargar, cada semana queda evaluada con los centros que reportaron."""
    cargar_catalogo(sesion, ESTABLECIMIENTOS)
    resumen = cargar_consultas(sesion, consultas_recortadas)

    semanas = sesion.scalars(select(SemanaCarga).order_by(SemanaCarga.semana)).all()
    assert [(s.anio, s.semana, s.centros_reportados, s.completa) for s in semanas] == [
        (2026, 38, 14, True),
        (2026, 39, 14, True),
    ]
    assert resumen.ultima_semana_completa.isoformat() == "2026-09-27"  # inicio de la SE 39 de 2026


def test_cargar_consultas_dos_veces_actualiza_sin_duplicar(sesion, consultas_recortadas):
    cargar_catalogo(sesion, ESTABLECIMIENTOS)
    primera = cargar_consultas(sesion, consultas_recortadas)
    segunda = cargar_consultas(sesion, consultas_recortadas)

    assert primera.filas == segunda.filas == sesion.scalar(select(func.count()).select_from(ConsultaSemanal))


def test_consultas_sin_catalogo_dan_error_claro(sesion, consultas_recortadas):
    with pytest.raises(ValueError, match="catálogo"):
        cargar_consultas(sesion, consultas_recortadas)


def test_comando_cargar_con_datos_de_prueba(tmp_path, monkeypatch, capsys, consultas_recortadas):
    url = f"sqlite:///{(tmp_path / 'sart.db').as_posix()}"
    motor = create_engine(url)
    Base.metadata.create_all(motor)
    motor.dispose()
    monkeypatch.setenv("DATABASE_URL", url)
    monkeypatch.setattr("sys.stdin", io.StringIO(""))

    codigo = cli.main(
        ["cargar", "--establecimientos", str(ESTABLECIMIENTOS), "--consultas", str(consultas_recortadas)]
    )

    salida = capsys.readouterr().out
    assert codigo == 0
    assert "14 centros" in salida
    assert "2 semanas" in salida


def test_comando_sin_archivos_explica_que_falta(capsys):
    assert cli.main(["cargar"]) == 1
    assert "--prueba" in capsys.readouterr().err


# RF-1 / T1
def _real(anio=2026, semana=20, cantidad=10, causa="IRA Alta (J00-J06)"):
    return {
        "EstablecimientoCodigo": "100001",
        "Anio": anio,
        "SemanaEstadistica": semana,
        "Causa": causa,
        "NumTotal": cantidad,
        "NumMenor1Anio": cantidad,
        "Num1a4Anios": 0,
        "Num5a14Anios": 0,
        "Num15a64Anios": 0,
        "Num65oMas": 0,
    }


def _cargar_real(sesion, tmp_path, filas):
    ruta = tmp_path / "real.parquet"
    pd.DataFrame(filas).to_parquet(ruta, index=False)
    return cargar_consultas(sesion, ruta)


def test_rf1_real_excluye_totales_y_conserva_covid_como_senal(sesion, tmp_path):
    cargar_catalogo(sesion, ESTABLECIMIENTOS)
    filas = [
        _real(causa=c)
        for c in [
            "IRA Alta (J00-J06)",
            "Influenza (J09-J11)",
            "TOTAL ATENCIONES POR COVID-19, Virus Identificado U07.1",
            "TOTAL ATENCIONES POR COVID-19  Virus no Identificado U07.2",
            "TOTAL CAUSA SISTEMA RESPIRATORIO (J00-J98)",
            "- Causas sistema respiratorio (J00-J98)",
            "- Por covid-19, virus identificado U07.1",
        ]
    ]
    resumen = _cargar_real(sesion, tmp_path, filas)
    from sart.parametros import cargar_parametros
    from sart.tareas.panel import leer_conteos_semanales

    p = cargar_parametros()
    panel = leer_conteos_semanales(
        sesion,
        causas_consulta=p["ingesta"]["causas_en_consultas"],
        causas_virales=p["modelo"]["causas_senal_viral"],
    )
    assert panel.iloc[0]["y"] == 20
    assert panel.iloc[0]["viral"] == 30
    assert resumen.filas == 20
    assert sum(resumen.causas_omitidas.values()) == 3


def test_rf1_real_sin_codigo_y_duplicados_no_inflan_conteos(sesion, tmp_path):
    cargar_catalogo(sesion, ESTABLECIMIENTOS)
    fila = _real()
    resumen = _cargar_real(sesion, tmp_path, [fila, fila, {**fila, "EstablecimientoCodigo": None}])
    assert resumen.filas_sin_codigo == 1
    assert resumen.duplicados_omitidos == 1
    assert sesion.scalar(select(func.sum(ConsultaSemanal.cantidad))) == 10


def test_rf1_real_conflicto_no_modifica_ultimo_dato(sesion, tmp_path):
    cargar_catalogo(sesion, ESTABLECIMIENTOS)
    _cargar_real(sesion, tmp_path, [_real()])
    with pytest.raises(ValueError, match="contradictorios"):
        _cargar_real(sesion, tmp_path, [_real(), _real(cantidad=12)])
    assert sesion.scalar(select(func.sum(ConsultaSemanal.cantidad))) == 10


@pytest.mark.parametrize(
    "columna,valor", [("NumMenor1Anio", -1), ("NumTotal", 11), ("Num1a4Anios", None), ("NumTotal", 10.5)]
)
def test_rf1_real_rechaza_conteos_invalidos(sesion, tmp_path, columna, valor):
    cargar_catalogo(sesion, ESTABLECIMIENTOS)
    with pytest.raises(ValueError):
        _cargar_real(sesion, tmp_path, [{**_real(), columna: valor}])
    assert sesion.scalar(select(func.count()).select_from(ConsultaSemanal)) == 0


def test_tc01_cruce_recarga_y_correccion_conservan_aportes(sesion, tmp_path):
    cargar_catalogo(sesion, ESTABLECIMIENTOS)
    filas = [_real(2015, 52, 9), _real(2016, 52, 10)]
    primera = _cargar_real(sesion, tmp_path, filas)
    segunda = _cargar_real(sesion, tmp_path, filas[::-1])
    assert primera.filas == segunda.filas == 10

    def total():
        return dict(
            sesion.execute(
                select(ConsultaSemanal.anio, func.sum(ConsultaSemanal.cantidad)).group_by(
                    ConsultaSemanal.anio
                )
            ).all()
        )

    assert total() == {2015: 11, 2016: 8}
    _cargar_real(sesion, tmp_path, [_real(2015, 52, 18), _real(2016, 52, 10)])
    assert total() == {2015: 20, 2016: 8}
    with pytest.raises(ValueError, match="completa"):
        _cargar_real(sesion, tmp_path, [_real(2016, 52, 10)])
    assert total() == {2015: 20, 2016: 8}


def test_rf1_fallo_de_marca_revierte_las_consultas(sesion, tmp_path, monkeypatch):
    cargar_catalogo(sesion, ESTABLECIMIENTOS)
    _cargar_real(sesion, tmp_path, [_real()])

    def fallar(*args, **kwargs):
        raise ValueError("marca fallida")

    monkeypatch.setattr("sart.tareas.semanas_y_umbrales.marcar_semanas", fallar)
    with pytest.raises(ValueError, match="marca fallida"):
        _cargar_real(sesion, tmp_path, [_real(cantidad=50)])
    assert sesion.scalar(select(func.sum(ConsultaSemanal.cantidad))) == 10


def test_catalogo_real_codigo_antiguo_con_guion(sesion, tmp_path):
    datos = pd.read_csv(ESTABLECIMIENTOS, sep=";", encoding="latin-1", dtype=str).iloc[:1]
    datos["EstablecimientoCodigoAntiguo"] = "09-001"
    ruta = tmp_path / "catalogo.csv"
    datos.to_csv(ruta, sep=";", encoding="utf-8-sig", index=False)
    cargar_catalogo(sesion, ruta)
    assert sesion.scalar(select(CentroSalud.codigo_antiguo)) == 9001


@pytest.mark.integracion
def test_rf1_real_upsert_agrupado_en_postgresql(crear_base_temporal, tmp_path):
    motor = create_engine(crear_base_temporal())
    Base.metadata.create_all(motor)
    try:
        with Session(motor) as sesion:
            cargar_catalogo(sesion, ESTABLECIMIENTOS)
            filas = [_real(2015, 52, 9), _real(2016, 52, 10)]
            _cargar_real(sesion, tmp_path, filas)
            _cargar_real(sesion, tmp_path, filas)
            assert sesion.scalar(select(func.sum(ConsultaSemanal.cantidad))) == 19
            assert sesion.scalar(select(func.count()).select_from(ConsultaSemanal)) == 10
    finally:
        motor.dispose()
