"""Panel semanal por centro para el modelo de pronóstico (RF-2, CI-1, RB-4, RB-5). Lógica pura con pandas.

Migrado del notebook 5 (``conteos_semanales``, ``mp25_semanal``, ``clima_semanal``, ``agregar_rezago``,
``agregar_rezago_global`` y ``construir_panel``). La lectura desde la base está en ``sart.tareas.panel``.

Una fila por centro y semana epidemiológica con:
- ``y``: consultas respiratorias (las 6 causas J00–J98) y ``viral``: influenza y COVID-19 (pendientes #26),
  sumadas en la base por ``sart.tareas.panel.leer_conteos_semanales``;
- MP2,5 de la estación asignada al centro (CI-3), o el de la estación de respaldo si esa semana no tiene dato
  (RB-5, ``mp25_de_respaldo``), y el clima del punto de Open-Meteo;
- los rezagos por fecha (no por posición: una semana faltante no desordena los rezagos), la estacionalidad,
  la tendencia y la marca ``excluido`` de los años de pandemia.

Con ``semanas_a_pronosticar`` se agrega, para cada centro, una fila sin ``y`` en esas semanas: sus rezagos
salen de las semanas anteriores y es la fila que el modelo pronostica (RF-2 paso 2).
"""

from __future__ import annotations

from collections.abc import Iterable
from datetime import date

import numpy as np
import pandas as pd

from sart.dominio.modelo import terminos_estacionales
from sart.dominio.semanas import inicio_semana, semana_epidemiologica

CLAVES = ["estab", "anio", "semana"]
COLUMNAS_MP25 = ["mp25", "mp25_max", "dias_sobre_umbral"]
# Grupos de edad de consulta_semanal (sart.dominio.valores.GRUPOS_EDAD_DEIS): definiciones, no supuestos
GRUPOS_MENORES_5 = ("menores_1", "de_1_a_4")
GRUPOS_65_Y_MAS = ("de_65_y_mas",)


def _con_semana(diario: pd.DataFrame, columna_fecha: str = "fecha") -> pd.DataFrame:
    d = diario.copy()
    dias = pd.to_datetime(d[columna_fecha]).dt.date
    pares = {dia: semana_epidemiologica(dia) for dia in set(dias)}
    d["anio"] = dias.map(lambda dia: pares[dia][0]).astype(int)
    d["semana"] = dias.map(lambda dia: pares[dia][1]).astype(int)
    return d


def mp25_semanal(diario: pd.DataFrame, *, umbral_diario: float) -> pd.DataFrame:
    """MP2,5 diario (estacion, fecha, mp25) → media, máximo y días sobre la norma, por estación y semana.

    «Sobre la norma» es estrictamente mayor que ``umbral_diario`` (``mp25_niveles.normal_hasta``, RB-1).
    """
    if diario.empty:
        return pd.DataFrame(columns=["estacion", "anio", "semana", *COLUMNAS_MP25])
    d = _con_semana(diario)
    d["sobre"] = (d["mp25"] > umbral_diario).astype(int)
    return (
        d.groupby(["estacion", "anio", "semana"])
        .agg(mp25=("mp25", "mean"), mp25_max=("mp25", "max"), dias_sobre_umbral=("sobre", "sum"))
        .reset_index()
    )


def clima_semanal(diario: pd.DataFrame) -> pd.DataFrame:
    """Clima diario (fecha, temp, temp_min, humedad) → promedios por semana epidemiológica."""
    columnas = [c for c in ("temp", "temp_min", "humedad") if c in diario.columns]
    if diario.empty:
        return pd.DataFrame(columns=["anio", "semana", *columnas])
    d = _con_semana(diario)
    return d.groupby(["anio", "semana"])[columnas].mean().reset_index()


def agregar_rezago(
    panel: pd.DataFrame, columna: str, semanas: int, nombre: str | None = None
) -> pd.DataFrame:
    """Valor de ``columna`` ``semanas`` antes, para el mismo centro (por fecha)."""
    nombre = nombre or f"{columna}_l{semanas}"
    previo = panel[["estab", "inicio_semana", columna]].copy()
    previo["inicio_semana"] = previo["inicio_semana"] + pd.Timedelta(weeks=semanas)
    return panel.merge(previo.rename(columns={columna: nombre}), on=["estab", "inicio_semana"], how="left")


def agregar_rezago_global(panel: pd.DataFrame, columna: str, semanas: int, nombre: str) -> pd.DataFrame:
    """Rezago de una variable que depende de la semana y no del centro (el clima)."""
    por_semana = panel[["inicio_semana", columna]].dropna().drop_duplicates("inicio_semana").copy()
    por_semana["inicio_semana"] = por_semana["inicio_semana"] + pd.Timedelta(weeks=semanas)
    return panel.merge(por_semana.rename(columns={columna: nombre}), on="inicio_semana", how="left")


def _inicios(anios: pd.Series, semanas: pd.Series) -> pd.Series:
    unicos = {(int(a), int(s)) for a, s in zip(anios, semanas, strict=True)}
    fechas = {par: pd.Timestamp(inicio_semana(*par)) for par in unicos}
    return pd.Series(
        [fechas[(int(a), int(s))] for a, s in zip(anios, semanas, strict=True)], index=anios.index
    ).astype("datetime64[ns]")


def construir_panel(
    conteos: pd.DataFrame,
    centros: pd.DataFrame,
    mp25: pd.DataFrame,
    clima: pd.DataFrame,
    *,
    estacion_respaldo: str,
    anio_inicio: int,
    anios_excluidos: Iterable[int],
    armonicos: int,
    semanas_a_pronosticar: Iterable[date] = (),
) -> pd.DataFrame:
    """Panel semanal ordenado por centro y semana.

    - ``conteos``: salida de ``conteos_semanales``.
    - ``centros``: estab, estacion (nombre de la estación asignada, CI-3) y atributos (nombre_estab, comuna,
      tipo, lat, lon).
    - ``mp25``: salida de ``mp25_semanal``; ``clima``: salida de ``clima_semanal``.
    """
    panel = conteos[conteos["anio"] >= anio_inicio].copy()
    objetivos = sorted(set(semanas_a_pronosticar))
    if objetivos:
        filas = []
        for objetivo in objetivos:
            anio, semana = semana_epidemiologica(objetivo)
            filas += [{"estab": e, "anio": anio, "semana": semana} for e in centros["estab"]]
        nuevas = pd.DataFrame(filas)
        claves_nuevas = pd.MultiIndex.from_frame(nuevas[CLAVES])
        panel = panel[~pd.MultiIndex.from_frame(panel[CLAVES]).isin(claves_nuevas)]
        panel = pd.concat([panel, nuevas], ignore_index=True)
    panel = panel.merge(centros, on="estab", how="inner")
    panel["inicio_semana"] = _inicios(panel["anio"], panel["semana"])

    # Exposición: la estación asignada al centro; si esa semana no tiene dato, la de respaldo (RB-5)
    panel = panel.merge(
        mp25[["estacion", "anio", "semana", *COLUMNAS_MP25]], on=["estacion", "anio", "semana"], how="left"
    )
    respaldo = mp25[mp25["estacion"] == estacion_respaldo][["anio", "semana", *COLUMNAS_MP25]].rename(
        columns={c: f"{c}_resp" for c in COLUMNAS_MP25}
    )
    panel = panel.merge(respaldo, on=["anio", "semana"], how="left")
    panel["mp25_de_respaldo"] = panel["mp25"].isna() & panel["mp25_resp"].notna()
    for c in COLUMNAS_MP25:
        panel[c] = panel[c].fillna(panel[f"{c}_resp"])
    panel = panel.drop(columns=[f"{c}_resp" for c in COLUMNAS_MP25])

    panel = panel.merge(clima, on=["anio", "semana"], how="left")

    panel = agregar_rezago(panel, "y", 1)
    panel = agregar_rezago(panel, "y", 2)
    panel = agregar_rezago(panel, "y", 52)
    panel = agregar_rezago(panel, "viral", 1)
    panel = agregar_rezago(panel, "mp25", 1)
    panel = agregar_rezago(panel, "dias_sobre_umbral", 1)
    if "temp" in panel:
        panel = agregar_rezago_global(panel, "temp", 1, "temp_l1")

    panel["log_y_l1"] = np.log1p(panel["y_l1"])
    panel["log_y_l2"] = np.log1p(panel["y_l2"])
    panel["log_viral_l1"] = np.log1p(panel["viral_l1"])
    panel = panel.assign(**terminos_estacionales(panel["semana"], armonicos))
    panel["tendencia"] = (panel["inicio_semana"] - pd.Timestamp(f"{anio_inicio}-01-01")).dt.days / 365.25
    panel["excluido"] = panel["anio"].isin(list(anios_excluidos))
    return panel.sort_values(["estab", "inicio_semana"]).reset_index(drop=True)
