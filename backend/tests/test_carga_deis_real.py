"""Integración opcional de la carga DEIS con archivos reales, sin clima ni SINCA."""

import pandas as pd
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session

from sart.db.modelos import CentroSalud, ConsultaSemanal
from sart.dominio.catalogo import clave_causa
from sart.parametros import cargar_parametros
from sart.tareas.carga import cargar_consultas


def test_carga_deis_real_conserva_cantidades_y_recarga(
    archivo_base_deis_real, archivos_deis_reales
):
    """Compara totales por causa y edad con la fuente y todas las claves tras recargar."""
    _, consultas = archivos_deis_reales
    edades = {
        "NumMenor1Anio": "menores_1",
        "Num1a4Anios": "de_1_a_4",
        "Num5a14Anios": "de_5_a_14",
        "Num15a64Anios": "de_15_a_64",
        "Num65oMas": "de_65_y_mas",
    }
    columnas = ["EstablecimientoCodigo", "Anio", "SemanaEstadistica", "Causa", *edades]
    fuente = pd.read_parquet(consultas, columns=columnas)
    causas = cargar_parametros()["ingesta"]["causas"]
    mapa = {glosa: clave_causa(glosa, causas) for glosa in fuente["Causa"].dropna().unique()}
    fuente["causa_normalizada"] = fuente["Causa"].map(mapa)
    fuente["codigo"] = pd.to_numeric(fuente["EstablecimientoCodigo"], errors="coerce")

    motor = create_engine(f"sqlite:///{archivo_base_deis_real.as_posix()}")
    try:
        with Session(motor) as sesion:
            codigos = set(sesion.scalars(select(CentroSalud.codigo_deis)))
            assert codigos, "El catálogo real no cargó centros del escenario"
            fuente = fuente.loc[
                fuente["codigo"].isin(codigos) & fuente["causa_normalizada"].notna()
            ].drop_duplicates(subset=["codigo", "Anio", "SemanaEstadistica", "Causa", *edades])
            assert not fuente.empty, "No hay consultas reales para los centros del catálogo"
            esperados = {
                (causa, grupo): int(total)
                for columna, grupo in edades.items()
                for causa, total in fuente.groupby("causa_normalizada")[columna].sum().items()
            }
            guardados = {
                (causa, grupo): int(total)
                for causa, grupo, total in sesion.execute(
                    select(
                        ConsultaSemanal.causa,
                        ConsultaSemanal.grupo_edad,
                        func.sum(ConsultaSemanal.cantidad),
                    ).group_by(ConsultaSemanal.causa, ConsultaSemanal.grupo_edad)
                )
            }
            assert guardados == esperados, "Los totales por causa y edad difieren de la fuente"
            consulta = select(
                ConsultaSemanal.centro_id,
                ConsultaSemanal.anio,
                ConsultaSemanal.semana,
                ConsultaSemanal.causa,
                ConsultaSemanal.grupo_edad,
                ConsultaSemanal.cantidad,
            ).order_by(
                ConsultaSemanal.centro_id,
                ConsultaSemanal.anio,
                ConsultaSemanal.semana,
                ConsultaSemanal.causa,
                ConsultaSemanal.grupo_edad,
            )
            antes = [tuple(fila) for fila in sesion.execute(consulta)]
            assert antes
            assert all(fila[-1] >= 0 for fila in antes)
            assert len({fila[:-1] for fila in antes}) == len(antes)
            cargar_consultas(sesion, consultas)
            despues = [tuple(fila) for fila in sesion.execute(consulta)]
            assert despues == antes, "La recarga alteró cantidades o duplicó registros"
    finally:
        motor.dispose()
