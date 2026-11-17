"""Planificador de las corridas programadas (RNF-P-1, RNF-P-2, TC-13, T11).

Uso, desde ``backend/`` (en Docker Compose es el servicio ``planificador``)::

    .venv/Scripts/python -m sart.planificador              # queda corriendo
    .venv/Scripts/python -m sart.planificador --mostrar    # muestra lo que correría en las próximas 24 h

Cada minuto revisa qué tareas tocan según ``horarios`` (``sart.dominio.planificador``) y las corre una por
una, cada una en su propio proceso (``python -m …``): si una falla o se cae, el planificador sigue y la
siguiente corre igual. Cada tarea registra su corrida en la base (RNF-M-3); aquí solo queda el log. Lee los
parámetros en cada vuelta, así que un cambio de horario en el YAML rige sin reiniciar. Al arrancar no pone al
día las corridas perdidas.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
import time as reloj
from collections.abc import Callable
from datetime import UTC, datetime, timedelta

from sart.dominio.planificador import ErrorHorarios, Tarea, tareas_debidas
from sart.parametros import ErrorParametros, cargar_parametros

Ejecutor = Callable[[Tarea], int]


def _log(mensaje: str) -> None:
    print(f"{datetime.now(UTC):%Y-%m-%d %H:%M:%S} UTC · {mensaje}", flush=True)


def ejecutar_en_proceso(tarea: Tarea) -> int:
    """Corre la tarea como ``python -m …`` y devuelve su código de salida."""
    try:
        return subprocess.run([sys.executable, "-m", *tarea.comando], check=False).returncode
    except OSError as error:
        _log(f"{tarea.nombre}: no se pudo iniciar ({error})")
        return 1


def una_vuelta(
    desde: datetime, hasta: datetime, ejecutar: Ejecutor = ejecutar_en_proceso
) -> list[tuple[str, int]]:
    """Corre lo que toca en ``(desde, hasta]``; devuelve (tarea, código) de cada una."""
    parametros = cargar_parametros()
    resultados = []
    for momento, tarea in tareas_debidas(desde, hasta, parametros["horarios"], parametros["zona_horaria"]):
        _log(f"{tarea.nombre} ({momento:%H:%M} hora local): python -m {' '.join(tarea.comando)}")
        codigo = ejecutar(tarea)
        _log(f"{tarea.nombre}: {'terminó bien' if codigo == 0 else f'falló con código {codigo}'}")
        resultados.append((tarea.nombre, codigo))
    return resultados


def correr(ejecutar: Ejecutor = ejecutar_en_proceso) -> None:  # pragma: no cover (ciclo infinito)
    desde = datetime.now(UTC)
    _log("planificador iniciado")
    while True:
        reloj.sleep(max(1.0, 60 - datetime.now(UTC).second))
        hasta = datetime.now(UTC)
        try:
            una_vuelta(desde, hasta, ejecutar)
        except (ErrorParametros, ErrorHorarios, KeyError) as error:
            _log(f"no se pudieron leer los horarios: {error}")
        desde = hasta


def mostrar(ahora: datetime | None = None) -> str:
    parametros = cargar_parametros()
    ahora = ahora or datetime.now(UTC)
    filas = tareas_debidas(
        ahora, ahora + timedelta(hours=24), parametros["horarios"], parametros["zona_horaria"]
    )
    return "\n".join(f"{m:%a %d/%m %H:%M} · {t.nombre}: python -m {' '.join(t.comando)}" for m, t in filas)


def main(argv: list[str] | None = None) -> int:
    analizador = argparse.ArgumentParser(
        prog="python -m sart.planificador", description=__doc__.splitlines()[0]
    )
    analizador.add_argument("--mostrar", action="store_true", help="lo que correría en las próximas 24 h")
    args = analizador.parse_args(argv)
    try:
        if args.mostrar:
            print(mostrar())
            return 0
        correr()  # pragma: no cover
    except (ErrorParametros, ErrorHorarios, KeyError) as error:
        print(f"No se pudo iniciar el planificador: {error}", file=sys.stderr)
        return 1
    return 0  # pragma: no cover


if __name__ == "__main__":
    sys.exit(main())
