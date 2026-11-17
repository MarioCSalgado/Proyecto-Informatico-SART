"""Normalización pura de los dos contratos de urgencias (RF-1, TC-01 y TC-02)."""

from __future__ import annotations

from fractions import Fraction

import pandas as pd

from sart.dominio.catalogo import clave_causa
from sart.dominio.semanas import fracciones_de_etiqueta, inicio_semana
from sart.dominio.valores import GRUPOS_EDAD_DEIS

EDADES_REALES = dict(
    zip(
        ["NumMenor1Anio", "Num1a4Anios", "Num5a14Anios", "Num15a64Anios", "Num65oMas"],
        GRUPOS_EDAD_DEIS.values(),
        strict=True,
    )
)
CLAVE = ["centro_id", "anio", "semana", "causa", "grupo_edad"]


def codigo_deis(valor) -> int | None:
    """Admite códigos numéricos y códigos antiguos con guion, no trunca decimales."""
    if pd.isna(valor) or not str(valor).strip():
        return None
    texto = str(valor).strip()
    if texto.endswith(".0"):
        texto = texto[:-2]
    texto = texto.replace("-", "")
    if not texto.isascii() or not texto.isdecimal():
        raise ValueError(f"Código de establecimiento inválido: {valor!r}")
    return int(texto)


def repartir_entero(cantidad: int, fracciones: dict[tuple[int, int], float]) -> dict[tuple[int, int], int]:
    """Mayor resto; conserva cantidades, con desempate cronológico y aritmética racional."""
    if cantidad < 0 or int(cantidad) != cantidad:
        raise ValueError("La cantidad debe ser entera y no negativa.")
    pesos = {k: Fraction(v).limit_denominator(366) for k, v in fracciones.items()}
    if not pesos or any(v <= 0 for v in pesos.values()) or sum(pesos.values()) != 1:
        raise ValueError("Las fracciones deben ser positivas y sumar uno.")
    exactos = {k: cantidad * v for k, v in pesos.items()}
    salida = {k: int(v) for k, v in exactos.items()}
    orden = sorted(pesos, key=lambda k: (-(exactos[k] - salida[k]), k))
    for clave in orden[: cantidad - sum(salida.values())]:
        salida[clave] += 1
    return salida


def normalizar_consultas(datos: pd.DataFrame, centros: dict[int, int], causas: dict[str, str]):
    """Devuelve filas internas agrupadas y métricas. El real debe ser la copia completa original.

    Se reparten y agrupan únicamente los registros publicados. La ausencia de una combinación
    centro/año/semana/causa no permite distinguir un recorte de una ausencia legítima y no se
    interpreta como cero ni como error. El llamador debe proporcionar la publicación completa
    para las recargas: esta función no puede certificar su integridad histórica.
    """
    real = "EstablecimientoCodigo" in datos
    codigo = "EstablecimientoCodigo" if real else "IdEstablecimiento"
    edades = EDADES_REALES if real else GRUPOS_EDAD_DEIS
    total = "NumTotal" if real else "Total"
    requeridas = [codigo, "Anio", "SemanaEstadistica", "Causa", *edades]
    if real:
        requeridas.append(total)
    faltantes = [c for c in requeridas if c not in datos]
    if faltantes:
        raise ValueError(f"Faltan las columnas: {', '.join(faltantes)}")
    if real and "IdEstablecimiento" in datos:
        raise ValueError("El archivo mezcla los perfiles real y sintético de establecimientos.")
    # Solo columnas del contrato: evita copiar las columnas geográficas de millones de filas.
    seleccion = list(dict.fromkeys([*requeridas, *([total] if total in datos else [])]))
    datos = datos[seleccion].copy()
    codigos = {v: codigo_deis(v) for v in datos[codigo].dropna().unique()}
    datos["codigo"] = datos[codigo].map(codigos).astype("Int64")
    metricas = {"filas_sin_codigo": int(datos["codigo"].isna().sum()), "duplicados_omitidos": 0}
    en_catalogo = datos["codigo"].isin(centros)
    metricas["establecimientos_sin_catalogo"] = int(datos.loc[~en_catalogo, "codigo"].nunique())
    datos = datos.loc[en_catalogo].copy()
    glosas = datos["Causa"].dropna().unique()
    datos["causa"] = datos["Causa"].map({g: clave_causa(g, causas) for g in glosas})
    metricas["causas_omitidas"] = datos.loc[datos["causa"].isna(), "Causa"].value_counts().to_dict()
    datos = datos.loc[datos["causa"].notna()].copy()
    if datos.empty:
        return pd.DataFrame(columns=[*CLAVE, "cantidad"]), metricas
    numericas = ["Anio", "SemanaEstadistica", *edades]
    if total in datos:
        numericas.append(total)
    for columna in numericas:
        valores = pd.to_numeric(datos[columna], errors="coerce")
        if (valores.isna() | (valores < 0) | (valores % 1 != 0) | (valores > 2147483647)).any():
            raise ValueError(f"{columna}: se requieren enteros no negativos, no nulos, de 32 bits.")
        datos[columna] = valores.astype("int64")
    if total in datos and datos[list(edades)].sum(axis=1).ne(datos[total]).any():
        raise ValueError(f"La suma de edades difiere de {total}.")
    clave_origen = ["codigo", "Anio", "SemanaEstadistica", "Causa"]
    # Las dimensiones extra no autorizan sumar dos reportes de una misma causa.
    antes = len(datos)
    datos = datos.drop_duplicates()
    metricas["duplicados_omitidos"] = antes - len(datos)
    if datos.duplicated(clave_origen).any():
        raise ValueError("Conteos contradictorios para una misma clave de origen; no se sumaron.")
    datos["centro_id"] = datos["codigo"].map(centros)
    datos = datos.rename(columns={"Anio": "anio", "SemanaEstadistica": "semana"})
    largo = datos.melt(
        id_vars=["centro_id", "anio", "semana", "causa"],
        value_vars=list(edades),
        var_name="grupo_edad",
        value_name="cantidad",
    )
    largo["grupo_edad"] = largo["grupo_edad"].map(edades)
    largo = largo.groupby(CLAVE, as_index=False)["cantidad"].sum()
    if not real:
        for anio, semana in largo[["anio", "semana"]].drop_duplicates().itertuples(index=False, name=None):
            inicio_semana(int(anio), int(semana))
        return largo, metricas
    pares = set(datos[["anio", "semana"]].itertuples(index=False, name=None))
    primero, ultimo = int(datos.anio.min()), int(datos.anio.max())
    metricas["anios_origen"] = (primero, ultimo)
    mapas = {}
    for anio, semana in pares:
        partes = fracciones_de_etiqueta(int(anio), int(semana))
        # El año en curso no aporta días de diciembre aún no publicados.
        if anio == ultimo and (ultimo, 52) not in pares:
            partes = {k: v for k, v in partes.items() if k[0] <= ultimo}
            suma = sum(partes.values())
            partes = {k: v / suma for k, v in partes.items()}
        mapas[anio, semana] = partes
    # Un centro puede empezar a reportar después o una causa incorporarse en otro año.
    # No exigir el producto cartesiano de centros, causas y etiquetas vecinas.
    # Los aportes existentes se suman por su clave destino al final del reparto.
    filas = []
    for centro, anio, semana, causa, grupo, cantidad in largo.itertuples(index=False, name=None):
        for (a, s), n in repartir_entero(int(cantidad), mapas[anio, semana]).items():
            filas.append((centro, a, s, causa, grupo, n))
    salida = pd.DataFrame(filas, columns=[*CLAVE, "cantidad"]).groupby(CLAVE, as_index=False).cantidad.sum()
    if salida.cantidad.gt(2147483647).any():
        raise ValueError("La cantidad agrupada excede el entero de 32 bits.")
    return salida, metricas
