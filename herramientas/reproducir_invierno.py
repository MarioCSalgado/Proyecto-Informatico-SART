"""TC-19, RF-10: reproduce las corridas de los lunes del invierno 2025 y compara las alertas con lo observado.

Sin información futura: los umbrales son los del recálculo de marzo de 2025 (RB-3, datos hasta febrero) y cada
semana se pronostica con las consultas hasta su fecha de corte (``correr_semanal(fecha_corte=…)``). Las alertas
quedan con la fecha de emisión de su lunes, como las vería el historial (RF-10).

**Modifica la base**: córralo sobre una copia (por ejemplo, una SQLite con los datos públicos reales).
Uso (desde backend/, con el venv y DATABASE_URL apuntando a la copia):
    python ../herramientas/reproducir_invierno.py --confirmar

Escribe ``docs/resultados/tc19_invierno_2025.md`` y ``tc19_invierno_2025.csv``.
"""

from __future__ import annotations

import argparse
from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

import pandas as pd
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from sart.configuracion import RAIZ_REPOSITORIO
from sart.db.alertas import historial_de_alertas
from sart.db.modelos import CentroSalud, ConsultaSemanal, Pronostico, SemanaCarga, UmbralCentro
from sart.db.sesion import crear_motor
from sart.db.supuestos import parametros_vigentes
from sart.dominio.semanas import semana_epidemiologica
from sart.tareas.semanal import correr_semanal
from sart.tareas.semanas_y_umbrales import recalcular_umbrales

SALIDA = RAIZ_REPOSITORIO / "docs" / "resultados"


def reproducir(sesion: Session, desde: date, hasta: date, umbrales_hasta: date) -> list[str]:
    parametros = parametros_vigentes(sesion)
    zona = ZoneInfo(parametros["zona_horaria"])
    recalcular_umbrales(sesion, hasta=umbrales_hasta, parametros=parametros)
    hora = time.fromisoformat(parametros["horarios"]["pronostico"])
    textos, objetivo = [], desde
    while objetivo <= hasta:
        emision = datetime.combine(objetivo + timedelta(days=1), hora, tzinfo=zona)  # lunes de esa semana
        resumen = correr_semanal(sesion, fecha_corte=objetivo - timedelta(weeks=1), emision=emision)
        textos.append(resumen.texto().splitlines()[0])
        objetivo += timedelta(weeks=1)
    return textos


def observado(sesion: Session, causas: list[str]) -> dict[tuple[int, int, int], int]:
    """Total respiratorio por centro y semana, solo en semanas completas (RB-4), como el historial."""
    filas = sesion.execute(
        select(ConsultaSemanal.centro_id, ConsultaSemanal.anio, ConsultaSemanal.semana,
               func.sum(ConsultaSemanal.cantidad))
        .join(SemanaCarga, (SemanaCarga.anio == ConsultaSemanal.anio) & (SemanaCarga.semana == ConsultaSemanal.semana))
        .where(ConsultaSemanal.causa.in_(causas), SemanaCarga.completa.is_(True))
        .group_by(ConsultaSemanal.centro_id, ConsultaSemanal.anio, ConsultaSemanal.semana)
    ).all()
    return {(c, a, s): int(t) for c, a, s, t in filas}


def comparar(sesion: Session, desde: date, hasta: date) -> tuple[pd.DataFrame, dict]:
    causas = parametros_vigentes(sesion)["ingesta"]["causas_en_consultas"]
    obs = observado(sesion, causas)
    sd, sh = semana_epidemiologica(desde), semana_epidemiologica(hasta)
    filas = []
    for p, centro, umbral in sesion.execute(
        select(Pronostico, CentroSalud, UmbralCentro)
        .join(CentroSalud, Pronostico.centro_id == CentroSalud.id)
        .join(UmbralCentro, Pronostico.umbral_id == UmbralCentro.id)
        .where(Pronostico.vigente.is_(True))
    ).all():
        if not (sd <= (p.anio, p.semana) <= sh):
            continue
        y = obs.get((p.centro_id, p.anio, p.semana))
        filas.append({
            "anio": p.anio, "semana": p.semana, "centro": centro.nombre, "codigo_deis": centro.codigo_deis,
            "nivel": p.nivel, "pronostico": round(p.valor, 1), "con_margen": round(p.valor_con_margen, 1),
            "umbral_alerta": umbral.umbral_alerta, "observado": y,
            "semana_alta": None if y is None else y > umbral.umbral_alerta,
        })
    tabla = pd.DataFrame(filas).sort_values(["anio", "semana", "centro"])

    # Lo que muestra el historial (RF-10) para las mismas semanas, contra el cálculo independiente de arriba
    centros = list(sesion.scalars(select(CentroSalud)))
    historial = historial_de_alertas(sesion, centros, causas, desde=sd, hasta=sh)
    distintos = 0
    for alerta, centro, pronostico, umbral_alerta, consultas in historial:
        esperado = obs.get((centro.id, pronostico.anio, pronostico.semana))
        if consultas != esperado or alerta.nivel != pronostico.nivel:
            distintos += 1
    evaluable = tabla.dropna(subset=["semana_alta"])
    alerta = evaluable["nivel"] == "alerta"
    alta = evaluable["semana_alta"].astype(bool)
    aciertos = int((alerta & alta).sum())
    resumen = {
        "semanas": tabla[["anio", "semana"]].drop_duplicates().shape[0],
        "pronosticos": len(tabla), "evaluables": len(evaluable),
        "alertas": int(alerta.sum()), "atencion": int((evaluable["nivel"] == "atencion").sum()),
        "semanas_altas": int(alta.sum()), "aciertos": aciertos,
        "precision": aciertos / alerta.sum() if alerta.sum() else float("nan"),
        "sensibilidad": aciertos / alta.sum() if alta.sum() else float("nan"),
        "filas_historial": len(historial), "historial_distintos": distintos,
    }
    return tabla, resumen


def escribir(tabla: pd.DataFrame, resumen: dict, textos: list[str], desde: date, hasta: date,
             umbrales_hasta: date) -> None:
    SALIDA.mkdir(parents=True, exist_ok=True)
    tabla.to_csv(SALIDA / "tc19_invierno_2025.csv", index=False)

    def c(x, d=3):
        return "—" if pd.isna(x) else f"{x:.{d}f}".replace(".", ",")

    alertas = tabla[tabla["nivel"] == "alerta"]
    lineas = ["| Semana | Centro | Pronóstico + margen | Umbral de alerta | Observado | ¿Semana alta? |",
              "|---|---|---|---|---|---|"]
    for r in alertas.to_dict("records"):
        alta = "sin dato" if r["semana_alta"] is None else ("sí" if r["semana_alta"] else "no")
        lineas.append(f"| SE {r['semana']} de {r['anio']} | {r['centro']} | {c(r['con_margen'], 1)} | "
                      f"{c(r['umbral_alerta'], 1)} | {r['observado'] if r['observado'] is not None else '—'} | {alta} |")
    r = resumen
    texto = f"""# TC-19 · Historial de alertas con el invierno 2025 (RF-10)

Generado con `herramientas/reproducir_invierno.py` sobre una copia de la base con los datos públicos reales (no
editar a mano). Semanas objetivo del {desde} al {hasta}; umbrales de RB-3 calculados con datos hasta el
{umbrales_hasta} (recálculo de marzo de 2025); cada semana se pronosticó solo con las consultas hasta su fecha
de corte, con el k del sistema. Semana alta: total observado sobre el umbral de alerta original del centro.

- **{r['semanas']} semanas**, {r['pronosticos']} pronósticos ({r['evaluables']} con observación válida).
- **{r['alertas']} alertas ALERTA** y {r['atencion']} en atención; {r['semanas_altas']} semanas realmente altas.
- Aciertos: {r['aciertos']} → **precisión {c(r['precision'])}** y **sensibilidad {c(r['sensibilidad'])}** en
  el invierno (RNF-Q-2 pide ≥ 0,70 y ≥ 0,60 sobre el período de prueba completo).
- **Historial (RF-10):** {r['filas_historial']} filas (ALERTA y atención); {r['historial_distintos']} con un
  observado o un nivel distinto del cálculo independiente.

## Corridas

{chr(10).join('- ' + t for t in textos)}

## Alertas ALERTA frente a lo observado

{chr(10).join(lineas)}
"""
    (SALIDA / "tc19_invierno_2025.md").write_text(texto, encoding="utf-8")


def main() -> None:
    analizador = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    analizador.add_argument("--desde", type=date.fromisoformat, default=date(2025, 5, 4), help="primera semana")
    analizador.add_argument("--hasta", type=date.fromisoformat, default=date(2025, 9, 28), help="última semana")
    analizador.add_argument("--umbrales-hasta", type=date.fromisoformat, default=date(2025, 2, 23))
    analizador.add_argument("--confirmar", action="store_true", help="modifica la base: úselo en una copia")
    args = analizador.parse_args()
    if not args.confirmar:
        raise SystemExit("Este script modifica la base (umbrales, pronósticos y alertas): use --confirmar en una copia.")
    with Session(crear_motor()) as sesion:
        textos = reproducir(sesion, args.desde, args.hasta, args.umbrales_hasta)
        tabla, resumen = comparar(sesion, args.desde, args.hasta)
    escribir(tabla, resumen, textos, args.desde, args.hasta, args.umbrales_hasta)
    print("\n".join(textos))
    print(resumen)


if __name__ == "__main__":
    main()
