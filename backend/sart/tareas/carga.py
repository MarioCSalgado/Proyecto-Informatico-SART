"""Carga del catálogo (zonas, estaciones y centros) y de las consultas semanales del DEIS (CI-3, RB-5, RF-1).

Las dos cargas se pueden repetir: actualizan lo que ya existe en vez de duplicarlo. La ingesta programada de
las 05:00 (RF-1) usará ``cargar_consultas`` después de descargar el archivo; la marca de semana incompleta
(RB-4) se calcula en la parte 5 (TC-01), por eso ``semana_carga.completa`` queda sin evaluar.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pandas as pd
from sqlalchemy import select
from sqlalchemy.dialects import postgresql, sqlite
from sqlalchemy.orm import Session

from sart.db.modelos import CentroSalud, ConsultaSemanal, Estacion, SemanaCarga, Zona
from sart.dominio.catalogo import clave_causa, estacion_de_comuna, normalizar, tipo_centro
from sart.dominio.valores import GRUPOS_EDAD_DEIS, FuenteEstacion
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
FILAS_POR_LOTE = 5000


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
        codigo = _entero(fila[col["codigo"]])
        centro = centros.get(codigo) or CentroSalud(codigo_deis=codigo)
        centro.codigo_antiguo = _entero(fila.get(col["codigo_antiguo"]))
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
    for inicio in range(0, len(filas), FILAS_POR_LOTE):
        lote = filas[inicio : inicio + FILAS_POR_LOTE]
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
    centros = {c.codigo_antiguo: c.id for c in sesion.scalars(select(CentroSalud)) if c.codigo_antiguo}
    if not centros:
        raise ValueError("No hay centros en el catálogo: primero cargue el catálogo de establecimientos.")

    datos = pd.read_parquet(ruta_urgencias)
    _exigir_columnas(datos, {**COLUMNAS_URGENCIAS, **{c: c for c in GRUPOS_EDAD_DEIS}}, ruta_urgencias)
    col = COLUMNAS_URGENCIAS
    resumen = ResumenConsultas()

    en_catalogo = datos[col["establecimiento"]].isin(centros)
    resumen.establecimientos_sin_catalogo = int(datos.loc[~en_catalogo, col["establecimiento"]].nunique())
    datos = datos[en_catalogo].copy()

    claves = {g: clave_causa(g, parametros["ingesta"]["causas"]) for g in datos[col["causa"]].unique()}
    datos["causa_clave"] = datos[col["causa"]].map(claves)
    omitidas = Counter(datos.loc[datos["causa_clave"].isna(), col["causa"]])
    resumen.causas_omitidas = dict(omitidas)
    datos = datos[datos["causa_clave"].notna()]

    largo = datos.melt(
        id_vars=[col["establecimiento"], col["anio"], col["semana"], "causa_clave"],
        value_vars=list(GRUPOS_EDAD_DEIS),
        var_name="grupo",
        value_name="cantidad",
    )
    filas = [
        {
            "centro_id": centros[int(f[col["establecimiento"]])],
            "anio": int(f[col["anio"]]),
            "semana": int(f[col["semana"]]),
            "causa": f["causa_clave"],
            "grupo_edad": GRUPOS_EDAD_DEIS[f["grupo"]],
            "cantidad": int(f["cantidad"]),
        }
        for f in largo.to_dict("records")
    ]
    _insertar_o_actualizar(
        sesion,
        ConsultaSemanal,
        filas,
        claves=["centro_id", "anio", "semana", "causa", "grupo_edad"],
        actualizar=["cantidad"],
    )

    por_semana = datos.groupby([col["anio"], col["semana"]])[col["establecimiento"]].nunique()
    semanas = [
        {"anio": int(anio), "semana": int(semana), "centros_reportados": int(n), "completa": None}
        for (anio, semana), n in por_semana.items()
    ]
    _insertar_o_actualizar(
        sesion, SemanaCarga, semanas, claves=["anio", "semana"], actualizar=["centros_reportados", "completa"]
    )
    sesion.commit()

    resumen.filas = len(filas)
    resumen.centros = int(datos[col["establecimiento"]].nunique())
    resumen.semanas = len(semanas)
    return resumen
