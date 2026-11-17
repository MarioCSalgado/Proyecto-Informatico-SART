"""Exportación CSV del estado de los centros para Excel o Power BI (RF-11, TC-15, RNF-S-5). Lógica pura.

Las filas salen de lo mismo que muestra RF-7 (``estado_de_centros``): las cifras guardadas por la corrida
semanal, sin recalcular (#39). Solo datos agregados por centro y semana: ningún dato de pacientes ni de
cuentas.

Formato pensado para Excel en español de Chile: UTF-8 con BOM (para que abra bien las tildes), separador «;» y
coma decimal. La última columna cita la fuente (datos abiertos del DEIS con licencia CC BY-NC).
"""

from __future__ import annotations

import csv
import io
from collections.abc import Iterable
from typing import Any

FUENTE = "DEIS-MINSAL (datos abiertos, licencia CC BY-NC), SINCA y Open-Meteo; procesado por SART"
ETIQUETA_NIVEL = {"alerta": "ALERTA", "atencion": "atención", "normal": "normal"}

COLUMNAS = [
    "codigo_deis",
    "centro",
    "tipo",
    "comuna",
    "anio",
    "semana_epidemiologica",
    "inicio_semana",
    "pronostico_consultas",
    "limite_inferior_90",
    "limite_superior_90",
    "nivel",
    "umbral_atencion",
    "umbral_alerta",
    "k_margen",
    "pronostico_desactualizado",
    "profesionales_sugeridos",
    "espera_media_min",
    "supuestos_dotacion_por_validar",
    "mp25_ug_m3",
    "mp25_fecha",
    "mp25_nivel",
    "mp25_estacion",
    "mp25_de_respaldo",
    "fuente",
]


def _numero(valor: float | None, decimales: int = 1) -> str:
    return "" if valor is None else f"{valor:.{decimales}f}".replace(".", ",")


def _si_no(valor: bool | None) -> str:
    return "" if valor is None else ("sí" if valor else "no")


def fila_csv(estado: dict[str, Any]) -> list[str]:
    """Una fila por centro a partir de una entrada de ``estado_de_centros``."""
    centro, p, d, mp = estado["centro"], estado["pronostico"], estado["dotacion"], estado["mp25"]
    umbrales = p["umbrales"] if p else None
    return [
        str(centro["codigo_deis"]),
        centro["nombre"],
        centro["tipo"],
        centro["comuna"],
        str(p["anio"]) if p else "",
        str(p["semana"]) if p else "",
        p["inicio_semana"].isoformat() if p else "",
        _numero(p["valor"]) if p else "",
        _numero(p["limite_inferior"]) if p else "",
        _numero(p["limite_superior"]) if p else "",
        ETIQUETA_NIVEL.get(p["nivel"], "") if p and p["nivel"] else "sin nivel",
        _numero(umbrales["atencion"]) if umbrales else "",
        _numero(umbrales["alerta"]) if umbrales else "",
        _numero(p["k_margen"], 2) if p else "",
        _si_no(p["desactualizado"]) if p else "",
        str(d["profesionales"]) if d else "",
        _numero(d["espera_media_min"]) if d else "",
        _si_no(d["por_validar"]) if d else "",
        _numero(mp["valor"]),
        mp["fecha"].isoformat() if mp["fecha"] else "",
        mp["nivel"]["nombre"] if mp["nivel"] else ("datos insuficientes" if mp["estado"] != "ok" else ""),
        mp["estacion"] or "",
        _si_no(mp["de_respaldo"]) if mp["valor"] is not None else "",
        FUENTE,
    ]


def csv_de_estados(estados: Iterable[dict[str, Any]]) -> bytes:
    """El archivo completo, en UTF-8 con BOM."""
    salida = io.StringIO()
    escritor = csv.writer(salida, delimiter=";", lineterminator="\r\n")
    escritor.writerow(COLUMNAS)
    for estado in estados:
        escritor.writerow(fila_csv(estado))
    return salida.getvalue().encode("utf-8-sig")
