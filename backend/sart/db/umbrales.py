"""Umbrales de atención y alerta por centro (RB-3, RF-3, RF-9), con historia y auditoría (RNF-S-4).

El cálculo de los percentiles (RB-3) es de la parte 5; aquí solo se guardan. Un umbral fijado a mano por el
administrador se respeta en los recálculos hasta que él mismo lo cambie (pendientes #21).
"""

from __future__ import annotations

import math

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from sart.db.auditoria import registrar_auditoria
from sart.db.modelos import CentroSalud, UmbralCentro, Usuario
from sart.dominio.valores import OrigenUmbral


class ErrorUmbral(ValueError):
    """El umbral no se puede guardar. El mensaje se puede mostrar al administrador."""


def umbral_vigente(sesion: Session, centro_id: int) -> UmbralCentro | None:
    return sesion.scalar(
        select(UmbralCentro).where(UmbralCentro.centro_id == centro_id, UmbralCentro.vigente.is_(True))
    )


def _bloquear_centro(sesion: Session, centro_id: int) -> None:
    # La fila del centro existe aun si todavía no hay un umbral vigente que bloquear.
    centro = sesion.scalar(
        select(CentroSalud.id).where(CentroSalud.id == centro_id).with_for_update(key_share=True)
    )
    if centro is None:
        raise ErrorUmbral("No existe el centro que se quiere configurar.")


def _resumen(umbral: UmbralCentro | None) -> dict | None:
    if umbral is None:
        return None
    return {
        "umbral_atencion": umbral.umbral_atencion,
        "umbral_alerta": umbral.umbral_alerta,
        "origen": umbral.origen.value,
    }


def _retirar_vigente(sesion: Session, centro_id: int) -> None:
    sesion.execute(
        update(UmbralCentro)
        .where(UmbralCentro.centro_id == centro_id, UmbralCentro.vigente.is_(True))
        .values(vigente=False)
    )


def guardar_umbrales_calculados(
    sesion: Session, umbrales: dict[int, tuple[float, float]], *, anios_usados: str
) -> dict[str, int]:
    """Guarda los umbrales calculados por RB-3 ({centro_id: (atención, alerta)}). No pisa los manuales."""
    resumen = {"guardados": 0, "manuales_respetados": 0}
    # Adquirir los bloqueos en el mismo orden si coinciden dos recálculos.
    for centro_id, (atencion, alerta) in sorted(umbrales.items()):
        _bloquear_centro(sesion, centro_id)
        anterior = umbral_vigente(sesion, centro_id)
        if anterior is not None and anterior.origen is OrigenUmbral.MANUAL:
            resumen["manuales_respetados"] += 1
            continue
        _retirar_vigente(sesion, centro_id)
        nuevo = UmbralCentro(
            centro_id=centro_id,
            umbral_atencion=atencion,
            umbral_alerta=alerta,
            origen=OrigenUmbral.CALCULADO,
            anios_usados=anios_usados,
        )
        sesion.add(nuevo)
        registrar_auditoria(
            sesion,
            autor=None,
            accion="recalculo_umbral",
            entidad="centro_salud",
            entidad_id=centro_id,
            anterior=_resumen(anterior),
            nuevo=_resumen(nuevo),
            motivo=f"RB-3 con {anios_usados}",
        )
        resumen["guardados"] += 1
    sesion.commit()
    return resumen


def fijar_umbral_manual(
    sesion: Session, centro_id: int, atencion: float, alerta: float, *, autor: Usuario, motivo: str
) -> UmbralCentro:
    """RF-9: el administrador corrige los umbrales de un centro. Queda auditado (RNF-S-4)."""
    motivo = (motivo or "").strip()
    if not motivo:
        raise ErrorUmbral("El motivo del cambio es obligatorio.")
    if not math.isfinite(atencion) or not math.isfinite(alerta):
        raise ErrorUmbral("Los umbrales deben ser números finitos.")
    if atencion < 0 or alerta < 0:
        raise ErrorUmbral("Un umbral no puede ser negativo.")
    if atencion > alerta:
        raise ErrorUmbral("El umbral de atención debe ser menor o igual que el de alerta.")

    _bloquear_centro(sesion, centro_id)
    resumen_anterior = _resumen(umbral_vigente(sesion, centro_id))
    _retirar_vigente(sesion, centro_id)
    nuevo = UmbralCentro(
        centro_id=centro_id,
        umbral_atencion=atencion,
        umbral_alerta=alerta,
        origen=OrigenUmbral.MANUAL,
        motivo=motivo,
        autor_id=autor.id,
    )
    sesion.add(nuevo)
    registrar_auditoria(
        sesion,
        autor=autor,
        accion="cambio_umbral",
        entidad="centro_salud",
        entidad_id=centro_id,
        anterior=resumen_anterior,
        nuevo=_resumen(nuevo),
        motivo=motivo,
    )
    sesion.commit()
    return nuevo
