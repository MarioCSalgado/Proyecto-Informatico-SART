"""Estado de los centros (RF-7, TC-09). Primer endpoint de lectura: sirve de ejemplo para los demás.

- ``GET /centros/estado``: los centros que el usuario puede ver, ordenados Alerta → Atención → Normal y,
  dentro de cada nivel, por pronóstico (RF-7 paso 2).
- ``GET /centros/{codigo_deis}/estado``: el detalle de uno (RF-7 paso 3).

Acceso (RNF-S-2): cualquier sesión; la jefatura solo ve sus centros asignados. Si pide un centro ajeno (o uno
que no existe, para no revelar cuáles existen) recibe 403 y el intento queda en la auditoría (RF-7 E2,
RNF-S-4). La lógica vive en ``sart.db.estado_centros`` y ``sart.dominio.estado_centro``; aquí solo el acceso
y el formato. Sin datos de pacientes ni de cuentas en la respuesta (RNF-S-5).
"""

from __future__ import annotations

from datetime import date
from typing import Annotated, Any, Literal

import pandas as pd
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select

from sart.api.dependencias import SesionDB, UsuarioActual
from sart.db.auditoria import registrar_auditoria
from sart.db.estado_centros import centros_visibles, estado_de_centros
from sart.db.modelos import CentroSalud
from sart.db.supuestos import parametros_vigentes
from sart.dominio.roles import Rol
from sart.parametros import cargar_parametros

router = APIRouter(prefix="/centros", tags=["centros"])

Nivel = Literal["normal", "atencion", "alerta"]


class CentroPublico(BaseModel):
    codigo_deis: int
    nombre: str
    tipo: str
    comuna: str
    latitud: float | None
    longitud: float | None
    estacion_asignada: str


class UmbralesUsados(BaseModel):
    atencion: float
    alerta: float
    origen: str  # calculado (RB-3) o manual (RF-9)


class PronosticoPublico(BaseModel):
    anio: int
    semana: int
    inicio_semana: date
    fecha_corte: date
    valor: float
    limite_inferior: float
    limite_superior: float
    nivel: Nivel | None  # None: el centro no tenía umbral al correr (RF-3 E1)
    valor_con_margen: float | None
    k_margen: float | None
    version_modelo: str
    desactualizado: bool  # RF-3 E2: la semana pronosticada no es la semana en curso
    datos_antiguos: bool  # RF-7 E1
    umbrales: UmbralesUsados | None


class DotacionPublica(BaseModel):
    profesionales: int
    llegadas_hora_punta: float
    espera_media_min: float
    espera_con_uno_menos_min: float | None
    supuestos: dict[str, Any]
    por_validar: bool  # RF-6 E1


class NivelMp25Breve(BaseModel):
    clave: str
    nombre: str


class Mp25Zona(BaseModel):
    estado: Literal["ok", "datos_insuficientes"]  # RB-5, RF-7 E3
    estacion: str | None
    de_respaldo: bool
    fecha: date | None  # día de la medición (si hay datos insuficientes, la última válida)
    valor: float | None  # promedio de 24 h, µg/m³
    nivel: NivelMp25Breve | None


class SemanaObservada(BaseModel):
    anio: int
    semana: int
    inicio: date
    consultas: float
    nivel_observado: Nivel | None


class EstadoCentro(BaseModel):
    centro: CentroPublico
    pronostico: PronosticoPublico | None
    dotacion: DotacionPublica | None
    mp25: Mp25Zona
    ultimas_semanas: list[SemanaObservada]


def fecha_de_hoy() -> date:
    """Hoy en la zona horaria de SART. Es una dependencia para que las pruebas fijen el día."""
    return pd.Timestamp.now(tz=cargar_parametros()["zona_horaria"]).date()


Hoy = Annotated[date, Depends(fecha_de_hoy)]


@router.get("/estado", response_model=list[EstadoCentro])
def estado_centros(usuario: UsuarioActual, sesion: SesionDB, hoy: Hoy) -> list[dict[str, Any]]:
    centros = centros_visibles(sesion, usuario)
    return estado_de_centros(sesion, centros, hoy=hoy, parametros=parametros_vigentes(sesion))


@router.get("/{codigo_deis}/estado", response_model=EstadoCentro)
def estado_centro(codigo_deis: int, usuario: UsuarioActual, sesion: SesionDB, hoy: Hoy) -> dict[str, Any]:
    if usuario.rol is Rol.JEFATURA:
        centro = next((c for c in usuario.centros if c.codigo_deis == codigo_deis), None)
        if centro is None:  # RF-7 E2: acceso negado y registrado
            registrar_auditoria(
                sesion,
                autor=usuario,
                accion="acceso_denegado",
                entidad="centro_salud",
                entidad_id=codigo_deis,
                motivo="RF-7 E2: centro no asignado",
            )
            sesion.commit()
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Este centro no está asignado a su cuenta.")
    else:
        centro = sesion.scalar(select(CentroSalud).where(CentroSalud.codigo_deis == codigo_deis))
        if centro is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "No existe un centro con ese código.")
    [estado] = estado_de_centros(sesion, [centro], hoy=hoy, parametros=parametros_vigentes(sesion))
    return estado
