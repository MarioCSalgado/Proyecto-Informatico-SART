"""API de historial de alertas de demanda (RF-10, TC-19)."""

from datetime import UTC, date, datetime
from http import HTTPStatus
from typing import Annotated, Literal

from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel, Field

from sart.api.centros import CentroPublico, DotacionPublica
from sart.api.dependencias import SesionDB, UsuarioActual
from sart.db.alertas import historial_de_alertas
from sart.db.estado_centros import centros_visibles
from sart.dominio.roles import Rol
from sart.dominio.semanas import inicio_semana, semana_epidemiologica
from sart.parametros import cargar_parametros

router = APIRouter(prefix="/alertas", tags=["alertas"])

NivelDemandaEmitido = Literal["atencion", "alerta"]


class PronosticoHistorico(BaseModel):
    anio: int
    semana: int
    inicio_semana: date
    fecha_corte: date
    valor: float
    limite_inferior: float
    limite_superior: float
    vigente: bool
    umbral_alerta: float | None
    k_margen: float | None
    valor_con_margen: float | None


class ObservacionHistorica(BaseModel):
    consultas: int | None = Field(
        description="Total respiratorio observado. Nulo si falta una observación válida."
    )
    semana_alta: bool | None = Field(
        description="Si el total superó el umbral de alerta original. Nulo si no se pudo evaluar."
    )


class AlertaHistorica(BaseModel):
    id: int
    centro: CentroPublico
    fecha_emision: datetime
    nivel: NivelDemandaEmitido
    pronostico: PronosticoHistorico
    dotacion: DotacionPublica | None
    observacion: ObservacionHistorica


@router.get("/historial", response_model=list[AlertaHistorica])
def historial(
    usuario: UsuarioActual,
    sesion: SesionDB,
    codigo_deis: int | None = None,
    desde: Annotated[
        date | None, Query(description="Fecha de la primera semana objetivo (inclusive).")
    ] = None,
    hasta: Annotated[
        date | None, Query(description="Fecha de la última semana objetivo (inclusive).")
    ] = None,
    nivel: NivelDemandaEmitido | None = None,
) -> list[dict]:
    """Lista alertas emitidas. Las fechas se interpretan en el calendario epidemiológico del MINSAL."""
    if desde is not None and hasta is not None and desde > hasta:
        raise HTTPException(
            HTTPStatus.UNPROCESSABLE_ENTITY, "La fecha desde debe ser anterior o igual a hasta."
        )
    try:
        semana_desde = semana_epidemiologica(desde) if desde is not None else None
        semana_hasta = semana_epidemiologica(hasta) if hasta is not None else None
    except (ValueError, OverflowError):
        raise HTTPException(HTTPStatus.UNPROCESSABLE_ENTITY, "Fecha epidemiológica fuera de rango.") from None

    centros = centros_visibles(sesion, usuario)
    if codigo_deis is not None:
        centros = [centro for centro in centros if centro.codigo_deis == codigo_deis]
        if not centros:
            if usuario.rol is Rol.JEFATURA:
                raise HTTPException(status.HTTP_403_FORBIDDEN, "Este centro no está asignado a su cuenta.")
            raise HTTPException(status.HTTP_404_NOT_FOUND, "No existe un centro con ese código.")

    filas = historial_de_alertas(
        sesion,
        centros,
        cargar_parametros()["ingesta"]["causas_en_consultas"],
        desde=semana_desde,
        hasta=semana_hasta,
        nivel=nivel,
    )
    salida = []
    for alerta, centro, pronostico, umbral_alerta, consultas in filas:
        dotacion = pronostico.dotacion
        salida.append(
            {
                "id": alerta.id,
                "centro": CentroPublico.model_validate(centro, from_attributes=True),
                # SQLite devuelve las fechas sin zona; las emisiones de la corrida se guardan en UTC.
                "fecha_emision": alerta.fecha_emision.astimezone(UTC)
                if alerta.fecha_emision.tzinfo
                else alerta.fecha_emision.replace(tzinfo=UTC),
                "nivel": alerta.nivel,
                "pronostico": {
                    "anio": pronostico.anio,
                    "semana": pronostico.semana,
                    "inicio_semana": inicio_semana(pronostico.anio, pronostico.semana),
                    "fecha_corte": pronostico.fecha_corte,
                    "valor": pronostico.valor,
                    "limite_inferior": pronostico.limite_inferior,
                    "limite_superior": pronostico.limite_superior,
                    "vigente": pronostico.vigente,
                    "umbral_alerta": umbral_alerta,
                    "k_margen": pronostico.k_margen,
                    "valor_con_margen": pronostico.valor_con_margen,
                },
                "dotacion": None
                if dotacion is None
                else {
                    "profesionales": dotacion.profesionales,
                    "llegadas_hora_punta": dotacion.llegadas_hora_punta,
                    "espera_media_min": dotacion.espera_media_min,
                    "espera_con_uno_menos_min": dotacion.espera_con_uno_menos_min,
                    "supuestos": dotacion.supuestos,
                    "por_validar": not dotacion.supuestos.get("supuestos_validados", False),
                },
                "observacion": {
                    "consultas": consultas,
                    "semana_alta": consultas > umbral_alerta
                    if consultas is not None and umbral_alerta is not None
                    else None,
                },
            }
        )
    return salida
