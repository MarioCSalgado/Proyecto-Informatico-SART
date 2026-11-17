"""Router de umbrales, parámetros e historial de configuración (RF-9, RB-3, TC-17)."""

from datetime import UTC, datetime
from http import HTTPStatus
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, JsonValue, StringConstraints, field_validator
from sqlalchemy import String, cast, select

from sart.api.dependencias import SesionDB, requiere_rol
from sart.db.modelos import Auditoria, CentroSalud, UmbralCentro, Usuario
from sart.db.supuestos import ajustar_parametro, parametros_vigentes
from sart.db.umbrales import ErrorUmbral, fijar_umbral_manual, umbral_vigente
from sart.dominio.roles import Rol
from sart.dominio.supuestos import ErrorAjuste, valor_en
from sart.dominio.valores import OrigenUmbral

router = APIRouter(prefix="/administracion", tags=["configuración"])

Administrador = Annotated[Usuario, Depends(requiere_rol(Rol.ADMINISTRADOR))]
Numero = Annotated[float, Field(strict=True)]
Motivo = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]


class ReferenciaCentro(BaseModel):
    codigo_deis: int
    nombre: str


class UmbralPublico(BaseModel):
    umbral_atencion: float
    umbral_alerta: float
    origen: OrigenUmbral
    anios_usados: str | None


class UmbralPorCentro(BaseModel):
    centro: ReferenciaCentro
    umbral: UmbralPublico | None


class CambioUmbral(BaseModel):
    umbral_atencion: Numero
    umbral_alerta: Numero
    motivo: Motivo


class CambioParametro(BaseModel):
    valor: Numero
    motivo: Motivo


class ParametroVigente(BaseModel):
    clave: str
    valor: JsonValue


class CambioConfiguracion(BaseModel):
    fecha: datetime
    autor_id: int | None
    autor_rol: str | None
    accion: str
    entidad_id: str | None
    valor_anterior: JsonValue
    valor_nuevo: JsonValue
    motivo: str | None
    centro: ReferenciaCentro | None = None

    @field_validator("fecha")
    @classmethod
    def fecha_en_utc(cls, fecha: datetime) -> datetime:
        # SQLite devuelve sin zona la fecha almacenada en UTC.
        return fecha.astimezone(UTC) if fecha.tzinfo else fecha.replace(tzinfo=UTC)


def _umbral_por_centro(centro: CentroSalud, umbral: UmbralCentro | None) -> UmbralPorCentro:
    return UmbralPorCentro(
        centro=ReferenciaCentro.model_validate(centro, from_attributes=True),
        umbral=UmbralPublico.model_validate(umbral, from_attributes=True) if umbral is not None else None,
    )


@router.get("/umbrales")
def listar_umbrales(sesion: SesionDB, _: Administrador) -> list[UmbralPorCentro]:
    """Incluye todos los centros. Un centro sin configuración vigente devuelve umbral nulo."""
    centros = sesion.scalars(select(CentroSalud).order_by(CentroSalud.nombre, CentroSalud.codigo_deis))
    return [_umbral_por_centro(centro, umbral_vigente(sesion, centro.id)) for centro in centros]


@router.put("/umbrales/{codigo_deis}")
def cambiar_umbral(
    codigo_deis: int, datos: CambioUmbral, sesion: SesionDB, autor: Administrador
) -> UmbralPorCentro:
    """Guarda el umbral manual del centro y registra el cambio en la misma transacción."""
    centro = sesion.scalar(select(CentroSalud).where(CentroSalud.codigo_deis == codigo_deis))
    if centro is None:
        raise HTTPException(HTTPStatus.NOT_FOUND, "No existe un centro con ese código.")
    try:
        umbral = fijar_umbral_manual(
            sesion, centro.id, datos.umbral_atencion, datos.umbral_alerta, autor=autor, motivo=datos.motivo
        )
    except ErrorUmbral as error:
        raise HTTPException(HTTPStatus.UNPROCESSABLE_ENTITY, str(error)) from None
    return _umbral_por_centro(centro, umbral)


@router.get("/parametros")
def listar_parametros(sesion: SesionDB, _: Administrador) -> list[ParametroVigente]:
    """Valores efectivos de las claves autorizadas por el YAML."""
    vigentes = parametros_vigentes(sesion)
    return [
        ParametroVigente(clave=clave, valor=valor_en(vigentes, clave))
        for clave in vigentes["administracion"]["parametros_editables"]
    ]


@router.put("/parametros/{clave}")
def cambiar_parametro(
    clave: str, datos: CambioParametro, sesion: SesionDB, autor: Administrador
) -> ParametroVigente:
    """Guarda y audita el nuevo valor para las corridas siguientes."""
    try:
        ajuste = ajustar_parametro(sesion, clave, datos.valor, autor=autor, motivo=datos.motivo)
    except ErrorAjuste as error:
        raise HTTPException(HTTPStatus.UNPROCESSABLE_ENTITY, str(error)) from None
    return ParametroVigente(clave=ajuste.clave, valor=ajuste.valor)


@router.get("/historial")
def listar_historial(sesion: SesionDB, _: Administrador) -> list[CambioConfiguracion]:
    """Historial de configuración ordenado del más reciente al más antiguo."""
    filas = sesion.execute(
        select(Auditoria, CentroSalud)
        .outerjoin(
            CentroSalud,
            (Auditoria.entidad == "centro_salud") & (Auditoria.entidad_id == cast(CentroSalud.id, String)),
        )
        .where(Auditoria.accion.in_(("cambio_umbral", "recalculo_umbral", "cambio_parametro")))
        .order_by(Auditoria.fecha.desc(), Auditoria.id.desc())
    )
    historial = []
    for registro, centro in filas:
        cambio = CambioConfiguracion.model_validate(registro, from_attributes=True)
        if centro is not None:
            cambio.centro = ReferenciaCentro.model_validate(centro, from_attributes=True)
        historial.append(cambio)
    return historial
