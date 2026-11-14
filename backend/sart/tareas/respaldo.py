"""Respaldo diario de la base y restauración (RNF-D-2: RPO 24 h, RTO 2 h; TC-14).

Se respalda lo propio del sistema (cuentas, aceptaciones de RF-16, centros, umbrales, pronósticos, alertas,
notificaciones, acuses, auditoría…) con ``pg_dump`` en formato propio. De las fuentes públicas
(``respaldo.tablas_sin_datos``: consultas del DEIS y mediciones) se guarda solo la estructura: se vuelven a
descargar. Los respaldos quedan en ``respaldo.carpeta``, fuera de la base; en producción hay que copiarlos
además a otro proveedor (RNF-D-2, pendientes #38). Tienen datos personales de las cuentas (§5.3): no van a
git.

Herramienta: ``pg_dump``/``pg_restore`` del contenedor de la base si está corriendo (misma versión que el
servidor); si no, los del sistema, con la clave en ``PGPASSWORD`` y nunca en la línea de comandos.
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
from datetime import datetime
from pathlib import Path

from sqlalchemy.engine import make_url

from sart.configuracion import RAIZ_REPOSITORIO

PATRON_RESPALDO = re.compile(r"^.+_(\d{8}_\d{6})\.dump$")
SEGUNDOS_MAXIMOS = 1800


class ErrorRespaldo(RuntimeError):
    """No se pudo respaldar o restaurar. El mensaje explica por qué."""


def nombre_respaldo(base: str, momento: datetime) -> str:
    return f"{base}_{momento:%Y%m%d_%H%M%S}.dump"


def docker_disponible() -> bool:
    """True si el servicio ``db`` de docker-compose está corriendo."""
    try:
        resultado = subprocess.run(
            ["docker", "compose", "ps", "--status", "running", "--services"],
            cwd=RAIZ_REPOSITORIO,
            capture_output=True,
            text=True,
            timeout=20,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False
    return resultado.returncode == 0 and "db" in resultado.stdout.split()


def comando(herramienta: str, url: str) -> tuple[list[str], dict[str, str]]:
    """Inicio de la línea de comandos de ``pg_dump`` o ``pg_restore`` y el entorno con que se ejecuta."""
    destino = make_url(url)
    if docker_disponible():
        return ["docker", "compose", "exec", "-T", "db", herramienta, "-U", destino.username], dict(
            os.environ
        )
    ruta = shutil.which(herramienta)
    if ruta is None:
        raise ErrorRespaldo(
            f"No se encontró {herramienta}: levante el contenedor de la base (docker compose up -d db) o "
            "instale el cliente de PostgreSQL 16."
        )
    argv = [ruta, "-h", destino.host or "127.0.0.1", "-p", str(destino.port or 5432), "-U", destino.username]
    return argv, {**os.environ, "PGPASSWORD": destino.password or ""}


def crear_respaldo(
    url: str, carpeta: Path, tablas_sin_datos: list[str], ahora: datetime | None = None
) -> Path:
    """Respalda la base de ``url`` en ``carpeta`` y devuelve el archivo. Si falla, no deja archivos."""
    base = make_url(url).database
    carpeta = Path(carpeta)
    carpeta.mkdir(parents=True, exist_ok=True)
    archivo = carpeta / nombre_respaldo(base, ahora or datetime.now())
    argv, entorno = comando("pg_dump", url)
    argv += ["--format=custom", "--no-owner", "--no-privileges"]
    argv += [f"--exclude-table-data={tabla}" for tabla in tablas_sin_datos]
    argv.append(base)
    with archivo.open("wb") as salida:
        resultado = subprocess.run(
            argv,
            stdout=salida,
            stderr=subprocess.PIPE,
            env=entorno,
            cwd=RAIZ_REPOSITORIO,
            timeout=SEGUNDOS_MAXIMOS,
        )
    if resultado.returncode != 0 or archivo.stat().st_size == 0:
        archivo.unlink(missing_ok=True)
        detalle = resultado.stderr.decode("utf-8", errors="replace").strip()
        raise ErrorRespaldo(f"pg_dump falló con la base {base}: {detalle}")
    return archivo


def restaurar_respaldo(url: str, archivo: Path) -> None:
    """Restaura ``archivo`` en la base de ``url``, reemplazando lo que haya (todo o nada: una transacción)."""
    base = make_url(url).database
    argv, entorno = comando("pg_restore", url)
    argv += [
        "--clean",
        "--if-exists",
        "--no-owner",
        "--no-privileges",
        "--single-transaction",
        "--exit-on-error",
    ]
    argv += ["-d", base]
    with Path(archivo).open("rb") as entrada:
        resultado = subprocess.run(
            argv,
            stdin=entrada,
            capture_output=True,
            env=entorno,
            cwd=RAIZ_REPOSITORIO,
            timeout=SEGUNDOS_MAXIMOS,
        )
    if resultado.returncode != 0:
        detalle = resultado.stderr.decode("utf-8", errors="replace").strip()
        raise ErrorRespaldo(f"pg_restore falló en la base {base}: {detalle}")


def respaldos(carpeta: Path) -> list[Path]:
    """Respaldos de la carpeta, del más antiguo al más reciente (según la fecha del nombre)."""
    carpeta = Path(carpeta)
    if not carpeta.is_dir():
        return []
    encontrados = [(PATRON_RESPALDO.match(a.name), a) for a in carpeta.iterdir() if a.is_file()]
    return [a for m, a in sorted((m.group(1), a) for m, a in encontrados if m)]


def podar_respaldos(carpeta: Path, conservar: int) -> list[Path]:
    """Borra los respaldos más antiguos y deja los ``conservar`` más recientes. Devuelve los borrados."""
    todos = respaldos(carpeta)
    borrar = todos[: max(0, len(todos) - conservar)]
    for archivo in borrar:
        archivo.unlink()
    return borrar
