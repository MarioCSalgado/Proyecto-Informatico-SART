"""GET /referencias: valores fijos que la web necesita para dibujar sus pantallas (RNF-M-4).

La web no escribe en su código los límites de MP2,5 ni la lista de comunas: los pide aquí, y aquí se leen de
``config/parametros.yaml``. Exige sesión (cualquier rol).
"""

from __future__ import annotations

from dataclasses import asdict

from fastapi import APIRouter
from pydantic import BaseModel

from sart.api.dependencias import UsuarioActual
from sart.dominio.mp25 import niveles_mp25
from sart.parametros import cargar_parametros

router = APIRouter(tags=["referencias"])


class NivelMp25Publico(BaseModel):
    clave: str
    nombre: str
    desde: int
    hasta: int | None


class Referencias(BaseModel):
    mp25_niveles: list[NivelMp25Publico]
    comunas: list[str]
    finalidad_version: str  # texto de §5.3 que acepta el funcionario al crear su cuenta (RF-16)
    finalidad_texto: str


@router.get("/referencias", response_model=Referencias)
def referencias(_usuario: UsuarioActual) -> Referencias:
    parametros = cargar_parametros()
    return Referencias(
        mp25_niveles=[NivelMp25Publico(**asdict(n)) for n in niveles_mp25(parametros["mp25_niveles"])],
        comunas=list(parametros["escenario"]["comunas"]),
        finalidad_version=str(parametros["cuentas"]["version_texto_finalidad"]),
        finalidad_texto=str(parametros["cuentas"]["texto_finalidad"]),
    )
