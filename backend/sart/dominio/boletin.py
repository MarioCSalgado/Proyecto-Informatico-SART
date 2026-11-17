"""Boletín del lunes redactado por un LLM (RF-8, TC-18, RNF-S-5). Lógica pura: no toca la base ni la red.

El LLM **solo redacta**: recibe cifras agregadas por centro (nivel, pronóstico, límite superior y dotación),
nunca nombres ni correos de usuarios, y no puede cambiar un nivel. Antes de usar su texto se revisa que cada
cifra exista en los datos y que ningún centro aparezca con otro nivel; si algo no cuadra, o si no hay
proveedor configurado (pendientes #12), sale el boletín de plantilla, que se arma con las mismas cifras.
"""

from __future__ import annotations

import re
from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass
from typing import Any, Literal

ETIQUETA_NIVEL = {"alerta": "ALERTA", "atencion": "atención", "normal": "normal"}
# Palabras con que un texto puede nombrar cada nivel (en minúsculas)
_PALABRAS_NIVEL = {"alerta": ("alerta",), "atencion": ("atención", "atencion"), "normal": ("normal",)}
_NUMERO = re.compile(r"\d+(?:[.,]\d+)*")


class ErrorDatosPersonales(ValueError):
    """El texto para el LLM contiene un nombre o un correo de usuario: no se envía (RNF-S-5)."""


@dataclass(frozen=True)
class FilaBoletin:
    """Cifras agregadas de un centro para el boletín; es todo lo que ve el LLM."""

    centro: str
    nivel: Literal["normal", "atencion", "alerta"]
    pronostico: int
    limite_superior: int
    profesionales: int | None  # None: sin dotación sugerida (p. ej. un SUR, pendientes #40)


def filas_desde_estado(estados: Iterable[dict[str, Any]]) -> tuple[int, int, list[FilaBoletin]]:
    """Año, semana y filas desde ``estado_de_centros`` (RF-7): las cifras guardadas, no recalculadas (#39).

    Se omiten los centros sin pronóstico o sin nivel (RF-3 E1). Mantiene el orden de RF-7 (alerta primero).
    """
    filas, anio, semana = [], 0, 0
    for e in estados:
        p = e["pronostico"]
        if p is None or p["nivel"] is None:
            continue
        anio, semana = p["anio"], p["semana"]
        filas.append(
            FilaBoletin(
                centro=e["centro"]["nombre"],
                nivel=p["nivel"],
                pronostico=round(p["valor"]),
                limite_superior=round(p["limite_superior"]),
                profesionales=e["dotacion"]["profesionales"] if e["dotacion"] else None,
            )
        )
    return anio, semana, filas


def _linea(f: FilaBoletin) -> str:
    dotacion = f"; se sugieren {f.profesionales} profesionales en hora punta" if f.profesionales else ""
    return (
        f"- {f.centro}: nivel {ETIQUETA_NIVEL[f.nivel]}, {f.pronostico} consultas esperadas "
        f"(hasta {f.limite_superior}){dotacion}."
    )


def boletin_plantilla(anio: int, semana: int, filas: Sequence[FilaBoletin]) -> str:
    """Boletín sin LLM, con las mismas cifras. Es el respaldo cuando el texto del LLM no cuadra."""
    conteo = {n: sum(f.nivel == n for f in filas) for n in ETIQUETA_NIVEL}
    resumen = (
        f"Boletín SART, SE {semana} de {anio}. De {len(filas)} centros: {conteo['alerta']} en ALERTA, "
        f"{conteo['atencion']} en atención y {conteo['normal']} en nivel normal."
    )
    destacados = [_linea(f) for f in filas if f.nivel != "normal"]
    return "\n".join([resumen, *destacados, "Informa, no decide: la dotación es una sugerencia."])


def prompt_boletin(anio: int, semana: int, filas: Sequence[FilaBoletin]) -> str:
    datos = "\n".join(_linea(f) for f in filas)
    return (
        "Redacta en español de Chile un boletín breve (máximo 120 palabras) para jefaturas de urgencia.\n"
        f"Semana epidemiológica {semana} de {anio}. Datos por centro:\n{datos}\n"
        "Reglas: usa solo estas cifras, sin redondear ni calcular otras; "
        "no cambies el nivel de ningún centro; "
        "escribe el nombre de cada centro tal cual y en una línea propia; no des recomendaciones clínicas."
    )


def _a_numero(texto: str) -> float:
    return float(texto.replace(".", "").replace(",", "."))  # 1.234 → 1234; 12,5 → 12.5


def problemas_del_texto(texto: str, filas: Sequence[FilaBoletin], *, anio: int, semana: int) -> list[str]:
    """Cifras que no están en los datos y centros nombrados con otro nivel (TC-18). Vacía: el texto cuadra."""
    conteos = {sum(f.nivel == n for f in filas) for n in ETIQUETA_NIVEL}
    permitidos = {anio, semana, len(filas), *conteos} | {
        v for f in filas for v in (f.pronostico, f.limite_superior, f.profesionales) if v is not None
    }
    problemas = [
        f"cifra {n} no está en los datos" for n in _NUMERO.findall(texto) if _a_numero(n) not in permitidos
    ]

    # ponytail: heurística por tramo de texto (desde el nombre del centro hasta el siguiente centro o fin de
    # línea); un párrafo que mezcla centros puede dar un falso positivo, que solo hace salir la plantilla.
    minusculas = texto.lower()
    posiciones = sorted(
        (m.start(), f) for f in filas for m in re.finditer(re.escape(f.centro.lower()), minusculas)
    )
    for i, (inicio, fila) in enumerate(posiciones):
        salto = minusculas.find("\n", inicio)
        fin = min([salto if salto != -1 else len(minusculas), *(p for p, _ in posiciones[i + 1 :])])
        tramo = minusculas[inicio + len(fila.centro) : fin]
        otros = [
            n
            for n, palabras in _PALABRAS_NIVEL.items()
            if n != fila.nivel and any(p in tramo for p in palabras)
        ]
        if otros:
            problemas.append(f"{fila.centro} aparece como {', '.join(otros)} y su nivel es {fila.nivel}")
    return problemas


def _datos_personales(texto: str, cuentas: Iterable[tuple[str, str]]) -> bool:
    minusculas = texto.lower()
    return "@" in texto or any(n.lower() in minusculas or c.lower() in minusculas for n, c in cuentas)


def redactar_boletin(
    anio: int,
    semana: int,
    filas: Sequence[FilaBoletin],
    *,
    redactor: Callable[[str], str] | None,
    cuentas: Iterable[tuple[str, str]],
) -> tuple[str, Literal["llm", "plantilla"]]:
    """Texto del boletín y su origen. ``cuentas``: (nombre, correo) de los usuarios, para revisar el envío.

    Lanza ``ErrorDatosPersonales`` sin llamar al LLM si el texto a enviar nombra a un usuario (RNF-S-5).
    """
    plantilla = boletin_plantilla(anio, semana, filas)
    if redactor is None:
        return plantilla, "plantilla"
    prompt = prompt_boletin(anio, semana, filas)
    if _datos_personales(prompt, list(cuentas)):
        raise ErrorDatosPersonales("El texto para el LLM nombra a un usuario: no se envía.")
    texto = redactor(prompt)
    if problemas_del_texto(texto, filas, anio=anio, semana=semana):
        return plantilla, "plantilla"
    return texto, "llm"
