"""Estado de los centros que ve cada usuario (RF-7): nivel, pronóstico con su intervalo, umbrales usados,
dotación guardada, MP2,5 de la zona e historia observada. Solo cifras agregadas (RNF-S-5).

Qué centros ve cada rol (RNF-S-2): la jefatura, solo los asignados; el subdirector y el administrador, todos.
Los umbrales que se muestran son los que se usaron al clasificar, no los vigentes (pendientes #39).
"""

from __future__ import annotations

from collections import defaultdict
from datetime import UTC, date, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from sart.db.modelos import (
    CentroSalud,
    ConsultaSemanal,
    Estacion,
    Medicion,
    Pronostico,
    SemanaCarga,
    UmbralCentro,
    Usuario,
)
from sart.dominio.alerta_demanda import ORDEN_NIVELES
from sart.dominio.estado_centro import MedicionDiaria, datos_antiguos, elegir_mp25, nivel_observado
from sart.dominio.mp25 import clasificar_mp25
from sart.dominio.pronostico_semanal import esta_desactualizado
from sart.dominio.roles import Rol
from sart.dominio.semanas import inicio_semana, semana_epidemiologica
from sart.dominio.valores import OrigenMedicion, TipoMedicion


def centros_visibles(sesion: Session, usuario: Usuario) -> list[CentroSalud]:
    if usuario.rol is Rol.JEFATURA:
        return sorted(usuario.centros, key=lambda c: c.nombre)
    return list(sesion.scalars(select(CentroSalud).order_by(CentroSalud.nombre)))


def _pronosticos_vigentes(sesion: Session, ids: list[int]) -> dict[int, Pronostico]:
    """El pronóstico vigente más reciente de cada centro."""
    salida: dict[int, Pronostico] = {}
    for p in sesion.scalars(
        select(Pronostico).where(Pronostico.vigente.is_(True), Pronostico.centro_id.in_(ids))
    ):
        actual = salida.get(p.centro_id)
        if actual is None or (p.anio, p.semana) > (actual.anio, actual.semana):
            salida[p.centro_id] = p
    return salida


def _ultima_semana_completa(sesion: Session) -> date | None:
    ultima = sesion.execute(
        select(SemanaCarga.anio, SemanaCarga.semana)
        .where(SemanaCarga.completa.is_(True))
        .order_by(SemanaCarga.anio.desc(), SemanaCarga.semana.desc())
        .limit(1)
    ).first()
    return inicio_semana(*ultima) if ultima else None


def _consultas_por_semana(
    sesion: Session, ids: list[int], causas: list[str], desde: date, hasta: date
) -> dict[int, dict[date, float]]:
    anio_desde, _ = semana_epidemiologica(desde)
    filas = sesion.execute(
        select(
            ConsultaSemanal.centro_id,
            ConsultaSemanal.anio,
            ConsultaSemanal.semana,
            func.sum(ConsultaSemanal.cantidad),
        )
        .where(
            ConsultaSemanal.centro_id.in_(ids),
            ConsultaSemanal.causa.in_(causas),
            ConsultaSemanal.anio >= anio_desde,
        )
        .group_by(ConsultaSemanal.centro_id, ConsultaSemanal.anio, ConsultaSemanal.semana)
    )
    salida: dict[int, dict[date, float]] = defaultdict(dict)
    for centro, anio, semana, total in filas:
        inicio = inicio_semana(anio, semana)
        if desde <= inicio <= hasta:
            salida[centro][inicio] = float(total)
    return salida


def _ultimas_mediciones(sesion: Session, estacion_ids: set[int], zona: ZoneInfo) -> dict[int, MedicionDiaria]:
    """Última medición diaria observada de MP2,5 de cada estación."""
    ultimas = (
        select(Medicion.estacion_id, func.max(Medicion.fecha_hora).label("fecha_hora"))
        .where(
            Medicion.estacion_id.in_(estacion_ids),
            Medicion.tipo == TipoMedicion.MP25,
            Medicion.origen == OrigenMedicion.OBSERVADO,
        )
        .group_by(Medicion.estacion_id)
        .subquery()
    )
    filas = sesion.execute(
        select(Medicion.estacion_id, Estacion.nombre, Medicion.fecha_hora, Medicion.valor)
        .join(
            ultimas,
            (Medicion.estacion_id == ultimas.c.estacion_id) & (Medicion.fecha_hora == ultimas.c.fecha_hora),
        )
        .join(Estacion, Estacion.id == Medicion.estacion_id)
        .where(Medicion.tipo == TipoMedicion.MP25, Medicion.origen == OrigenMedicion.OBSERVADO)
    )
    salida = {}
    for estacion_id, nombre, momento, valor in filas:
        if momento.tzinfo is None:  # SQLite devuelve la fecha sin zona: se guardó en UTC
            momento = momento.replace(tzinfo=UTC)
        salida[estacion_id] = MedicionDiaria(nombre, momento.astimezone(zona).date(), float(valor))
    return salida


def _orden(estado: dict[str, Any]) -> tuple:
    """Alerta → atención → normal → sin nivel; dentro de cada nivel, el mayor pronóstico primero."""
    p = estado["pronostico"]
    if p is None:
        return (len(ORDEN_NIVELES) + 1, 0.0, estado["centro"]["nombre"])
    nivel = -ORDEN_NIVELES[p["nivel"]] if p["nivel"] else 1
    return (nivel, -p["valor"], estado["centro"]["nombre"])


def estado_de_centros(
    sesion: Session, centros: list[CentroSalud], *, hoy: date, parametros: dict[str, Any]
) -> list[dict[str, Any]]:
    """Una entrada por centro, en el orden de la vista de red (RF-7 paso 2)."""
    if not centros:
        return []
    ids = [c.id for c in centros]
    consulta = parametros["consulta"]
    n_semanas = int(consulta["semanas_historial"])
    zona = ZoneInfo(parametros["zona_horaria"])

    pronosticos = _pronosticos_vigentes(sesion, ids)
    corte_general = _ultima_semana_completa(sesion)
    cortes = [p.fecha_corte for p in pronosticos.values()] + ([corte_general] if corte_general else [])
    historia: dict[int, dict[date, float]] = {}
    if cortes:
        hasta = max(cortes)
        historia = _consultas_por_semana(
            sesion,
            ids,
            parametros["ingesta"]["causas_en_consultas"],
            hasta - timedelta(weeks=n_semanas + 52),
            hasta,  # holgura: cada centro corta en su fecha
        )

    ids_estaciones_asignadas = {centro.estacion_id for centro in centros}
    estaciones_asignadas = dict(
        sesion.execute(
            select(Estacion.id, Estacion.nombre).where(Estacion.id.in_(ids_estaciones_asignadas))
        ).all()
    )
    respaldo = sesion.scalar(select(Estacion).where(Estacion.es_respaldo.is_(True)))
    estaciones = {c.estacion_id for c in centros} | ({respaldo.id} if respaldo else set())
    mediciones = _ultimas_mediciones(sesion, estaciones, zona)

    salida = []
    for centro in centros:
        p = pronosticos.get(centro.id)
        umbral = sesion.get(UmbralCentro, p.umbral_id) if p and p.umbral_id else None
        if p is None:
            umbral = sesion.scalar(
                select(UmbralCentro).where(
                    UmbralCentro.centro_id == centro.id, UmbralCentro.vigente.is_(True)
                )
            )
        corte = p.fecha_corte if p else corte_general

        semanas = []
        if corte is not None:
            serie = historia.get(centro.id, {})
            for i in range(n_semanas - 1, -1, -1):
                inicio = corte - timedelta(weeks=i)
                if inicio in serie:
                    anio, numero = semana_epidemiologica(inicio)
                    semanas.append(
                        {
                            "anio": anio,
                            "semana": numero,
                            "inicio": inicio,
                            "consultas": serie[inicio],
                            "nivel_observado": nivel_observado(
                                serie[inicio],
                                umbral_atencion=umbral.umbral_atencion if umbral else None,
                                umbral_alerta=umbral.umbral_alerta if umbral else None,
                            ),
                        }
                    )

        mp = elegir_mp25(
            mediciones.get(centro.estacion_id),
            mediciones.get(respaldo.id) if respaldo else None,
            hoy,
            asignada_es_respaldo=respaldo is not None and centro.estacion_id == respaldo.id,
        )
        nivel_mp = clasificar_mp25(mp.medicion.valor, parametros["mp25_niveles"]) if mp.medicion else None

        salida.append(
            {
                "centro": {
                    "codigo_deis": centro.codigo_deis,
                    "nombre": centro.nombre,
                    "tipo": centro.tipo.value,
                    "comuna": centro.comuna,
                    "latitud": centro.latitud,
                    "longitud": centro.longitud,
                    "estacion_asignada": estaciones_asignadas[centro.estacion_id],
                },
                "pronostico": None
                if p is None
                else {
                    "anio": p.anio,
                    "semana": p.semana,
                    "inicio_semana": inicio_semana(p.anio, p.semana),
                    "fecha_corte": p.fecha_corte,
                    "valor": p.valor,
                    "limite_inferior": p.limite_inferior,
                    "limite_superior": p.limite_superior,
                    "nivel": p.nivel,
                    "valor_con_margen": p.valor_con_margen,
                    "k_margen": p.k_margen,
                    "version_modelo": p.version_modelo,
                    "desactualizado": esta_desactualizado(inicio_semana(p.anio, p.semana), hoy),
                    "datos_antiguos": datos_antiguos(
                        p.fecha_corte, hoy, dias_aviso=int(consulta["aviso_datos_antiguos_dias"])
                    ),
                    "umbrales": None
                    if umbral is None
                    else {
                        "atencion": umbral.umbral_atencion,
                        "alerta": umbral.umbral_alerta,
                        "origen": umbral.origen.value,
                    },
                },
                "dotacion": None
                if p is None or p.dotacion is None
                else {
                    "profesionales": p.dotacion.profesionales,
                    "llegadas_hora_punta": p.dotacion.llegadas_hora_punta,
                    "espera_media_min": p.dotacion.espera_media_min,
                    "espera_con_uno_menos_min": p.dotacion.espera_con_uno_menos_min,
                    "supuestos": p.dotacion.supuestos,
                    "por_validar": not p.dotacion.supuestos.get("supuestos_validados", False),
                },
                "mp25": {
                    "estado": mp.estado,
                    "estacion": mp.medicion.estacion if mp.medicion else None,
                    "de_respaldo": mp.de_respaldo,
                    "fecha": mp.medicion.fecha if mp.medicion else None,
                    "valor": mp.medicion.valor if mp.medicion else None,
                    "nivel": None
                    if nivel_mp is None
                    else {"clave": nivel_mp.clave, "nombre": nivel_mp.nombre},
                },
                "ultimas_semanas": semanas,
            }
        )
    return sorted(salida, key=_orden)
