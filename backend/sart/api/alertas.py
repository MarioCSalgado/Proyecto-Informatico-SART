"""API de historial de alertas de demanda (RF-10, TC-19)."""

from datetime import UTC, date, datetime
from http import HTTPStatus
from typing import Annotated, Literal

from fastapi import APIRouter, HTTPException, Query, Response, status
from pydantic import BaseModel, Field
from sqlalchemy import select

from sart.api.centros import CentroPublico, DotacionPublica
from sart.api.dependencias import SesionDB, UsuarioActual
from sart.db.alertas import acuses_propios, historial_de_alertas, resumen_notificaciones
from sart.db.auditoria import registrar_auditoria
from sart.db.estado_centros import centros_visibles
from sart.db.modelos import Estacion
from sart.dominio.alerta_demanda import NIVEL_QUE_NOTIFICA
from sart.dominio.roles import Rol
from sart.dominio.semanas import inicio_semana, semana_epidemiologica
from sart.dominio.valores import EstadoNotificacion
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


class AcusePropio(BaseModel):
    tipo: Literal["propia"] = "propia"
    estado: EstadoNotificacion | None
    fecha_confirmacion: datetime | None


class ConteoNotificacion(BaseModel):
    estado: EstadoNotificacion
    total: int


class ResumenNotificaciones(BaseModel):
    tipo: Literal["resumen"] = "resumen"
    estados: list[ConteoNotificacion]


class SinCorreoPrevisto(BaseModel):
    tipo: Literal["no_aplica"] = "no_aplica"


NotificacionesHistoricas = Annotated[
    AcusePropio | ResumenNotificaciones | SinCorreoPrevisto, Field(discriminator="tipo")
]


class AlertaHistorica(BaseModel):
    id: int
    centro: CentroPublico
    fecha_emision: datetime
    nivel: NivelDemandaEmitido
    pronostico: PronosticoHistorico
    dotacion: DotacionPublica | None
    observacion: ObservacionHistorica
    notificaciones: NotificacionesHistoricas


def _en_utc(fecha: datetime) -> datetime:
    # SQLite devuelve las fechas sin zona; las corridas y el acuse las guardan en UTC.
    return fecha.astimezone(UTC) if fecha.tzinfo else fecha.replace(tzinfo=UTC)


@router.get("/historial", response_model=list[AlertaHistorica])
def historial(
    usuario: UsuarioActual,
    sesion: SesionDB,
    respuesta: Response,
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
                codigo_auditado = str(codigo_deis)
                registrar_auditoria(
                    sesion,
                    autor=usuario,
                    accion="acceso_denegado",
                    entidad="centro_salud",
                    # Un filtro arbitrario puede exceder el VARCHAR(60) de auditoria.entidad_id.
                    entidad_id=codigo_auditado if len(codigo_auditado) <= 60 else None,
                    motivo="RF-10: centro no asignado",
                )
                sesion.commit()
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
    respuesta.headers["Cache-Control"] = "no-store"
    notificables = [alerta.id for alerta, *_ in filas if alerta.nivel == NIVEL_QUE_NOTIFICA]
    es_jefatura = usuario.rol is Rol.JEFATURA
    propios = acuses_propios(sesion, notificables, usuario.id) if es_jefatura else {}
    resumen = resumen_notificaciones(sesion, notificables) if not es_jefatura else {}
    ids_estaciones = {centro.estacion_id for _, centro, *_ in filas}
    estaciones = dict(
        sesion.execute(select(Estacion.id, Estacion.nombre).where(Estacion.id.in_(ids_estaciones))).all()
    )
    salida = []
    for alerta, centro, pronostico, umbral_alerta, consultas in filas:
        dotacion = pronostico.dotacion
        notificaciones: NotificacionesHistoricas
        if alerta.nivel != NIVEL_QUE_NOTIFICA:
            notificaciones = SinCorreoPrevisto()
        elif es_jefatura:
            estado, fecha = propios.get(alerta.id, (None, None))
            notificaciones = AcusePropio(estado=estado, fecha_confirmacion=_en_utc(fecha) if fecha else None)
        else:
            conteos = resumen.get(alerta.id, {})
            notificaciones = ResumenNotificaciones(
                estados=[
                    ConteoNotificacion(estado=estado, total=conteos[estado])
                    for estado in EstadoNotificacion
                    if estado in conteos
                ]
            )
        salida.append(
            {
                "id": alerta.id,
                "centro": CentroPublico(
                    codigo_deis=centro.codigo_deis,
                    nombre=centro.nombre,
                    tipo=centro.tipo.value,
                    comuna=centro.comuna,
                    latitud=centro.latitud,
                    longitud=centro.longitud,
                    estacion_asignada=estaciones[centro.estacion_id],  # RF-12 (T10) la agregó a CentroPublico
                ),
                "fecha_emision": _en_utc(alerta.fecha_emision),
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
                "notificaciones": notificaciones,
            }
        )
    return salida
