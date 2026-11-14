# SART · Sistema de Alerta Respiratoria Temprana

Pronóstico semanal de consultas respiratorias y alertas tempranas para los 33 centros de urgencia del Gran Concepción.
Proyecto Informático, Ingeniería Civil Informática, Universidad de Concepción, 2026.

Equipo: Benjamín Díaz Ulloa, Daniel Aburto Rivera, Juan Carvajal Ramírez, Joaquín Sandoval Reyes,
Mario Salgado Orellana, Jocabed López Flores.

## Cómo levantarlo en local

Requisitos: [Docker Desktop](https://www.docker.com/products/docker-desktop/), Python 3.12
(recomendado con [uv](https://docs.astral.sh/uv/)) y Node 20 o superior.

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
   Para que una jefatura vea su centro, cargue el catálogo y asígnele uno (código DEIS del centro):
   ```bash
   .venv/Scripts/python -m sart.catalogo cargar --prueba       # centros, consultas y mediciones de datos/prueba (~1 min)
   .venv/Scripts/python -m sart.cuentas asignar-centro --correo jefatura@demo.sart --centro 100001
   ```
6. **Administradores: MFA** (RNF-S-1). Una cuenta con `--rol administrador` no puede entrar hasta activar
   el código de una aplicación de autenticación (Google Authenticator, Microsoft Authenticator, Authy…):
   ```bash
   .venv/Scripts/python -m sart.cuentas activar-mfa --correo admin@demo.sart     # muestra la clave
   .venv/Scripts/python -m sart.cuentas confirmar-mfa --correo admin@demo.sart --codigo 123456
   .venv/Scripts/python -m sart.cuentas reiniciar-mfa --correo admin@demo.sart   # teléfono perdido
   ```
   Al iniciar sesión, después de la contraseña la web pide el código de 6 dígitos.

## Documentos

- Especificación: `docs/especificacion/`
- Instrucciones para el asistente de código: `CLAUDE.md`
- El frontend parte de ing-software2 (licencia MIT, ver `web/LICENSE-ing-software2`).

Datos: DEIS/MINSAL (CC BY-NC), establecimientos (CC0), SINCA/MMA, Open-Meteo.
