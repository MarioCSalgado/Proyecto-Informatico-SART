"""Exportación CSV (RF-11, TC-15).

- ``GET /exportar/centros.csv``: los centros que el usuario puede ver, con los mismos datos de
  ``GET /centros/estado`` (RF-7). ``?codigo_deis=`` limita a un centro (botón «Descargar CSV» de Mi centro).

Acceso (RNF-S-2): cualquier sesión; la jefatura solo exporta sus centros asignados. Si pide uno ajeno o que no
existe, recibe 403 y queda en la auditoría, como en RF-7 E2. Cada exportación queda en la auditoría (RNF-S-4),
sin nombre ni correo. Sin datos de pacientes (RNF-S-5).
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query, Response, status

from sart.api.centros import Hoy
from sart.api.dependencias import SesionDB, UsuarioActual
from sart.db.auditoria import registrar_auditoria
from sart.db.estado_centros import centros_visibles, estado_de_centros
from sart.db.supuestos import parametros_vigentes
from sart.dominio.exportacion import csv_de_estados
from sart.dominio.roles import Rol

router = APIRouter(prefix="/exportar", tags=["exportación"])


@router.get(
    "/centros.csv",
    response_class=Response,
    responses={200: {"content": {"text/csv": {}}, "description": "CSV UTF-8 (con BOM), separador «;»"}},
)
def exportar_centros(
    usuario: UsuarioActual,
    sesion: SesionDB,
    hoy: Hoy,
    codigo_deis: int | None = Query(default=None, description="solo este centro"),
) -> Response:
    centros = centros_visibles(sesion, usuario)
    if codigo_deis is not None:
        centros = [c for c in centros if c.codigo_deis == codigo_deis]
        if not centros:
            if usuario.rol is Rol.JEFATURA:  # RF-7 E2: acceso negado y registrado
                registrar_auditoria(
                    sesion,
                    autor=usuario,
                    accion="acceso_denegado",
                    entidad="centro_salud",
                    entidad_id=codigo_deis,
                    motivo="RF-11: exportación de un centro no asignado",
                )
                sesion.commit()
                raise HTTPException(status.HTTP_403_FORBIDDEN, "Este centro no está asignado a su cuenta.")
            raise HTTPException(status.HTTP_404_NOT_FOUND, "No existe un centro con ese código.")

    estados = estado_de_centros(sesion, centros, hoy=hoy, parametros=parametros_vigentes(sesion))
    registrar_auditoria(
        sesion,
        autor=usuario,
        accion="exportar_csv",
        entidad="centro_salud",
        entidad_id=codigo_deis,
        nuevo={"centros": len(estados)},
    )
    sesion.commit()
    nombre = f"sart_centro_{codigo_deis}_{hoy.isoformat()}.csv" if codigo_deis else f"sart_centros_{hoy}.csv"
    return Response(
        content=csv_de_estados(estados),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{nombre}"'},
    )
