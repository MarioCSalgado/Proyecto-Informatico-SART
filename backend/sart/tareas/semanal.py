"""Corrida semanal de los lunes a las 06:00: pronóstico, nivel y dotación de cada centro (RF-2, RF-3, RF-6).

Pasos (PASOS.md, parte 8):

1. ``marcar_semanas`` (RB-4): la última semana completa es la ``fecha_corte``; se pronostica la siguiente.
2. Panel desde la base y GLM quasi-Poisson reentrenado con las semanas completas (RF-2).
3. Un pronóstico vigente por centro y semana: si se vuelve a correr, el anterior queda ``vigente = false``.
4. Nivel con el umbral vigente y el margen k (RF-3); «atención» y «ALERTA» generan una ``alerta``, salvo
   que el pronóstico esté desactualizado (RF-3 E2). Cada alerta queda en la auditoría (RNF-S-4).
5. Dotación en hora punta con Erlang C (RF-6), guardada con los supuestos usados (pendientes #39).

Todo con los parámetros vigentes (YAML + ajustes del administrador, RNF-M-4) y registrado en ``corrida``
(RNF-M-3). Qué alertas se envían lo decide ``sart.db.alertas.alertas_por_notificar`` (RF-5, #29).
"""

from __future__ import annotations

import math
from collections import Counter
from dataclasses import dataclass, field
from datetime import UTC, date, datetime
from typing import Any

import pandas as pd
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from sart.db.auditoria import registrar_auditoria
from sart.db.modelos import Alerta, CentroSalud, DotacionSugerida, Pronostico, SemanaCarga
from sart.db.supuestos import parametros_vigentes
from sart.db.umbrales import umbral_vigente
from sart.dominio.alerta_demanda import (
    ETIQUETAS_NIVEL,
    clasificar_demanda,
    mensaje_alerta_demanda,
    pronostico_con_margen,
)
from sart.dominio.dotacion import ErrorDotacion, espera_media_min, recomendar_dotacion
from sart.dominio.pronostico_semanal import (
    ESPECIFICACIONES_DISPONIBLES,
    esta_desactualizado,
    pronosticar_semana,
    semana_objetivo,
    version_modelo,
)
from sart.dominio.semanas import inicio_semana, semana_epidemiologica
from sart.dominio.valores import NIVELES_DEMANDA, TipoAlerta
from sart.tareas.corridas import registrar_corrida
from sart.tareas.panel import panel_desde_la_base
from sart.tareas.semanas_y_umbrales import marcar_semanas

TAREA = "pronostico_semanal"


class ErrorCorridaSemanal(ValueError):
    """La corrida no se puede hacer. El mensaje se puede mostrar."""


@dataclass
class ResumenSemanal:
    fecha_corte: date
    objetivo: date
    anio: int
    semana: int
    desactualizado: bool
    pronosticos: int = 0
    alertas: int = 0
    por_nivel: Counter = field(default_factory=Counter)
    sin_historia: list[str] = field(default_factory=list)  # RF-2 E1
    sin_datos_recientes: list[str] = field(default_factory=list)
    sin_umbral: list[str] = field(default_factory=list)  # RF-3 E1
    sin_dotacion: dict[str, str] = field(default_factory=dict)  # centro → motivo

    def texto(self) -> str:
        anio_corte, semana_corte = semana_epidemiologica(self.fecha_corte)
        niveles = ", ".join(
            f"{self.por_nivel[n]} {ETIQUETAS_NIVEL[n]}" for n in ("alerta", "atencion", "normal")
        )
        lineas = [
            f"Pronóstico de la SE {self.semana} de {self.anio} (fecha de corte: SE {semana_corte} de "
            f"{anio_corte}): {self.pronosticos} centros ({niveles}); {self.alertas} alertas emitidas."
        ]
        if self.desactualizado:
            lineas.append(
                "Pronóstico desactualizado: la semana pronosticada no es la semana en curso (falta la última "
                "semana completa del DEIS). No se emitieron alertas nuevas (RF-3 E2)."
            )
        if self.sin_historia:
            lineas.append(
                f"Sin historia suficiente, no se pronostican (RF-2 E1): {', '.join(self.sin_historia)}."
            )
        if self.sin_datos_recientes:
            lineas.append(f"Sin datos de la semana anterior: {', '.join(self.sin_datos_recientes)}.")
        if self.sin_umbral:
            lineas.append(
                f"Sin umbral vigente, no se clasifican (RF-3 E1; ejecute recalcular-umbrales): "
                f"{', '.join(self.sin_umbral)}."
            )
        for centro, motivo in self.sin_dotacion.items():
            lineas.append(f"Sin dotación sugerida para {centro}: {motivo}")
        return "\n".join(lineas)


def _semanas_incompletas(sesion: Session) -> set[date]:
    return {
        inicio_semana(s.anio, s.semana)
        for s in sesion.scalars(select(SemanaCarga).where(SemanaCarga.completa.is_(False)))
    }


def _dotacion(valor: float, centro: CentroSalud, supuestos: dict[str, Any]) -> DotacionSugerida:
    """RF-6 con los supuestos vigentes; se guardan junto al resultado (paso 3 y E1)."""
    resultado = recomendar_dotacion(valor, centro.tipo, supuestos)
    minutos = float(supuestos["minutos_por_atencion"])
    con_uno_menos = (
        espera_media_min(resultado.profesionales - 1, resultado.llegadas_por_hora, minutos)
        if resultado.profesionales > 1
        else math.inf
    )
    return DotacionSugerida(
        profesionales=resultado.profesionales,
        llegadas_hora_punta=resultado.llegadas_por_hora,
        espera_media_min=resultado.espera_media_min,
        espera_con_uno_menos_min=None if math.isinf(con_uno_menos) else con_uno_menos,
        supuestos={**resultado.supuestos, "supuestos_validados": bool(supuestos["supuestos_validados"])},
    )


def _resumen_dotacion(d: DotacionSugerida | None) -> dict[str, Any] | None:
    if d is None:
        return None
    return {
        "profesionales": d.profesionales,
        "llegadas_hora_punta": round(d.llegadas_hora_punta, 2),
        "espera_media_min": round(d.espera_media_min, 1),
        "supuestos": d.supuestos,
    }


def _hoy(parametros: dict[str, Any]) -> date:
    return pd.Timestamp.now(tz=parametros["zona_horaria"]).date()


def correr_semanal(
    sesion: Session, *, fecha: date | None = None, parametros: dict[str, Any] | None = None
) -> ResumenSemanal:
    """Hace la corrida semanal y la registra en ``corrida``. ``fecha`` es el día de la corrida (por defecto,
    hoy en ``zona_horaria``); solo cambia si el pronóstico está desactualizado (RF-3 E2)."""
    with registrar_corrida(sesion, TAREA) as corrida:
        resumen = _correr(sesion, fecha, parametros)
        corrida.filas = resumen.pronosticos
        corrida.mensaje = resumen.texto()
    return resumen


def _correr(sesion: Session, fecha: date | None, parametros: dict[str, Any] | None) -> ResumenSemanal:
    parametros = parametros or parametros_vigentes(sesion)
    modelo = parametros["modelo"]
    if modelo["especificacion"] not in ESPECIFICACIONES_DISPONIBLES:
        raise ErrorCorridaSemanal(
            f"La corrida semanal solo está disponible con modelo.especificacion: solo_rezagos (está "
            f"«{modelo['especificacion']}»): con_pronostico necesita el MP2,5 pronosticado (RF-2 E2)."
        )
    fecha = fecha or _hoy(parametros)
    fecha_corte = marcar_semanas(sesion, parametros)
    if fecha_corte is None:
        raise ErrorCorridaSemanal("No hay semanas completas (RB-4): primero cargue las consultas del DEIS.")
    objetivo = semana_objetivo(fecha_corte)
    anio, semana = semana_epidemiologica(objetivo)
    resumen = ResumenSemanal(
        fecha_corte=fecha_corte,
        objetivo=objetivo,
        anio=anio,
        semana=semana,
        desactualizado=esta_desactualizado(objetivo, fecha),
    )

    panel = panel_desde_la_base(sesion, parametros, hasta=fecha_corte, semanas_a_pronosticar=[objetivo])
    nivel_intervalo = float(modelo["nivel_intervalo"])
    resultado = pronosticar_semana(
        panel,
        fecha_corte=fecha_corte,
        objetivo=objetivo,
        semanas_invalidas=_semanas_incompletas(sesion),
        especificacion=modelo["especificacion"],
        armonicos=int(modelo["armonicos"]),
        min_semanas=int(modelo["min_semanas_historia"]),
        nivel_intervalo=nivel_intervalo,
    )
    centros = {c.id: c for c in sesion.scalars(select(CentroSalud))}
    resumen.sin_historia = [centros[i].nombre for i in resultado.sin_historia]
    resumen.sin_datos_recientes = [centros[i].nombre for i in resultado.sin_datos_recientes]

    # RF-2 paso 3 y §5.1: un solo pronóstico vigente por centro y semana
    sesion.execute(
        update(Pronostico)
        .where(Pronostico.anio == anio, Pronostico.semana == semana, Pronostico.vigente.is_(True))
        .values(vigente=False)
    )
    k = float(parametros["regla_alerta"]["k_margen"])
    version = version_modelo(modelo["especificacion"], str(modelo["version"]))
    emision = datetime.now(UTC)

    for estimado in resultado.pronosticos:
        centro = centros[estimado.estab]
        pronostico = Pronostico(
            centro_id=centro.id,
            anio=anio,
            semana=semana,
            valor=estimado.valor,
            limite_inferior=estimado.limite_inferior,
            limite_superior=estimado.limite_superior,
            version_modelo=version,
            fecha_corte=fecha_corte,
            vigente=True,
        )
        umbral = umbral_vigente(sesion, centro.id)
        if umbral is None:
            resumen.sin_umbral.append(centro.nombre)
        else:
            pronostico.nivel = clasificar_demanda(
                estimado.valor,
                estimado.limite_superior,
                umbral_atencion=umbral.umbral_atencion,
                umbral_alerta=umbral.umbral_alerta,
                k=k,
                nivel_intervalo=nivel_intervalo,
            )
            pronostico.umbral_id = umbral.id
            pronostico.k_margen = k
            pronostico.valor_con_margen = pronostico_con_margen(
                estimado.valor, estimado.limite_superior, k=k, nivel_intervalo=nivel_intervalo
            )
            resumen.por_nivel[pronostico.nivel] += 1
        try:
            pronostico.dotacion = _dotacion(estimado.valor, centro, parametros["dotacion"])
        except ErrorDotacion as error:
            resumen.sin_dotacion[centro.nombre] = str(error)
        sesion.add(pronostico)
        sesion.flush()
        resumen.pronosticos += 1

        if pronostico.nivel in NIVELES_DEMANDA and not resumen.desactualizado:
            _emitir_alerta(sesion, pronostico, umbral, emision)
            resumen.alertas += 1

    sesion.commit()
    return resumen


def _emitir_alerta(sesion: Session, pronostico: Pronostico, umbral, emision: datetime) -> Alerta:
    alerta = Alerta(
        tipo=TipoAlerta.DEMANDA,
        nivel=pronostico.nivel,
        fecha_emision=emision,
        centro_id=pronostico.centro_id,
        pronostico_id=pronostico.id,
        mensaje=mensaje_alerta_demanda(
            nivel=pronostico.nivel,
            anio=pronostico.anio,
            semana=pronostico.semana,
            pronostico=pronostico.valor,
            limite_inferior=pronostico.limite_inferior,
            limite_superior=pronostico.limite_superior,
            umbral_atencion=umbral.umbral_atencion,
            umbral_alerta=umbral.umbral_alerta,
            k=pronostico.k_margen,
            valor_con_margen=pronostico.valor_con_margen,
        ),
    )
    sesion.add(alerta)
    sesion.flush()
    registrar_auditoria(
        sesion,
        autor=None,
        accion="emision_alerta",
        entidad="alerta",
        entidad_id=alerta.id,
        nuevo={
            "tipo": "demanda",
            "centro_id": pronostico.centro_id,
            "anio": pronostico.anio,
            "semana": pronostico.semana,
            "nivel": pronostico.nivel,
            "pronostico": round(pronostico.valor, 1),
            "intervalo_90": [round(pronostico.limite_inferior, 1), round(pronostico.limite_superior, 1)],
            "umbral_atencion": umbral.umbral_atencion,
            "umbral_alerta": umbral.umbral_alerta,
            "k_margen": pronostico.k_margen,
            "valor_con_margen": round(pronostico.valor_con_margen, 1),
            "dotacion": _resumen_dotacion(pronostico.dotacion),
            "version_modelo": pronostico.version_modelo,
        },
        motivo="RF-3: corrida semanal",
    )
    return alerta
