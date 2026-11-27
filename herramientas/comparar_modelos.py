"""Comparación reproducible del GLM quasi-Poisson actual con la alternativa Binomial Negativa y dos líneas base
(CI-1, RF-2, RNF-Q-1, RNF-Q-2, RNF-Q-3).

Mismos centros, mismo panel y mismo período de prueba (2024 hasta la última semana completa, RB-4). Los
parámetros que se eligen (α de la Binomial Negativa y el margen k de cada modelo) se calibran solo con el
entrenamiento: se entrena con los años anteriores a 2023 y se valida en 2023. Después se reentrena con todos los
años anteriores a 2024 y se mide una sola vez en la prueba.

Uso (desde backend/, con el venv):
    python ../herramientas/comparar_modelos.py                     # arma el panel desde DATABASE_URL
    python ../herramientas/comparar_modelos.py --panel RUTA.parquet  # o usa un panel ya armado

Escribe ``docs/resultados/comparacion_modelos.md`` y ``.csv`` y guarda el panel usado en
``datos/procesados/panel_sistema.parquet`` (fuera de git).
"""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd

from sart.configuracion import RAIZ_REPOSITORIO
from sart.dominio.modelo import (
    ajustar,
    ajustar_binomial_negativa,
    con_margen,
    dividir,
    elegir_alfa,
    elegir_k,
    evaluar_alertas,
    metricas,
    predecir,
    terminos_del_modelo,
    terminos_disponibles,
)
from sart.dominio.umbrales import calcular_umbrales, semanas_de_la_ventana
from sart.parametros import cargar_parametros

PRECISION_MINIMA = 0.70  # RNF-Q-2 (el criterio de aceptación, no un supuesto del modelo)
ALFAS = [0.005, 0.01, 0.02, 0.03, 0.05, 0.08, 0.12, 0.2]
KS = [round(0.1 * i, 1) for i in range(16)]
SALIDA = RAIZ_REPOSITORIO / "docs" / "resultados"


def panel_desde_base(parametros: dict) -> tuple[pd.DataFrame, pd.Timestamp]:
    from sqlalchemy.orm import Session

    from sart.db.sesion import crear_motor
    from sart.tareas.panel import panel_desde_la_base
    from sart.tareas.semanas_y_umbrales import marcar_semanas

    with Session(crear_motor()) as sesion:
        corte = marcar_semanas(sesion, parametros, confirmar=False)
        panel = panel_desde_la_base(sesion, parametros, hasta=corte)
    destino = RAIZ_REPOSITORIO / "datos" / "procesados" / "panel_sistema.parquet"
    destino.parent.mkdir(parents=True, exist_ok=True)
    panel.to_parquet(destino)
    return panel, pd.Timestamp(corte)


def umbrales_de(entrenamiento: pd.DataFrame, parametros: dict) -> pd.DataFrame:
    """RB-3 con las últimas 156 semanas válidas hasta el fin del tramo de entrenamiento que se use."""
    modelo, umbrales = parametros["modelo"], parametros["umbrales"]
    series = {e: dict(zip(g["inicio_semana"].dt.date, g["y"], strict=True)) for e, g in entrenamiento.groupby("estab")}
    calculados = calcular_umbrales(
        series,
        hasta=entrenamiento["inicio_semana"].max().date(),
        semanas=semanas_de_la_ventana(umbrales["anios_umbral"]),
        anios_excluidos=modelo["anios_excluidos"],
        cuantil_atencion=umbrales["cuantil_atencion"],
        cuantil_alerta=umbrales["cuantil_alerta"],
        minimo_semanas=modelo["min_semanas_historia"],
    )
    return pd.DataFrame([{"estab": e, "umbral_alerta": u.alerta} for e, u in calculados.items()])


def comparar(panel: pd.DataFrame, hasta: pd.Timestamp, parametros: dict) -> tuple[pd.DataFrame, dict]:
    modelo = parametros["modelo"]
    nivel = modelo["nivel_intervalo"]
    prueba_desde = modelo["anio_inicio_prueba"]
    terminos = terminos_disponibles(panel, terminos_del_modelo("solo_rezagos", modelo["armonicos"]))
    kwargs = {"anios_excluidos": modelo["anios_excluidos"], "min_semanas": modelo["min_semanas_historia"]}

    # 1) Calibración: entrenar < 2023, validar en 2023 (nada de la prueba)
    entr_in, valid = dividir(panel, anio_inicio_prueba=prueba_desde - 1,
                             hasta=pd.Timestamp(f"{prueba_desde - 1}-12-31"), **kwargs)
    valid = valid[valid["anio"] == prueba_desde - 1].merge(umbrales_de(entr_in, parametros), on="estab")
    alfa, tabla_alfa = elegir_alfa(entr_in, valid, terminos, ALFAS)
    v_qp = predecir(ajustar(entr_in, terminos), valid, terminos, nivel)
    v_nb = predecir(ajustar_binomial_negativa(entr_in, terminos, alfa), valid, terminos, nivel)
    k_qp, _ = elegir_k(v_qp, KS, precision_minima=PRECISION_MINIMA, nivel_intervalo=nivel)
    k_nb, _ = elegir_k(v_nb, KS, precision_minima=PRECISION_MINIMA, nivel_intervalo=nivel)

    # 2) Prueba: reentrenar con todo lo anterior a 2024 y medir una sola vez
    entr, prueba = dividir(panel, anio_inicio_prueba=prueba_desde, hasta=hasta, **kwargs)
    prueba = prueba.merge(umbrales_de(entr, parametros), on="estab")
    p_qp = predecir(ajustar(entr, terminos), prueba, terminos, nivel)
    p_nb = predecir(ajustar_binomial_negativa(entr, terminos, alfa), prueba, terminos, nivel)
    comunes = p_qp.index.intersection(p_nb.index).intersection(prueba.dropna(subset=["y_l1", "y_l52"]).index)
    p_qp, p_nb, base = p_qp.loc[comunes], p_nb.loc[comunes], prueba.loc[comunes]

    filas = []
    k_spec = parametros["regla_alerta"]["k_margen"]
    for nombre, d, k_cal in (("GLM quasi-Poisson (actual)", p_qp, k_qp), ("GLM Binomial Negativa", p_nb, k_nb)):
        cobertura = float(((d["y"] >= d["pred_inf"]) & (d["y"] <= d["pred_sup"])).mean())
        for etiqueta, k in ((f"k calibrado = {_c(k_cal)}", k_cal), (f"k del sistema = {_c(k_spec)}", k_spec)):
            a = evaluar_alertas(d.assign(m=con_margen(d, k, nivel)), "m")
            filas.append({"modelo": nombre, "regla": etiqueta, **_fila(d["y"], d["pred"], a), "cobertura_90": cobertura})
    for nombre, col in (("Línea base: semana anterior", "y_l1"), ("Línea base: misma semana del año anterior", "y_l52")):
        d = base.assign(pred=base[col])
        filas.append({"modelo": nombre, "regla": "sin margen", **_fila(d["y"], d["pred"], evaluar_alertas(d)),
                      "cobertura_90": np.nan})
    contexto = {"alfa": alfa, "tabla_alfa": tabla_alfa, "k_qp": k_qp, "k_nb": k_nb, "filas_prueba": len(comunes),
                "centros": base["estab"].nunique(), "desde": base["inicio_semana"].min().date(),
                "hasta": base["inicio_semana"].max().date(), "filas_validacion": len(v_qp)}
    return pd.DataFrame(filas), contexto


def _c(x) -> str:
    return f"{x:g}".replace(".", ",")


def _fila(y, pred, alertas) -> dict:
    return {"WAPE_%": metricas(y, pred)["WAPE_%"], "precision": alertas["precision"],
            "sensibilidad": alertas["sensibilidad"], "alertas": alertas["alertas_emitidas"],
            "semanas_altas": alertas["semanas_altas_reales"]}


def escribir(tabla: pd.DataFrame, contexto: dict) -> Path:
    SALIDA.mkdir(parents=True, exist_ok=True)
    tabla.to_csv(SALIDA / "comparacion_modelos.csv", index=False)
    def f(x, d=3):
        return "—" if pd.isna(x) else f"{x:.{d}f}".replace(".", ",")

    lineas = [
        "| Modelo | Regla | WAPE | Precisión | Sensibilidad | Alertas | Semanas altas | Cobertura 90 % |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for r in tabla.to_dict("records"):
        lineas.append(f"| {r['modelo']} | {r['regla']} | {f(r['WAPE_%'], 2)} % | {f(r['precision'])} | "
                      f"{f(r['sensibilidad'])} | {r['alertas']} | {r['semanas_altas']} | {f(r['cobertura_90'])} |")
    alfas = " · ".join(f"α = {_c(a['alfa'])}: {a['log_verosimilitud']:.0f}" for a in contexto["tabla_alfa"].to_dict("records"))
    c = contexto
    texto = f"""# Comparación de modelos de pronóstico (CI-1, RF-2, RNF-Q-1 a Q-3)

Generado con `herramientas/comparar_modelos.py` (no editar a mano; la conclusión está en
`docs/pendientes_informe.md` #60). Panel del sistema armado desde los datos públicos reales.

- **Prueba:** {c['filas_prueba']} semanas-centro de {c['centros']} centros, del {c['desde']} al {c['hasta']}
  (las mismas filas para todos los modelos y líneas base).
- **Calibración (sin la prueba):** entrenamiento con los años anteriores a 2023 (sin 2020 ni 2021) y validación
  en 2023 ({c['filas_validacion']} semanas-centro). α de la Binomial Negativa con la mejor log-verosimilitud en la
  validación: **α = {_c(c['alfa'])}** ({alfas}). Margen k con la mayor sensibilidad entre los que dan precisión
  ≥ {_c(PRECISION_MINIMA)} en la validación: **k = {_c(c['k_qp'])}** (quasi-Poisson) y **k = {_c(c['k_nb'])}** (Binomial
  Negativa). Después se reentrena con todos los años anteriores a 2024.
- Semana alta: consultas observadas sobre el umbral de alerta del centro (p90 de RB-3 con el entrenamiento).

{chr(10).join(lineas)}
"""
    ruta = SALIDA / "comparacion_modelos.md"
    ruta.write_text(texto, encoding="utf-8")
    return ruta


def main() -> None:
    analizador = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    analizador.add_argument("--panel", type=Path, help="panel semanal ya armado (parquet)")
    analizador.add_argument("--hasta", help="última semana completa AAAA-MM-DD (con --panel)")
    args = analizador.parse_args()
    parametros = cargar_parametros()
    if args.panel:
        panel = pd.read_parquet(args.panel)
        hasta = pd.Timestamp(args.hasta) if args.hasta else panel["inicio_semana"].max()
    else:
        panel, hasta = panel_desde_base(parametros)
    tabla, contexto = comparar(panel, hasta, parametros)
    print(tabla.to_string(index=False))
    print({k: v for k, v in contexto.items() if k != "tabla_alfa"})
    print("Escrito:", escribir(tabla, contexto))


if __name__ == "__main__":
    main()
