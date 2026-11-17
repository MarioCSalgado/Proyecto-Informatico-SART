"""Carga del catálogo (zonas, estaciones y centros), de las consultas semanales del DEIS y de las mediciones
ambientales de SINCA y Open-Meteo (CI-3, RB-5, RF-1, RF-4).

Todas las cargas se pueden repetir: actualizan lo que ya existe en vez de duplicarlo. La ingesta programada de
las 05:00 (RF-1) usará ``cargar_consultas`` después de descargar el archivo; la marca de semana incompleta
(RB-4) se recalcula al final de cada carga de consultas (``semanas_y_umbrales.marcar_semanas``).
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Any

import pandas as pd
from sqlalchemy import func, select
from sqlalchemy.dialects import postgresql, sqlite
from sqlalchemy.orm import Session

from sart.db.modelos import CentroSalud, ConsultaSemanal, Estacion, Medicion, Zona
from sart.dominio.catalogo import estacion_de_comuna, normalizar, tipo_centro
from sart.dominio.ingesta_deis import CLAVE, codigo_deis, normalizar_consultas
from sart.dominio.mediciones import valor_sinca
from sart.dominio.valores import (
    UNIDAD_POR_TIPO,
    FuenteEstacion,
    OrigenMedicion,
    TipoMedicion,
)
from sart.parametros import cargar_parametros

# Columnas de los archivos del MINSAL (esquema de la fuente, no supuestos del modelo)
COLUMNAS_ESTABLECIMIENTOS = {
    "codigo": "EstablecimientoCodigo",
    "codigo_antiguo": "EstablecimientoCodigoAntiguo",
    "nombre": "EstablecimientoGlosa",
    "comuna": "ComunaGlosa",
    "tipo": "TipoEstablecimientoGlosa",
    "latitud": "Latitud",
    "longitud": "Longitud",
}
COLUMNAS_URGENCIAS = {
    "establecimiento": "IdEstablecimiento",
    "anio": "Anio",
    "semana": "SemanaEstadistica",
    "causa": "Causa",
}
COLUMNAS_SINCA = {
    "fecha": "FECHA (YYMMDD)",
    "hora": "HORA (HHMM)",
    "validado": "Registros validados",
    "preliminar": "Registros preliminares",
    "no_validado": "Registros no validados",
}
# Columnas de los CSV de Open-Meteo que guarda el prototipo (notebook 5) → tipo de medición
COLUMNAS_CLIMA = {
    TipoMedicion.TEMPERATURA_MEDIA: "temp_media",
    TipoMedicion.TEMPERATURA_MINIMA: "temp_min",
    TipoMedicion.HUMEDAD: "humedad",
}
COLUMNAS_PRONOSTICO_MP = {TipoMedicion.MP25: "pm2_5", TipoMedicion.MP10: "pm10"}
# Parámetros por INSERT: SQLite acepta hasta 32.766 y PostgreSQL hasta 65.535
PARAMETROS_POR_LOTE = 30000


@dataclass
class ResumenCatalogo:
    zonas: int = 0
    estaciones: int = 0
    centros: int = 0
    omitidos_fuera_del_escenario: int = 0
    omitidos_por_tipo: int = 0


@dataclass
class ResumenConsultas:
    filas: int = 0
    centros: int = 0
    semanas: int = 0
    establecimientos_sin_catalogo: int = 0
    causas_omitidas: dict[str, int] = field(default_factory=dict)
    ultima_semana_completa: date | None = None
    filas_sin_codigo: int = 0
    duplicados_omitidos: int = 0


def _leer_csv(ruta: Path) -> pd.DataFrame:
    """Los CSV del MINSAL vienen con ';' y a veces en Latin-1."""
    for codificacion in ("utf-8-sig", "latin-1"):
        try:
            return pd.read_csv(ruta, sep=";", encoding=codificacion, dtype=str)
        except UnicodeDecodeError:
            continue
    raise ValueError(f"No se pudo leer {ruta}: codificación desconocida")


def _numero(texto: Any) -> float | None:
    if texto is None or pd.isna(texto) or str(texto).strip() == "":
        return None
    return float(str(texto).replace(",", "."))


def _entero(texto: Any) -> int | None:
    numero = _numero(texto)
    return int(numero) if numero is not None else None


def _exigir_columnas(datos: pd.DataFrame, columnas: dict[str, str], ruta: Path) -> None:
    faltantes = [c for c in columnas.values() if c not in datos.columns]
    if faltantes:
        raise ValueError(f"A {ruta.name} le faltan las columnas: {', '.join(faltantes)}")


def cargar_catalogo(
    sesion: Session, ruta_establecimientos: Path, parametros: dict[str, Any] | None = None
) -> ResumenCatalogo:
    """Crea o actualiza las zonas (una por comuna), las estaciones y los centros de urgencia del escenario."""
    parametros = parametros or cargar_parametros()
    escenario, catalogo = parametros["escenario"], parametros["catalogo"]
    resumen = ResumenCatalogo()

    zonas = {z.nombre: z for z in sesion.scalars(select(Zona))}
    for comuna in escenario["comunas"]:
        zonas.setdefault(comuna, Zona(nombre=comuna))
        sesion.add(zonas[comuna])
    resumen.zonas = len(escenario["comunas"])

    def zona_de(comuna: str) -> Zona:
        por_nombre = {normalizar(n): z for n, z in zonas.items()}
        zona = por_nombre.get(normalizar(comuna))
        if zona is None:
            raise ValueError(f"La comuna {comuna} no está en escenario.comunas de parametros.yaml")
        return zona

    estaciones = {e.nombre: e for e in sesion.scalars(select(Estacion))}
    for nombre, datos in catalogo["estaciones"].items():
        estacion = estaciones.get(nombre) or Estacion(nombre=nombre)
        estacion.comuna = datos["comuna"]
        estacion.zona = zona_de(datos["comuna"])
        estacion.fuente = FuenteEstacion(datos["fuente"])
        estacion.codigo_sinca = datos.get("codigo_sinca")
        estacion.latitud = datos.get("latitud")
        estacion.longitud = datos.get("longitud")
        estacion.es_respaldo = nombre == escenario["estacion_respaldo"]
        estaciones[nombre] = estacion
        sesion.add(estacion)
    resumen.estaciones = len(catalogo["estaciones"])

    registro = _leer_csv(ruta_establecimientos)
    _exigir_columnas(registro, COLUMNAS_ESTABLECIMIENTOS, ruta_establecimientos)
    comunas_escenario = {normalizar(c) for c in escenario["comunas"]}
    centros = {c.codigo_deis: c for c in sesion.scalars(select(CentroSalud))}
    col = COLUMNAS_ESTABLECIMIENTOS
    for fila in registro.to_dict("records"):
        if normalizar(fila[col["comuna"]] or "") not in comunas_escenario:
            resumen.omitidos_fuera_del_escenario += 1
            continue
        tipo = tipo_centro(fila[col["tipo"]], catalogo["tipos_establecimiento"])
        if tipo is None:
            resumen.omitidos_por_tipo += 1
            continue
        codigo = codigo_deis(fila[col["codigo"]])
        centro = centros.get(codigo) or CentroSalud(codigo_deis=codigo)
        centro.codigo_antiguo = codigo_deis(fila.get(col["codigo_antiguo"]))
        centro.nombre = fila[col["nombre"]].strip()
        centro.tipo = tipo
        centro.comuna = fila[col["comuna"]].strip()
        centro.latitud = _numero(fila.get(col["latitud"]))
        centro.longitud = _numero(fila.get(col["longitud"]))
        centro.zona = zona_de(centro.comuna)
        nombre_estacion = estacion_de_comuna(
            centro.comuna, catalogo["estacion_por_comuna"], escenario["estacion_respaldo"]
        )
        centro.estacion = estaciones[nombre_estacion]
        centros[codigo] = centro
        sesion.add(centro)
        resumen.centros += 1

    sesion.commit()
    return resumen


def _insertar_o_actualizar(
    sesion: Session, modelo, filas: list[dict], claves: list[str], actualizar: list[str]
):
    """INSERT … ON CONFLICT DO UPDATE en PostgreSQL y en SQLite (las pruebas)."""
    dialecto = sesion.get_bind().dialect.name
    modulo = {"postgresql": postgresql, "sqlite": sqlite}.get(dialecto)
    if modulo is None:
        raise NotImplementedError(f"Carga no disponible para la base {dialecto}")
    if not filas:
        return
    filas_por_lote = max(1, PARAMETROS_POR_LOTE // len(filas[0]))
    for inicio in range(0, len(filas), filas_por_lote):
        lote = filas[inicio : inicio + filas_por_lote]
        orden = modulo.insert(modelo).values(lote)
        orden = orden.on_conflict_do_update(
            index_elements=claves, set_={c: getattr(orden.excluded, c) for c in actualizar}
        )
        sesion.execute(orden)


def cargar_consultas(
    sesion: Session, ruta_urgencias: Path, parametros: dict[str, Any] | None = None
) -> ResumenConsultas:
    """Pasa el archivo semanal de urgencias del DEIS a ``consulta_semanal`` (un registro por centro, semana,
    causa y grupo de edad) y registra cada semana en ``semana_carga``."""
    parametros = parametros or cargar_parametros()
    catalogo = list(sesion.scalars(select(CentroSalud)))
    if not catalogo:
        raise ValueError("No hay centros en el catálogo: primero cargue el catálogo de establecimientos.")

    datos = pd.read_parquet(ruta_urgencias)
    real = "EstablecimientoCodigo" in datos
    centros = {
        (c.codigo_deis if real else c.codigo_antiguo): c.id
        for c in catalogo
        if (c.codigo_deis if real else c.codigo_antiguo) is not None
    }
    normalizadas, metricas = normalizar_consultas(datos, centros, parametros["ingesta"]["causas"])
    anios = metricas.pop("anios_origen", None)
    resumen = ResumenConsultas(**metricas)
    if normalizadas.empty:
        raise ValueError("El archivo no contiene consultas admitidas de centros del catálogo.")
    if real and anios:
        # Sin una tabla de procedencia no es seguro corregir solo un año de una copia histórica.
        menor, mayor = sesion.execute(
            select(func.min(ConsultaSemanal.anio), func.max(ConsultaSemanal.anio))
        ).one()
        if menor is not None and (anios[0] > menor or anios[1] < mayor):
            raise ValueError("La recarga real requiere la copia histórica completa, no un recorte anual.")
    filas = normalizadas.to_dict("records")
    from sart.tareas.semanas_y_umbrales import marcar_semanas  # evita la importación circular

    try:
        _insertar_o_actualizar(sesion, ConsultaSemanal, filas, claves=CLAVE, actualizar=["cantidad"])
        resumen.ultima_semana_completa = marcar_semanas(sesion, confirmar=False)
        sesion.commit()
    except Exception:
        sesion.rollback()
        raise
    resumen.filas = len(filas)
    resumen.centros = int(normalizadas.centro_id.nunique())
    resumen.semanas = len(normalizadas[["anio", "semana"]].drop_duplicates())
    return resumen


# ---------------------------------------------------------------------------
# Mediciones ambientales (RF-1, RF-4, RB-5)
# ---------------------------------------------------------------------------
@dataclass
class ResumenMediciones:
    filas: int = 0
    estaciones: int = 0
    sin_dato: int = 0
    archivos_sin_estacion: list[str] = field(default_factory=list)


def _a_utc(locales: pd.Series, zona_horaria: str) -> pd.Series:
    """Horas locales (sin zona) a UTC. Las que no existen por el cambio de hora se corren hacia adelante; las
    que se repiten (ambiguas) quedan vacías y se cuentan como sin dato."""
    return (
        pd.to_datetime(locales)
        .dt.tz_localize(zona_horaria, ambiguous="NaT", nonexistent="shift_forward")
        .dt.tz_convert("UTC")
    )


def _guardar_mediciones(sesion: Session, filas: list[dict]) -> None:
    _insertar_o_actualizar(
        sesion,
        Medicion,
        filas,
        claves=["estacion_id", "tipo", "origen", "fecha_hora"],
        actualizar=["valor", "unidad", "calidad"],
    )


def _estacion_open_meteo(sesion: Session) -> Estacion:
    estaciones = sesion.scalars(select(Estacion).where(Estacion.fuente == FuenteEstacion.OPEN_METEO)).all()
    if not estaciones:
        raise ValueError("No hay estación de Open-Meteo: primero cargue el catálogo (catalogo.estaciones).")
    if len(estaciones) > 1:
        raise ValueError("Hay más de una estación de Open-Meteo en el catálogo; no se sabe a cuál cargar.")
    return estaciones[0]


def cargar_sinca(
    sesion: Session, carpeta: Path, parametros: dict[str, Any] | None = None
) -> ResumenMediciones:
    """MP2,5 diario de SINCA: un archivo por estación, con el nombre de la estación del catálogo."""
    parametros = parametros or cargar_parametros()
    estaciones = {
        normalizar(e.nombre): e
        for e in sesion.scalars(select(Estacion).where(Estacion.fuente == FuenteEstacion.SINCA))
    }
    if not estaciones:
        raise ValueError("No hay estaciones de SINCA: primero cargue el catálogo (catalogo.estaciones).")
    resumen = ResumenMediciones()
    col = COLUMNAS_SINCA

    for ruta in sorted(Path(carpeta).glob("*.csv")):
        estacion = estaciones.get(normalizar(ruta.stem))
        if estacion is None:
            resumen.archivos_sin_estacion.append(ruta.name)
            continue
        datos = _leer_csv(ruta)
        _exigir_columnas(datos, col, ruta)
        locales = pd.to_datetime("20" + datos[col["fecha"]] + datos[col["hora"]], format="%Y%m%d%H%M")
        momentos = _a_utc(locales, parametros["zona_horaria"])
        filas = []
        for registro, momento in zip(datos.to_dict("records"), momentos, strict=True):
            dato = valor_sinca(
                registro[col["validado"]], registro[col["preliminar"]], registro[col["no_validado"]]
            )
            if dato is None or pd.isna(momento):
                resumen.sin_dato += 1
                continue
            valor, calidad = dato
            filas.append(
                {
                    "estacion_id": estacion.id,
                    "fecha_hora": momento.to_pydatetime(),
                    "tipo": TipoMedicion.MP25,
                    "valor": valor,
                    "unidad": UNIDAD_POR_TIPO[TipoMedicion.MP25],
                    "origen": OrigenMedicion.OBSERVADO,
                    "calidad": calidad,
                }
            )
        _guardar_mediciones(sesion, filas)
        resumen.filas += len(filas)
        resumen.estaciones += 1

    sesion.commit()
    return resumen


def _cargar_open_meteo(
    sesion: Session,
    ruta: Path,
    columna_fecha: str,
    columnas: dict[TipoMedicion, str],
    origen: OrigenMedicion,
    parametros: dict[str, Any] | None,
) -> ResumenMediciones:
    parametros = parametros or cargar_parametros()
    estacion = _estacion_open_meteo(sesion)
    datos = pd.read_csv(ruta)
    _exigir_columnas(datos, {"fecha": columna_fecha}, Path(ruta))
    momentos = _a_utc(datos[columna_fecha], parametros["zona_horaria"])
    resumen = ResumenMediciones(estaciones=1)
    filas = []
    for tipo, columna in columnas.items():
        if columna not in datos.columns:  # p. ej., Open-Meteo a veces no entrega humedad
            continue
        for valor, momento in zip(datos[columna], momentos, strict=True):
            if pd.isna(valor) or pd.isna(momento):
                resumen.sin_dato += 1
                continue
            filas.append(
                {
                    "estacion_id": estacion.id,
                    "fecha_hora": momento.to_pydatetime(),
                    "tipo": tipo,
                    "valor": float(valor),
                    "unidad": UNIDAD_POR_TIPO[tipo],
                    "origen": origen,
                    "calidad": None,
                }
            )
    _guardar_mediciones(sesion, filas)
    sesion.commit()
    resumen.filas = len(filas)
    return resumen


def cargar_clima(sesion: Session, ruta: Path, parametros: dict[str, Any] | None = None) -> ResumenMediciones:
    """Clima diario observado de Open-Meteo: temperatura media y mínima, y humedad."""
    return _cargar_open_meteo(sesion, ruta, "fecha", COLUMNAS_CLIMA, OrigenMedicion.OBSERVADO, parametros)


def cargar_pronostico_mp25(
    sesion: Session, ruta: Path, parametros: dict[str, Any] | None = None
) -> ResumenMediciones:
    """Pronóstico horario de MP2,5 y MP10 de Open-Meteo para los próximos días (RF-4)."""
    return _cargar_open_meteo(
        sesion, ruta, "fecha_hora", COLUMNAS_PRONOSTICO_MP, OrigenMedicion.PRONOSTICO, parametros
    )
