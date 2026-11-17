# Cómo trabajar en SART

Guía para el equipo. Lo que el sistema debe hacer está en `docs/especificacion/` (no se edita a mano); qué está
hecho y qué falta, en `docs/avance.md`; las tareas para tomar, en `docs/tareas_equipo.md`.

## 1. Instalación (unos 10 minutos)

Requisitos: [Docker Desktop](https://www.docker.com/products/docker-desktop/), Python 3.12 con
[uv](https://docs.astral.sh/uv/) y Node 22 o superior.

```bash
cp .env.example .env                 # cambiar la clave de PostgreSQL y el JWT_SECRET (instrucciones en el archivo)
docker compose up -d db              # PostgreSQL 16
docker compose exec db pg_isready    # «accepting connections»

cd backend
uv venv --python 3.12 .venv && uv pip install -e ".[dev]"
.venv/Scripts/python -m alembic upgrade head        # en Linux/macOS: .venv/bin/python
.venv/Scripts/python -m sart.demo preparar             # datos de prueba, pronóstico y cuentas demo (ver README)
.venv/Scripts/python -m uvicorn sart.api.app:app --port 8000

cd ../web
npm install
npm run dev                          # http://localhost:5173
```

Para entrar, las cuentas demo del `README.md` (las mismas del video): por ejemplo `jefatura.capturas@demo.sart`
con la clave `demo-WYDVvVkcQmq_jO4I`; el administrador `admin@demo.sart` pide además el código `123456`.

Si el puerto 5432 está ocupado, en `.env` usar `POSTGRES_PORT=5433` y `:5433` en `DATABASE_URL`. Más comandos en
`CLAUDE.md` (sección «Comandos») y en el `README.md`.

## 2. Flujo de trabajo

1. **Elegir una tarea** de `docs/tareas_equipo.md` (la asigna Mario en la columna «Responsable»). Si no está en el
   tablero, conversarla antes.
2. **Una rama por tarea**, desde `main` actualizado, con el requisito y una descripción corta:
   `rf-5/correo-alerta`, `rf-11/exportacion-csv`, `docs/guia-instalacion`.
3. **La prueba primero:** desde el Gherkin de §3.2 o el TC de §11 (ver la sección 3), y después el código.
4. **Commits pequeños, en español y con IDs:** `RF-5: correo de alerta con nivel y dotación (TC-06)`.
5. **Antes del PR**, en local:
   ```bash
   cd backend && .venv/Scripts/python -m ruff check . && .venv/Scripts/python -m pytest
   cd web && npm run lint && npm run build && npx vitest run
   ```
6. **Pull request a `main`**, con qué hace, qué IDs cubre, cómo se probó y capturas si toca pantallas (GitHub abre
   la plantilla `.github/pull_request_template.md` con esos campos). **Lo revisa
   un compañero** antes de unirlo, y la CI (GitHub Actions) tiene que estar en verde: ruff, pytest con PostgreSQL,
   cobertura ≥ 70 % en `sart/dominio` y `sart/tareas`, y lint, build y Vitest de la web.
7. Al terminar: marcar la tarea en `docs/tareas_equipo.md` y, si implementaste un TC, su estado en
   `docs/estado_tc.md`.

**Si algo tiene que apartarse de la especificación**, no se hace en silencio: se anota en
`docs/pendientes_informe.md` (qué, por qué y qué sección del informe cambia) y se avisa en el PR.

## 3. Cómo escribir la prueba de un TC o de un requisito

- **Un archivo por caso**, con el ID en el nombre: `backend/tests/test_tc06_correo_y_acuse.py`,
  `test_rf10_historial.py`. Las funciones también llevan el ID: `def test_tc06_reenvio_a_las_24_horas(...)`.
- **Del Gherkin a la prueba:** el «Dado» arma los datos, el «Cuando» llama a la función o a la ruta, y el
  «Entonces» son los `assert`. Con las cifras del informe cuando las hay (por ejemplo, TC-07: 545 consultas en
  123 h → 3 profesionales y 4,2 min de espera).
- **Lógica pura** (`sart/dominio`): pruebas sin base, rápidas. Es donde va la mayor parte de la lógica.
- **Con base de datos:** el fixture `motor_memoria` (SQLite en memoria, vacía) o `base_prueba` (una copia de
  SQLite con todo `datos/prueba` cargado; ver `tests/conftest.py`). Ejemplos: `test_rf2_rf3_corrida_semanal.py`.
- **API:** `TestClient` con la base de prueba; para el acceso por rol, ver `test_tc09_rf7_estado_centros.py`.
- **Necesita PostgreSQL de verdad:** marcarla con `@pytest.mark.integracion` y usar `crear_base_temporal`; en un
  equipo sin base se salta sola.
- **Web:** Vitest y Testing Library; se simula la API con `vi.spyOn(clienteApi, 'get')`. Ejemplo:
  `web/src/tests/estadoCentros.test.tsx`. Buscar por rol y por texto (como lo usa una persona), no por clase CSS.

## 4. Dónde va cada cosa

| Qué | Dónde |
|---|---|
| Cálculos y reglas (sin base ni web) | `backend/sart/dominio/` |
| Consultas y escrituras en la base | `backend/sart/db/` |
| Corridas programadas | `backend/sart/tareas/` |
| Rutas de la API (solo acceso y formato) | `backend/sart/api/` |
| Supuestos y umbrales | `config/parametros.yaml` |
| Pantallas, componentes y servicios | `web/src/pantallas/`, `web/src/componentes/`, `web/src/servicios/` |
| Colores, tipografía y componentes visuales | `DESIGN.md` (léelo antes de tocar estilos) |

El primer endpoint de lectura, `GET /centros/estado` (RF-7), sirve de ejemplo de punta a punta: lógica en
`sart/dominio/estado_centro.py`, consulta en `sart/db/estado_centros.py`, ruta en `sart/api/centros.py`, servicio
en `web/src/servicios/centros.ts` y hook en `web/src/hooks/useEstadoCentros.ts`.

## 5. Reglas que no se negocian

Vienen de `CLAUDE.md` y del informe; un PR que no las cumple no entra.

- **0 datos de pacientes** en la base, los logs o las respuestas (RNF-S-5). Solo conteos agregados.
- **Ningún supuesto escrito en el código:** k, percentiles, minutos por atención, horarios, plazos… se leen de
  `config/parametros.yaml` (RNF-M-4); en las corridas, con `parametros_vigentes(sesion)`.
- **Toda ruta con datos de un centro** revisa el rol en la API (RNF-S-2); la web solo decide qué se muestra.
- **El nivel nunca se muestra solo con color** (RNF-U-1): siempre con texto o ícono.
- **El LLM solo redacta** (RF-8): recibe cifras agregadas y no puede cambiar un nivel.
- **Semanas epidemiológicas del MINSAL** (domingo a sábado); la última semana incompleta se marca y no se usa
  (RB-4).
- **Todo en español** (código de dominio sin tildes en los identificadores: `pronostico`, `umbral_alerta`).
- **Nunca subir** `.env`, `datos/` (salvo `datos/prueba/`), `respaldos/` ni nada de `referencia/`.
- Datos de urgencias con licencia CC BY-NC: uso no comercial y citar la fuente.
