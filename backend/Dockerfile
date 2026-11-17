# SART · imagen del backend (RNF-P-1): la API y el planificador usan la misma imagen.
# Se construye desde la raíz del repositorio: docker compose build (contexto ".", ver docker-compose.yml).
# trixie trae el cliente de PostgreSQL 17, que respalda y restaura la base 16 (RNF-D-2, sart.respaldo).
FROM python:3.12-slim-trixie

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

RUN apt-get update \
    && apt-get install -y --no-install-recommends postgresql-client \
    && rm -rf /var/lib/apt/lists/*

# El código queda en /app/backend y los parámetros en /app/config: sart.configuracion toma /app como la raíz
# del repositorio, igual que en desarrollo (config/parametros.yaml, datos/, respaldos/).
WORKDIR /app/backend
COPY backend/pyproject.toml ./
COPY backend/sart ./sart
RUN pip install -e .
COPY backend/alembic.ini ./
COPY backend/migraciones ./migraciones
COPY config /app/config

RUN useradd --create-home --uid 1000 sart && mkdir -p /app/datos /app/respaldos && chown -R sart /app
USER sart

EXPOSE 8000
CMD ["sh", "-c", "alembic upgrade head && uvicorn sart.api.app:app --host 0.0.0.0 --port 8000"]
