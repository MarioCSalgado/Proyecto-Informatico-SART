# SART · Sistema de Alerta Respiratoria Temprana

Pronóstico semanal de consultas respiratorias y alertas tempranas para los 33 centros de urgencia del Gran Concepción.
Proyecto Informático, Ingeniería Civil Informática, Universidad de Concepción, 2026.

Equipo: Benjamín Díaz Ulloa, Daniel Aburto Rivera, Juan Carvajal Ramírez, Joaquín Sandoval Reyes,
Mario Salgado Orellana, Jocabed López Flores.

## Estado

Base del sistema terminada (14/11/2026): cuentas con MFA, base de datos, carga de datos, modelo y reglas de
alerta probados, la corrida semanal que guarda pronósticos, niveles y dotación, y la web con «Mi centro» y la
«Red de centros» mostrando esos datos. Falta, entre otras cosas, la descarga automática, los correos y la
administración desde la web: el detalle está en [`docs/avance.md`](docs/avance.md) y las tareas del equipo en
[`docs/tareas_equipo.md`](docs/tareas_equipo.md). Para colaborar, ver [`CONTRIBUTING.md`](CONTRIBUTING.md).

## Cómo levantarlo en local

Requisitos: [Docker Desktop](https://www.docker.com/products/docker-desktop/), Python 3.12
(recomendado con [uv](https://docs.astral.sh/uv/)) y Node 22 o superior (la CI usa Node 22).

1. **Configuración.** Copiar `.env.example` a `.env` y cambiar la clave de PostgreSQL y el `JWT_SECRET`.
   El `.env` nunca se sube a git. La API lo lee sola; no hace falta pasarlo como argumento.
2. **Base de datos.** Con Docker Desktop abierto:
   ```bash
   docker compose up -d db
   docker compose exec db pg_isready      # debe decir «accepting connections»
   ```
   Si el puerto 5432 ya está ocupado (por ejemplo, por un PostgreSQL instalado en el equipo), en `.env`
   cambiar `POSTGRES_PORT=5433` y el puerto de `DATABASE_URL` a `:5433`, y volver a correr `docker compose up -d db`.
3. **Backend** (en `backend/`):
   ```bash
   uv venv --python 3.12 .venv
   uv pip install -e ".[dev]"
   .venv/Scripts/python -m alembic upgrade head  # crea o actualiza las tablas
   .venv/Scripts/python -m pytest --cov=sart     # en Linux/macOS: .venv/bin/python
   .venv/Scripts/python -m ruff check .
   .venv/Scripts/python -m uvicorn sart.api.app:app --port 8000
   ```
   Abrir http://127.0.0.1:8000/salud (debe decir `"estado":"ok"`) o http://127.0.0.1:8000/docs.
4. **Web** (en `web/`):
   ```bash
   npm install
   npm run build && npm run lint && npx vitest run
   npm run dev
   ```
   Abrir http://localhost:5173. La web llama a `/api/...` y Vite lo reenvía a la API en el puerto 8000.
5. **Cuenta para entrar** (en `backend/`; pide la contraseña, mínimo 12 caracteres):
   ```bash
   .venv/Scripts/python -m sart.cuentas crear --nombre "Jefatura Demo" --correo jefatura@demo.sart \
       --rol jefatura --acepta-finalidad
   ```
   `--acepta-finalidad` deja constancia de que la persona aceptó el uso de sus datos (RF-16).
   Para que las pantallas tengan datos, cargue los de prueba, calcule los umbrales, corra el pronóstico de la
   semana y asígnele un centro a la jefatura (código DEIS del centro):
   ```bash
   .venv/Scripts/python -m sart.catalogo cargar --prueba       # centros, consultas y mediciones de datos/prueba (~1 min)
   .venv/Scripts/python -m sart.catalogo recalcular-umbrales   # percentiles 75 y 90 de cada centro (RB-3)
   .venv/Scripts/python -m sart.tareas semanal --prueba        # pronóstico, nivel y dotación (RF-2, RF-3, RF-6)
   .venv/Scripts/python -m sart.cuentas asignar-centro --correo jefatura@demo.sart --centro 100001
   ```
   La jefatura ve «Mi centro»; para ver la «Red de centros», cree también una cuenta con `--rol subdirector`.
   Como los datos de prueba terminan en septiembre de 2026, las pantallas avisan que el pronóstico está
   desactualizado y que los datos son antiguos: es lo esperado.
   Para cambiar la contraseña de una cuenta: `.venv/Scripts/python -m sart.cuentas restablecer-clave --correo …`.

6. **Administradores: MFA** (RNF-S-1). Una cuenta con `--rol administrador` no puede entrar hasta activar
   el código de una aplicación de autenticación (Google Authenticator, Microsoft Authenticator, Authy…):
   ```bash
   .venv/Scripts/python -m sart.cuentas activar-mfa --correo admin@demo.sart     # muestra la clave
   .venv/Scripts/python -m sart.cuentas confirmar-mfa --correo admin@demo.sart --codigo 123456
   .venv/Scripts/python -m sart.cuentas reiniciar-mfa --correo admin@demo.sart   # teléfono perdido
   ```
   Al iniciar sesión, después de la contraseña la web pide el código de 6 dígitos.
   **Solo para probar en local**, se puede fijar un código en `.env` con `MFA_CODIGO_DESARROLLO=123456`: rige
   únicamente con `COOKIE_SEGURA=false` y `/salud` avisa que está activo. Nunca en producción.

7. **Respaldo** (RNF-D-2): `.venv/Scripts/python -m sart.respaldo crear` deja una copia en `respaldos/` (fuera de
   git: tiene nombres y correos). Para volver a una copia: `… restaurar respaldos/ARCHIVO.dump --confirmar` (reemplaza
   toda la base) y después `python -m sart.catalogo cargar …` para recargar las fuentes públicas.

## Documentos

- **Para colaborar:** `CONTRIBUTING.md` (ramas, PR, pruebas y reglas) y `docs/tareas_equipo.md` (tareas y
  responsables)
- **Diseño de la web:** `DESIGN.md` (colores, tipografía y componentes; leer antes de tocar pantallas)
- Especificación: `docs/especificacion/`
- Qué está hecho y qué sigue: `docs/avance.md`; casos de prueba: `docs/estado_tc.md`
- Diferencias con el informe que hay que corregir en él: `docs/pendientes_informe.md`
- Instrucciones para el asistente de código: `CLAUDE.md` y `PASOS.md`
- El frontend parte de ing-software2 (licencia MIT, ver `web/LICENSE-ing-software2`).

Datos: DEIS/MINSAL (CC BY-NC), establecimientos (CC0), SINCA/MMA, Open-Meteo.
