"""Tareas sobre las consultas cargadas: marca de semana incompleta (RB-4, RF-1 paso 4, TC-01) y recálculo
anual de umbrales (RB-3, RF-3 paso 1). Leen los parámetros vigentes: YAML + ajustes del administrador
(opción a, #31).

Las consultas que cuentan son las 6 causas J00–J98 de ``ingesta.causas_en_consultas``; el COVID-19 se guarda
como señal viral pero no suma (RF-1, pendientes #26).
"""

from __future__ import annotations

from collections import defaultdict
from datetime import date
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from sart.db.modelos import ConsultaSemanal, SemanaCarga
from sart.db.supuestos import parametros_vigentes
from sart.db.umbrales import guardar_umbrales_calculados
from sart.dominio.semana_completa import evaluar_semanas, ultima_semana_completa
from sart.dominio.semanas import inicio_semana, semana_epidemiologica
from sart.dominio.umbrales import calcular_umbrales, semanas_de_la_ventana


def totales_semanales(sesion: Session, causas: list[str]) -> dict[int, dict[date, float]]:
    """{centro: {inicio de semana: consultas respiratorias}} a partir de ``consulta_semanal``."""
    filas = sesion.execute(
        select(
            ConsultaSemanal.centro_id,
            ConsultaSemanal.anio,
            ConsultaSemanal.semana,
            func.sum(ConsultaSemanal.cantidad),
        )
        .where(ConsultaSemanal.causa.in_(causas))
        .group_by(ConsultaSemanal.centro_id, ConsultaSemanal.anio, ConsultaSemanal.semana)
    )
    series: dict[int, dict[date, float]] = defaultdict(dict)
    for centro, anio, semana, total in filas:
        series[centro][inicio_semana(anio, semana)] = float(total)
    return dict(series)


def _por_semana(series: dict[int, dict[date, float]]) -> dict[date, dict[int, float]]:
    reportes: dict[date, dict[int, float]] = defaultdict(dict)
    for centro, serie in series.items():
        for semana, total in serie.items():
            reportes[semana][centro] = total
    return dict(reportes)


def marcar_semanas(sesion: Session, parametros: dict[str, Any] | None = None) -> date | None:
    """Evalúa RB-4 y deja la marca en ``semana_carga``. Devuelve la última semana completa."""
    from sart.tareas.carga import _insertar_o_actualizar  # evita la importación circular con carga.py

    parametros = parametros or parametros_vigentes(sesion)
    ingesta = parametros["ingesta"]
    reportes = _por_semana(totales_semanales(sesion, ingesta["causas_en_consultas"]))
    evaluacion = evaluar_semanas(
        reportes,
        cobertura_minima=float(ingesta["cobertura_minima_semana"]),
        semanas_centros_activos=int(ingesta["semanas_centros_activos"]),
        factor_caida_total=float(ingesta["factor_caida_total"]),
        semanas_mediana_previa=int(ingesta["semanas_mediana_previa"]),
    )
    filas = []
    for inicio, completa in evaluacion.items():
        anio, semana = semana_epidemiologica(inicio)
        filas.append(
            {
                "anio": anio,
                "semana": semana,
                "centros_reportados": len(reportes[inicio]),
                "completa": completa,
            }
        )
    _insertar_o_actualizar(
        sesion, SemanaCarga, filas, claves=["anio", "semana"], actualizar=["centros_reportados", "completa"]
    )
    sesion.commit()
    return ultima_semana_completa(evaluacion)


def recalcular_umbrales(
    sesion: Session, *, hasta: date | None = None, parametros: dict[str, Any] | None = None
) -> dict[str, Any]:
    """RB-3: p75 y p90 de las últimas 156 semanas válidas de cada centro hasta ``hasta`` (por defecto, la
    última semana completa). No pisa los umbrales fijados a mano (pendientes #32).

    Primero vuelve a marcar las semanas (RB-4): así una semana a medias nunca entra a un umbral, aunque nadie
    haya marcado antes.
    """
    parametros = parametros or parametros_vigentes(sesion)
    ultima_completa = marcar_semanas(sesion, parametros)
    if hasta is None:
        if ultima_completa is None:
            raise ValueError("No hay semanas completas: primero cargue las consultas.")
        hasta = ultima_completa
    series = totales_semanales(sesion, parametros["ingesta"]["causas_en_consultas"])
    invalidas = {
        inicio_semana(s.anio, s.semana)
        for s in sesion.scalars(select(SemanaCarga).where(SemanaCarga.completa.is_(False)))
    }

    umbrales = calcular_umbrales(
        series,
        hasta=hasta,
        semanas=semanas_de_la_ventana(parametros["umbrales"]["anios_umbral"]),
        anios_excluidos=parametros["modelo"]["anios_excluidos"],
        cuantil_atencion=float(parametros["umbrales"]["cuantil_atencion"]),
        cuantil_alerta=float(parametros["umbrales"]["cuantil_alerta"]),
        minimo_semanas=int(parametros["modelo"]["min_semanas_historia"]),
        semanas_invalidas=invalidas,
    )
    descripcion = next(iter(umbrales.values())).descripcion if umbrales else ""
    resumen = guardar_umbrales_calculados(
        sesion, {c: (u.atencion, u.alerta) for c, u in umbrales.items()}, anios_usados=descripcion
    )
    return {**resumen, "sin_historia": len(series) - len(umbrales), "hasta": hasta}
