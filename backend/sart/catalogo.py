"""Comando para cargar en la base el catálogo de centros, las consultas del DEIS y las mediciones ambientales
(CI-3, RF-1, RF-4). Cada carga queda en el log de corridas (RNF-M-3).

Uso, desde ``backend/`` (con la base migrada: ``alembic upgrade head``)::

    .venv/Scripts/python -m sart.catalogo cargar --prueba          # todo, con datos/prueba
    .venv/Scripts/python -m sart.catalogo cargar --establecimientos RUTA.csv [--consultas RUTA.parquet]
        [--sinca CARPETA] [--clima RUTA.csv] [--pronostico-mp25 RUTA.csv]

Se puede repetir: actualiza lo que ya existe sin duplicar.
"""

from __future__ import annotations

import argparse
import sys
from collections.abc import Callable
from pathlib import Path

from sqlalchemy.orm import Session

from sart.configuracion import RAIZ_REPOSITORIO
from sart.db.sesion import SinBaseDeDatos, crear_motor
from sart.parametros import ErrorParametros
from sart.tareas.carga import (
    cargar_catalogo,
    cargar_clima,
    cargar_consultas,
    cargar_pronostico_mp25,
    cargar_sinca,
)
from sart.tareas.corridas import fallas_seguidas, hay_que_avisar, registrar_corrida

PRUEBA = RAIZ_REPOSITORIO / "datos" / "prueba" / "crudos"
ARCHIVOS_DE_PRUEBA = {
    "establecimientos": PRUEBA / "establecimientos.csv",
    "consultas": PRUEBA / "at_urg_respiratorio_semanal.parquet",
    "sinca": PRUEBA / "sinca",
    "clima": PRUEBA / "clima_openmeteo.csv",
    "pronostico_mp25": PRUEBA / "pronostico_mp25_openmeteo.csv",
}


def _argumentos(argv: list[str] | None) -> argparse.Namespace:
    analizador = argparse.ArgumentParser(
        prog="python -m sart.catalogo", description="Catálogo y datos de entrada."
    )
    acciones = analizador.add_subparsers(dest="accion", required=True)
    cargar = acciones.add_parser("cargar", help="carga centros y, si se indican, consultas y mediciones")
    cargar.add_argument("--prueba", action="store_true", help="usar los archivos sintéticos de datos/prueba")
    cargar.add_argument("--establecimientos", type=Path, help="registro de establecimientos (CSV del MINSAL)")
    cargar.add_argument("--consultas", type=Path, help="urgencias respiratorias semanales (parquet del DEIS)")
    cargar.add_argument("--sinca", type=Path, help="carpeta con un CSV de MP2,5 por estación de SINCA")
    cargar.add_argument("--clima", type=Path, help="clima diario de Open-Meteo (CSV)")
    cargar.add_argument(
        "--pronostico-mp25", type=Path, help="pronóstico horario de MP2,5 de Open-Meteo (CSV)"
    )
    return analizador.parse_args(argv)


def _pasos(archivos: dict[str, Path | None]) -> list[tuple[str, str, str, Callable]]:
    """(clave del archivo, tarea, fuente, función que carga y devuelve el texto del resumen)."""

    def catalogo(sesion, ruta):
        r = cargar_catalogo(sesion, ruta)
        texto = (
            f"Catálogo: {r.zonas} zonas, {r.estaciones} estaciones y {r.centros} centros. Omitidos: "
            f"{r.omitidos_fuera_del_escenario} fuera de las comunas del escenario y {r.omitidos_por_tipo} "
            "que no son de urgencia."
        )
        return r.centros, texto

    def consultas(sesion, ruta):
        r = cargar_consultas(sesion, ruta)
        texto = (
            f"Consultas: {r.filas} registros de {r.centros} centros en {r.semanas} semanas. Omitidos: "
            f"{r.establecimientos_sin_catalogo} establecimientos sin catálogo y "
            f"{sum(r.causas_omitidas.values())} filas de causas que no se cargan."
        )
        return r.filas, texto

    def mediciones(funcion, nombre):
        def cargar(sesion, ruta):
            r = funcion(sesion, ruta)
            estaciones = "1 estación" if r.estaciones == 1 else f"{r.estaciones} estaciones"
            texto = f"{nombre}: {r.filas} mediciones de {estaciones} ({r.sin_dato} sin dato)."
            if getattr(r, "archivos_sin_estacion", None):
                texto += f" Sin estación en el catálogo: {', '.join(r.archivos_sin_estacion)}."
            return r.filas, texto

        return cargar

    return [
        ("establecimientos", "carga_catalogo", "registro_establecimientos", catalogo),
        ("consultas", "carga_consultas", "DEIS", consultas),
        ("sinca", "carga_sinca", "SINCA", mediciones(cargar_sinca, "MP2,5 de SINCA")),
        ("clima", "carga_clima", "Open-Meteo", mediciones(cargar_clima, "Clima de Open-Meteo")),
        (
            "pronostico_mp25",
            "carga_pronostico_mp25",
            "Open-Meteo",
            mediciones(cargar_pronostico_mp25, "Pronóstico de MP2,5 de Open-Meteo"),
        ),
    ]


def main(argv: list[str] | None = None) -> int:
    args = _argumentos(argv)
    archivos = {clave: getattr(args, clave) for clave in ARCHIVOS_DE_PRUEBA}
    if args.prueba:
        archivos = {clave: archivos[clave] or ruta for clave, ruta in ARCHIVOS_DE_PRUEBA.items()}
    if archivos["establecimientos"] is None:
        print(
            "Indique --establecimientos RUTA.csv, o --prueba para los datos de datos/prueba.", file=sys.stderr
        )
        return 1

    try:
        motor = crear_motor()
    except SinBaseDeDatos as error:
        print(f"No se completó la carga: {error}", file=sys.stderr)
        return 1
    try:
        with Session(motor) as sesion:
            for clave, tarea, fuente, cargar in _pasos(archivos):
                ruta = archivos[clave]
                if ruta is None:
                    continue
                if clave == "consultas":
                    print("Cargando consultas (puede tardar un par de minutos)…")
                try:
                    with registrar_corrida(sesion, tarea, fuente) as corrida:
                        corrida.filas, texto = cargar(sesion, ruta)
                    print(texto)
                except (ValueError, OSError, KeyError, ErrorParametros) as error:
                    print(f"No se completó la carga de {clave}: {error}", file=sys.stderr)
                    if hay_que_avisar(sesion, fuente):
                        print(
                            f"AVISO (RNF-M-3): la fuente {fuente} falló {fallas_seguidas(sesion, fuente)} "
                            "veces seguidas.",
                            file=sys.stderr,
                        )
                    return 1
    finally:
        motor.dispose()
    return 0


if __name__ == "__main__":
    sys.exit(main())
