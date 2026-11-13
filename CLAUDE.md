# SART · Sistema de Alerta Respiratoria Temprana

Proyecto del ramo Proyecto Informático (UdeC, 2026). Aplicación web que cada lunes pronostica las consultas
respiratorias de la semana en 33 centros de urgencia del Gran Concepción, avisa por correo a las jefaturas y al
Subdirector asistencial cuando un centro va a estar sobre lo habitual o se espera MP2,5 alto, y sugiere cuántos
profesionales tener en hora punta. **Informa, no decide.** Trabaja solo con conteos públicos agregados (DEIS,
SINCA, Open-Meteo); nunca con datos de pacientes.

Idioma: todo en español (código de dominio, mensajes, interfaz, commits y documentación). Identificadores de
código en español sin tildes (`pronostico`, `umbral_alerta`).

## Fuente de verdad

La especificación está en `docs/especificacion/` (exportada del informe SRS IEEE 830 del curso):

| Archivo | Contenido |
|---|---|
| `03_requisitos_funcionales.md` | RF-1 a RF-16 con flujos y criterios Gherkin |
| `04_requisitos_no_funcionales.md` | RNF con métrica, objetivo y método de verificación |
| `05_datos.md` | Modelo de información (entidades) e interfaces externas |
| `06_reglas_de_negocio.md` | RB-1 a RB-5 |
| `11_trazabilidad.md` | Matriz RF → RNF → TC y casos de prueba TC-01 a TC-20 |
| `02_restricciones_y_ciencias.md` | Restricciones de diseño (cost, schedule, legal…) y CI-1 a CI-3 |

Además: `docs/arquitectura.md`, `config/parametros.yaml`, `docs/pendientes_informe.md`, `docs/plan_reutilizacion_ing-software2.md`.

Reglas para usar la especificación:
1. Cita siempre los IDs (RF-x, RNF-x, RB-x, TC-x) en docstrings, nombres de pruebas y mensajes de commit.
2. Si el código necesita apartarse de la especificación, **no lo hagas en silencio**: anótalo en
   `docs/pendientes_informe.md` (qué, por qué, qué sección del informe hay que cambiar) y avísame.
3. No edites los archivos de `docs/especificacion/` a mano: se regeneran desde el informe con
   `python herramientas/docx_a_markdown.py <informe.docx> "3." "4."`.

## Stack (decidido en el informe y en la E2; no cambiarlo sin acuerdo del equipo)

- **web/**: React + TypeScript + Vite, MUI, react-hook-form + zod, axios. Base: `referencia/ing-software2/main`.
- **backend/**: Python 3.12, un solo paquete `sart` con:
  - `sart/api` → FastAPI (única puerta de entrada a la base; 3 roles; auditoría) — RNF-S-2, RNF-S-4
  - `sart/tareas` → corridas programadas: ingesta 05:00, pronóstico lunes 06:00, alerta ambiental 07:00, boletín antes de 08:00
  - `sart/dominio` → lógica pura y probada: semanas epidemiológicas, modelo GLM quasi-Poisson, umbrales, regla de alerta, RB-1, Erlang C
  - SQLAlchemy 2 + Alembic, PostgreSQL 16, statsmodels/pandas/numpy/scipy
- Contraseñas con Argon2id (RNF-S-1), JWT en cookie httpOnly, MFA solo para administradores.
- Docker Compose para todo (RNF-P-1); límite 2 vCPU y 4 GB (RNF-P-2).
- Calidad: pytest + pytest-cov (≥ 70 % en `sart/dominio` y `sart/tareas`, RNF-M-1), ruff con 0 errores (RNF-M-2), GitHub Actions.

## Estructura

```
SART/
├── CLAUDE.md
├── docker-compose.yml        .env.example (nunca subir .env)
├── config/parametros.yaml    ← todos los supuestos y umbrales (RNF-M-4)
├── backend/
│   ├── pyproject.toml
│   ├── sart/{api,tareas,dominio,db}/
│   └── tests/                ← un archivo por caso: test_tc07_erlang.py, test_tc17_regla_alerta.py…
├── web/
├── notebooks/analisis_informatico5.ipynb   ← prototipo vigente; de aquí sale la lógica del modelo
├── datos/                    ← crudos y procesados reales: NO se suben a git (pesan ~70 MB)
│   └── prueba/               ← datos sintéticos pequeños para pruebas: SÍ se suben
├── docs/
├── herramientas/
└── referencia/ing-software2/ ← código de otro ramo, solo para consultar; NO se sube a git
```

## Reglas que no se negocian

- **0 datos de pacientes** en la base, los logs o las respuestas (RNF-S-5). Los conteos del DEIS son agregados por centro y semana.
- **El LLM solo redacta** (RF-8): recibe cifras agregadas, nunca nombres ni correos, y no puede cambiar un nivel.
- **Ningún supuesto escrito en el código**: k, percentiles, minutos por atención, factor de hora punta, horas de
  funcionamiento, horarios, plazos de RB-2… se leen de `config/parametros.yaml` (RNF-M-4, RF-9).
- **Semanas epidemiológicas del MINSAL** (domingo a sábado; la SE 1 es la primera que tiene 4 o más días del año).
- **La última semana publicada, si viene incompleta, se marca y no se usa** (RB-4).
- **El nivel nunca se muestra solo con color** (RNF-U-1): siempre con texto o ícono.
- El acuse de lectura se registra con un botón «Confirmar lectura», no por abrir el enlace (RF-15).
- Datos públicos con licencia CC BY-NC (urgencias): uso no comercial y citar la fuente.

## Cómo trabajar en este repo

- Antes de un cambio grande, propón un plan corto y espera mi visto bueno.
- Lógica nueva → primero la prueba (desde el Gherkin de §3.2 o el TC de §11), después el código.
- Al migrar funciones del notebook, agrega una prueba de regresión que reproduzca sus cifras del backtest
  2024–2026: WAPE 14,9 %; con k = 0 precisión 0,85 y sensibilidad 0,48; con k = 0,4 precisión 0,73 y sensibilidad 0,66.
- Cuando un TC quede implementado y pasando, actualiza su estado en `docs/estado_tc.md` (no en la especificación).
- Commits pequeños, en español, con IDs: `RF-3: regla de alerta con margen k (TC-17)`.
- No copies secretos de `referencia/` (allí hay un `.env.development` con un JWT_SECRET real).

## Comandos

Requisitos: Docker Desktop, Python 3.12 (con `uv` o `venv`), Node 20+. La API lee el `.env` de la raíz sola
(`sart/configuracion.py`); las variables de entorno tienen prioridad sobre el archivo.

```bash
cp .env.example .env                          # una vez; cambiar clave y JWT_SECRET
docker compose up -d db                       # PostgreSQL 16 en 127.0.0.1:${POSTGRES_PORT:-5432}
docker compose exec db pg_isready             # comprobar que responde

# backend (una vez: crear el venv e instalar)
cd backend && uv venv --python 3.12 .venv && uv pip install -e ".[dev]"
cd backend && .venv/Scripts/python -m alembic upgrade head  # crear/actualizar las tablas
cd backend && .venv/Scripts/python -m sart.cuentas crear --nombre "…" --correo … --rol jefatura --acepta-finalidad
                                              # crear una cuenta (RF-16); pide la contraseña
cd backend && .venv/Scripts/python -m sart.cuentas activar-mfa --correo …   # MFA de un administrador:
cd backend && .venv/Scripts/python -m sart.cuentas confirmar-mfa --correo … --codigo 123456  # (RNF-S-1)
cd backend && .venv/Scripts/python -m pytest --cov=sart     # pruebas (en Linux/macOS: .venv/bin/python)
                                              # las marcadas «integracion» usan PostgreSQL y se saltan sin él
cd backend && .venv/Scripts/python -m ruff check .          # estilo
cd backend && .venv/Scripts/python -m uvicorn sart.api.app:app --port 8000   # API → http://127.0.0.1:8000/salud

# web
cd web && npm install
cd web && npm run build && npm run lint && npx vitest run   # compilar, estilo, pruebas
cd web && npm run dev                         # → http://localhost:5173
```

Si el puerto 5432 ya está ocupado (por ejemplo, un PostgreSQL instalado en Windows), en `.env` poner
`POSTGRES_PORT=5433` y usar `:5433` en `DATABASE_URL`; luego `docker compose up -d db` de nuevo.
