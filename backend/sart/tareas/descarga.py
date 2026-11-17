"""Descarga y carga de fuentes (T2, RF-1, TC-02, RNF-M-3).

Uso: python -m sart.tareas.descarga [--fecha AAAA-MM-DD] [--carpeta RUTA]
El catálogo debe estar cargado. La programación horaria corresponde a T11.
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
import tempfile
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any
from urllib.parse import urlencode, urlsplit, urlunsplit
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo

import pandas as pd
from sart.configuracion import RAIZ_REPOSITORIO
from sart.db.modelos import CentroSalud, Estacion
from sart.db.sesion import crear_motor
from sart.db.supuestos import parametros_vigentes
from sart.dominio.valores import FuenteEstacion
from sart.tareas.carga import (
    COLUMNAS_SINCA,
    _leer_csv,
    cargar_clima,
    cargar_consultas,
    cargar_pronostico_mp25,
    cargar_sinca,
)
from sart.tareas.corridas import fallas_seguidas, hay_que_avisar, registrar_corrida
from sqlalchemy import select
from sqlalchemy.orm import Session


@dataclass
class ResumenDescarga:
    cargadas: dict[str, int] = field(default_factory=dict)
    fallidas: dict[str, str] = field(default_factory=dict)
    avisos: list[str] = field(default_factory=list)
    omitidas: list[str] = field(default_factory=list)

    def texto(self) -> str:
        lineas = [
            f"{fuente}: {filas} registros cargados."
            for fuente, filas in self.cargadas.items()
        ]
        lineas += [
            f"ERROR {fuente}: {mensaje}" for fuente, mensaje in self.fallidas.items()
        ]
        lineas += [f"AVISO: {aviso}" for aviso in self.avisos]
        lineas += [f"SIN URL CONFIGURADA: {nombre}" for nombre in self.omitidas]
        return "\n".join(lineas)


def descargar_http(
    url: str, destino: Path, *, timeout: float, maximo_bytes: int
) -> None:
    """Guarda bytes crudos, limitando tamaño y rechazando respuestas HTTP fallidas."""
    peticion = Request(
        url, headers={"User-Agent": "Mozilla/5.0 (SART, proyecto academico)"}
    )
    with urlopen(peticion, timeout=timeout) as respuesta, destino.open("wb") as archivo:
        total = 0
        while bloque := respuesta.read(1024 * 1024):
            total += len(bloque)
            if total > maximo_bytes:
                raise ValueError("La descarga supera el tamaño máximo configurado.")
            archivo.write(bloque)
    if not total:
        raise ValueError("La fuente devolvió un archivo vacío.")


def url_sinca(url: str, *, desde: date, hasta: date) -> str:
    """Actualiza las fechas sin modificar los demás parámetros."""
    partes = urlsplit(url)
    for parametro in partes.query.split("&"):
        clave, _, valor = parametro.partition("=")
        if clave == "from":
            desde = max(desde, datetime.strptime(valor, "%y%m%d").date())
    fechas = {
        "from": desde.strftime("%y%m%d"),
        "to": hasta.strftime("%y%m%d"),
    }
    parametros = []

    for parametro in partes.query.split("&"):
        clave = parametro.partition("=")[0]
        if clave in fechas:
            parametro = f"{clave}={fechas.pop(clave)}"
        parametros.append(parametro)

    parametros.extend(f"{clave}={valor}" for clave, valor in fechas.items())

    return urlunsplit((
        partes.scheme,
        partes.netloc,
        partes.path,
        "&".join(parametros),
        partes.fragment,
    ))


def _url_api(base: str, parametros: dict) -> str:
    return base + ("&" if "?" in base else "?") + urlencode(parametros)


def _fecha(valor) -> date:
    return valor if isinstance(valor, date) else date.fromisoformat(str(valor))


def _json(ruta: Path, clave: str) -> dict:
    contenido = json.loads(ruta.read_text(encoding="utf-8"))
    if not isinstance(contenido, dict) or contenido.get("error"):
        raise ValueError("La API devolvió un error o un JSON inesperado.")
    datos = contenido.get(clave)
    if not isinstance(datos, dict) or not datos.get("time"):
        raise ValueError(f"La respuesta no contiene datos {clave}.")
    return datos


def convertir_clima(crudo: Path, destino: Path) -> None:
    diario = _json(crudo, "daily")
    tabla = pd.DataFrame(
        {
            "fecha": diario["time"],
            "temp_media": diario["temperature_2m_mean"],
            "temp_min": diario["temperature_2m_min"],
        }
    )
    if "relative_humidity_2m_mean" in diario:
        tabla["humedad"] = diario["relative_humidity_2m_mean"]
    if tabla.temp_media.isna().all() or tabla.temp_min.isna().all():
        raise ValueError("El clima no contiene temperaturas utilizables.")
    pd.to_datetime(tabla.fecha, errors="raise")
    if tabla.fecha.duplicated().any():
        raise ValueError("El clima contiene fechas repetidas.")
    for columna in tabla.columns.drop("fecha"):
        tabla[columna] = pd.to_numeric(tabla[columna], errors="raise")
    tabla.to_csv(destino, index=False)


def convertir_pronostico(crudo: Path, destino: Path) -> None:
    horas = _json(crudo, "hourly")
    tabla = pd.DataFrame(
        {"fecha_hora": horas["time"], "pm2_5": horas["pm2_5"], "pm10": horas["pm10"]}
    )
    momentos = pd.to_datetime(tabla.fecha_hora, errors="raise")
    if momentos.duplicated().any():
        raise ValueError("El pronóstico contiene horas repetidas.")
    for columna in ("pm2_5", "pm10"):
        tabla[columna] = pd.to_numeric(tabla[columna], errors="raise")
        if tabla[columna].isna().all() or tabla[columna].lt(0).any():
            raise ValueError(f"El pronóstico no contiene valores válidos de {columna}.")
    tabla.to_csv(destino, index=False)


def _validar_sinca(ruta: Path) -> None:
    datos = _leer_csv(ruta)
    faltantes = set(COLUMNAS_SINCA.values()) - set(datos.columns)
    if faltantes:
        raise ValueError("SINCA: faltan columnas: " + ", ".join(sorted(faltantes)))
    if datos.empty:
        raise ValueError("SINCA devolvió solo la cabecera, sin mediciones.")


def _publicar(origen: Path, destino: Path) -> None:
    """El archivo anterior se sustituye solo por un candidato aceptado por la carga."""
    destino.parent.mkdir(parents=True, exist_ok=True)
    origen.replace(destino)


def _procesar(
    sesion: Session,
    resumen: ResumenDescarga,
    *,
    fuente: str,
    url: str,
    carpeta: Path,
    parametros: dict,
    preparar: Callable,
    obtener: Callable,
    esperar: Callable,
) -> None:
    cfg = parametros["descarga"]
    reintentos = int(parametros["ingesta"]["reintentos_fuente"])
    if reintentos < 0:
        raise ValueError("ingesta.reintentos_fuente no puede ser negativo.")
    try:
        with registrar_corrida(sesion, "descarga_y_carga", fuente) as corrida:
            # Una corrida por fuente; los intentos internos no cuentan como corridas consecutivas.
            for intento in range(reintentos + 1):
                try:
                    with tempfile.TemporaryDirectory(
                        prefix=".sart_descarga_", dir=carpeta
                    ) as temporal:
                        crudo = Path(temporal) / "respuesta"
                        obtener(
                            url,
                            crudo,
                            timeout=float(cfg["timeout_segundos"]),
                            maximo_bytes=int(cfg["maximo_bytes"]),
                        )
                        filas, publicaciones = preparar(crudo)
                        if filas <= 0:
                            raise ValueError(
                                "La fuente no aportó registros utilizables; se conserva el archivo anterior."
                            )
                        for origen, destino in publicaciones:
                            _publicar(origen, destino)
                        corrida.filas = filas
                        resumen.cargadas[fuente] = filas
                    break
                except Exception:
                    sesion.rollback()
                    if intento == reintentos:
                        raise
                    esperar(float(cfg["espera_reintento_segundos"]))
    except Exception as error:
        resumen.fallidas[fuente] = f"{type(error).__name__}: {error}"
        if hay_que_avisar(sesion, fuente, parametros):
            resumen.avisos.append(
                f"{fuente} falló {fallas_seguidas(sesion, fuente)} corridas consecutivas."
            )


def correr_descarga(
    sesion: Session,
    *,
    carpeta: Path,
    fecha: date | None = None,
    parametros: dict[str, Any] | None = None,
    obtener: Callable = descargar_http,
    esperar: Callable = time.sleep,
) -> ResumenDescarga:
    """RF-1: fuentes independientes; una falla no cancela la descarga de las demás."""
    parametros = parametros or parametros_vigentes(sesion)
    cfg = parametros["descarga"]
    fecha = fecha or datetime.now(ZoneInfo(parametros["zona_horaria"])).date()
    carpeta = Path(carpeta)
    carpeta.mkdir(parents=True, exist_ok=True)
    if sesion.scalar(select(CentroSalud.id).limit(1)) is None:
        raise ValueError(
            "Primero cargue el catálogo de establecimientos (precondición de RF-1)."
        )
    estaciones = set(
        sesion.scalars(
            select(Estacion.nombre).where(Estacion.fuente == FuenteEstacion.SINCA)
        )
    )
    urls = cfg["sinca"]["estaciones"]
    if not urls:
        raise ValueError("No hay URLs SINCA configuradas.")
    desconocidas = set(urls) - estaciones
    if desconocidas:
        raise ValueError(
            f"Estaciones SINCA fuera del catálogo cargado: {', '.join(sorted(desconocidas))}."
        )
    resumen = ResumenDescarga(omitidas=sorted(estaciones - set(urls)))

    def procesar(fuente, url, preparar):
        _procesar(
            sesion,
            resumen,
            fuente=fuente,
            url=url,
            carpeta=carpeta,
            parametros=parametros,
            preparar=preparar,
            obtener=obtener,
            esperar=esperar,
        )

    def deis(crudo):
        candidato = crudo.with_suffix(".parquet")
        crudo.rename(candidato)
        r = cargar_consultas(sesion, candidato, parametros)
        return r.filas, [(candidato, carpeta / "at_urg_respiratorio_semanal.parquet")]

    procesar("DEIS", cfg["deis_url"], deis)
    for nombre, url in urls.items():

        def sinca(crudo, nombre=nombre):
            _validar_sinca(crudo)
            directorio = crudo.parent / "sinca"
            directorio.mkdir()
            candidato = directorio / f"{nombre}.csv"
            shutil.copyfile(crudo, candidato)
            r = cargar_sinca(sesion, directorio, parametros)
            return r.filas, [(candidato, carpeta / "sinca" / f"{nombre}.csv")]

        hasta = fecha - timedelta(days=int(cfg["sinca"]["retraso_dias"]))
        procesar(
            f"SINCA/{nombre}",
            url_sinca(url, desde=_fecha(cfg["sinca"]["desde"]), hasta=hasta),
            sinca,
        )
    coord = cfg["open_meteo"]
    comunes = {
        "latitude": coord["latitud"],
        "longitude": coord["longitud"],
        "timezone": parametros["zona_horaria"],
    }
    hasta = fecha - timedelta(days=int(coord["retraso_clima_dias"]))
    url_clima = _url_api(
        coord["clima_url"],
        {
            **comunes,
            "start_date": f"{parametros['modelo']['anio_inicio']}-01-01",
            "end_date": str(hasta),
            "daily": "temperature_2m_mean,temperature_2m_min,relative_humidity_2m_mean",
        },
    )

    def clima(crudo):
        csv = crudo.with_suffix(".csv")
        convertir_clima(crudo, csv)
        r = cargar_clima(sesion, csv, parametros)
        return r.filas, [
            (crudo, carpeta / "clima_openmeteo.json"),
            (csv, carpeta / "clima_openmeteo.csv"),
        ]

    procesar("Open-Meteo/clima", url_clima, clima)
    url_mp = _url_api(
        coord["pronostico_url"],
        {
            **comunes,
            "hourly": "pm2_5,pm10",
            "forecast_days": coord["dias_pronostico"],
        },
    )

    def pronostico(crudo):
        csv = crudo.with_suffix(".csv")
        convertir_pronostico(crudo, csv)
        r = cargar_pronostico_mp25(sesion, csv, parametros)
        return r.filas, [
            (crudo, carpeta / "pronostico_mp25_openmeteo.json"),
            (csv, carpeta / "pronostico_mp25_openmeteo.csv"),
        ]

    procesar("Open-Meteo/pronostico", url_mp, pronostico)
    return resumen


def main(argv: list[str] | None = None) -> int:
    analizador = argparse.ArgumentParser(
        description="Descarga y carga de las fuentes de SART (T2)."
    )
    analizador.add_argument(
        "--fecha", type=date.fromisoformat, help="fecha de referencia AAAA-MM-DD"
    )
    analizador.add_argument(
        "--carpeta", type=Path, default=RAIZ_REPOSITORIO / "datos" / "crudos"
    )
    args = analizador.parse_args(argv)
    motor = None
    try:
        motor = crear_motor()
        with Session(motor) as sesion:
            resumen = correr_descarga(sesion, carpeta=args.carpeta, fecha=args.fecha)
        print(resumen.texto())
        return 1 if resumen.fallidas else 0
    except Exception as error:
        print(
            f"No se completó la ingesta: {type(error).__name__}: {error}",
            file=sys.stderr,
        )
        return 1
    finally:
        if motor is not None:
            motor.dispose()


if __name__ == "__main__":
    sys.exit(main())
