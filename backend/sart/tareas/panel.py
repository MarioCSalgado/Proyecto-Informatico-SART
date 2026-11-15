"""Lectura del panel semanal desde la base (RF-2, CI-3, RB-5): ``consulta_semanal`` y ``medicion`` → el panel
que espera ``sart.dominio.modelo``. El cálculo está en ``sart.dominio.panel``; aquí solo se consulta.

Las mediciones se guardan en UTC (pendientes #33); para agruparlas por día y semana se vuelven a la hora de
``zona_horaria``.
"""

from __future__ import annotations

from collections.abc import Iterable
from datetime import date
from typing import Any

import pandas as pd
from sqlalchemy import case, func, select
from sqlalchemy.orm import Session

from sart.db.modelos import CentroSalud, ConsultaSemanal, Estacion, Medicion
from sart.dominio.panel import (
    GRUPOS_65_Y_MAS,
    GRUPOS_MENORES_5,
    clima_semanal,
    construir_panel,
    mp25_semanal,
)
from sart.dominio.semanas import semana_epidemiologica
from sart.dominio.valores import FuenteEstacion, OrigenMedicion, TipoMedicion

TIPOS_CLIMA = {
    TipoMedicion.TEMPERATURA_MEDIA: "temp",
    TipoMedicion.TEMPERATURA_MINIMA: "temp_min",
    TipoMedicion.HUMEDAD: "humedad",
}


def _hasta(consulta, hasta: date | None):
    if hasta is None:
        return consulta
    anio, semana = semana_epidemiologica(hasta)
    return consulta.where(
        (ConsultaSemanal.anio < anio) | ((ConsultaSemanal.anio == anio) & (ConsultaSemanal.semana <= semana))
    )


def leer_conteos_semanales(
    sesion: Session,
    *,
    causas_consulta: Iterable[str],
    causas_virales: Iterable[str],
    hasta: date | None = None,
) -> pd.DataFrame:
    """Una fila por centro y semana con ``y`` (consultas respiratorias), ``viral``, ``y_menores_5`` e
    ``y_65_y_mas``; la suma se hace en la base (unas 36 veces menos filas que leer ``consulta_semanal``)."""
    causas_consulta, causas_virales = list(causas_consulta), list(causas_virales)
    respiratoria = ConsultaSemanal.causa.in_(causas_consulta)

    def suma(condicion):
        return func.sum(case((condicion, ConsultaSemanal.cantidad), else_=0))

    consulta = _hasta(
        select(
            ConsultaSemanal.centro_id.label("estab"),
            ConsultaSemanal.anio,
            ConsultaSemanal.semana,
            suma(respiratoria).label("y"),
            suma(ConsultaSemanal.causa.in_(causas_virales)).label("viral"),
            suma(respiratoria & ConsultaSemanal.grupo_edad.in_(GRUPOS_MENORES_5)).label("y_menores_5"),
            suma(respiratoria & ConsultaSemanal.grupo_edad.in_(GRUPOS_65_Y_MAS)).label("y_65_y_mas"),
            func.count(case((respiratoria, 1))).label("filas_respiratorias"),
        )
        .where(ConsultaSemanal.causa.in_({*causas_consulta, *causas_virales}))
        .group_by(ConsultaSemanal.centro_id, ConsultaSemanal.anio, ConsultaSemanal.semana),
        hasta,
    )
    datos = pd.DataFrame(sesion.execute(consulta).all(), columns=list(consulta.selected_columns.keys()))
    # una semana con solo COVID-19 informado no tiene consultas respiratorias (y queda sin dato, no en 0)
    datos = datos[datos["filas_respiratorias"] > 0].drop(columns="filas_respiratorias")
    columnas = ["y", "viral", "y_menores_5", "y_65_y_mas"]
    return datos.astype({c: float for c in columnas}).reset_index(drop=True)


def leer_centros(sesion: Session) -> pd.DataFrame:
    filas = sesion.execute(
        select(
            CentroSalud.id,
            CentroSalud.nombre,
            CentroSalud.comuna,
            CentroSalud.tipo,
            CentroSalud.latitud,
            CentroSalud.longitud,
            Estacion.nombre,
        ).join(Estacion, CentroSalud.estacion_id == Estacion.id)
    ).all()
    return pd.DataFrame(
        [(i, n, c, t.value, la, lo, e) for i, n, c, t, la, lo, e in filas],
        columns=["estab", "nombre_estab", "comuna", "tipo", "lat", "lon", "estacion"],
    )


def _mediciones(sesion: Session, tipos: Iterable[TipoMedicion], fuente: FuenteEstacion) -> pd.DataFrame:
    filas = sesion.execute(
        select(Estacion.nombre, Medicion.tipo, Medicion.fecha_hora, Medicion.valor)
        .join(Estacion, Medicion.estacion_id == Estacion.id)
        .where(
            Medicion.tipo.in_(list(tipos)),
            Medicion.origen == OrigenMedicion.OBSERVADO,
            Estacion.fuente == fuente,
        )
    ).all()
    return pd.DataFrame(filas, columns=["estacion", "tipo", "fecha_hora", "valor"])


def _fecha_local(momentos: pd.Series, zona_horaria: str) -> pd.Series:
    """Día local de cada medición (en SQLite la fecha vuelve sin zona: se lee como UTC)."""
    utc = pd.to_datetime(momentos, utc=True)
    return utc.dt.tz_convert(zona_horaria).dt.tz_localize(None).dt.normalize()


def leer_mp25_diario(sesion: Session, zona_horaria: str) -> pd.DataFrame:
    """MP2,5 observado de SINCA: estacion, fecha (día local), mp25 (promedio del día)."""
    datos = _mediciones(sesion, [TipoMedicion.MP25], FuenteEstacion.SINCA)
    if datos.empty:
        return pd.DataFrame(columns=["estacion", "fecha", "mp25"])
    datos["fecha"] = _fecha_local(datos["fecha_hora"], zona_horaria)
    return (
        datos.groupby(["estacion", "fecha"], as_index=False)["valor"].mean().rename(columns={"valor": "mp25"})
    )


def leer_clima_diario(sesion: Session, zona_horaria: str) -> pd.DataFrame:
    """Clima observado del punto de Open-Meteo: fecha (día local), temp, temp_min y humedad."""
    datos = _mediciones(sesion, TIPOS_CLIMA, FuenteEstacion.OPEN_METEO)
    if datos.empty:
        return pd.DataFrame(columns=["fecha", *TIPOS_CLIMA.values()])
    datos["fecha"] = _fecha_local(datos["fecha_hora"], zona_horaria)
    datos["variable"] = datos["tipo"].map(lambda t: TIPOS_CLIMA[TipoMedicion(t)])
    ancho = datos.pivot_table(index="fecha", columns="variable", values="valor", aggfunc="mean")
    return ancho.reset_index().rename_axis(columns=None)


def estacion_de_respaldo(sesion: Session) -> str:
    nombre = sesion.scalar(select(Estacion.nombre).where(Estacion.es_respaldo.is_(True)))
    if nombre is None:
        raise ValueError("No hay estación de respaldo en el catálogo (RB-5): primero cargue el catálogo.")
    return nombre


def panel_desde_la_base(
    sesion: Session,
    parametros: dict[str, Any],
    *,
    hasta: date | None = None,
    semanas_a_pronosticar: Iterable[date] = (),
) -> pd.DataFrame:
    """Panel semanal con los datos guardados (RF-2). ``estab`` es el id del centro en la base.

    Con ``hasta`` (la fecha de corte, RB-4) no entran consultas de semanas posteriores; con
    ``semanas_a_pronosticar`` se agregan las filas a pronosticar (ver ``sart.dominio.panel``).
    """
    ingesta, modelo = parametros["ingesta"], parametros["modelo"]
    causas_consulta = ingesta["causas_en_consultas"]
    causas_virales = modelo["causas_senal_viral"]
    conteos = leer_conteos_semanales(
        sesion, causas_consulta=causas_consulta, causas_virales=causas_virales, hasta=hasta
    )
    zona = parametros["zona_horaria"]
    return construir_panel(
        conteos,
        leer_centros(sesion),
        mp25_semanal(
            leer_mp25_diario(sesion, zona), umbral_diario=float(parametros["mp25_niveles"]["normal_hasta"])
        ),
        clima_semanal(leer_clima_diario(sesion, zona)),
        estacion_respaldo=estacion_de_respaldo(sesion),
        anio_inicio=int(modelo["anio_inicio"]),
        anios_excluidos=modelo["anios_excluidos"],
        armonicos=int(modelo["armonicos"]),
        semanas_a_pronosticar=semanas_a_pronosticar,
    )
