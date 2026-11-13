# Qué reutilizar de ing-software2

`referencia/ing-software2` es el proyecto del ramo Ingeniería de Software 2 (sistema de convivencia escolar),
licencia MIT (© 2026 Fabián González y equipo). Se puede reutilizar conservando el aviso de licencia:
copiar `LICENSE` como `web/LICENSE-ing-software2` y mencionarlo en el README y en el Anexo E del informe.

Su stack: **Express + TypeScript + Prisma** (backend) y **React + Vite + MUI** (frontend).
SART usa FastAPI en Python, así que **se reutiliza el frontend y los patrones, no el backend**.

## Frontend (`main/` → `web/`)

| Tomar | Para qué en SART |
|---|---|
| Configuración de Vite, TypeScript, ESLint, Vitest y Testing Library | Base del proyecto web |
| `services/axiosInstance.ts`, `services/paths.ts` | Cliente de la API |
| `context/authContext.tsx`, `LoginScreen` | Inicio de sesión |
| `auth/permissions.ts` + `RequirePermission` + `usePermissions` | Permisos por rol, cambiando los roles a Jefatura, Subdirector y Administrador |
| `UserManagementScreen` | RF-9 y RF-16: agregar centros asignados y la aceptación de la finalidad |
| `Toast`, `EmptyState`, `Skeleton`, `TopBar`, `SuccessModal`, `Icon` | Componentes genéricos |

Descartar: pantallas de incidentes, intervenciones y estudiantes, y sus imágenes.

Cambio necesario: ing-software2 navega con un estado `screen` en `App.tsx`, sin URLs. SART necesita **rutas con
URL** (react-router), porque el correo de RF-5/RF-15 lleva un enlace a la página de acuse.

## Backend (solo como referencia de patrones)

| En ing-software2 | Equivalente en SART |
|---|---|
| `requireRoles(...)` de Express | Dependencia de FastAPI `requiere_rol(...)` |
| `authService.ts` con bcrypt + JWT | Argon2id (RNF-S-1) + JWT en cookie httpOnly |
| `schema.prisma` + migraciones | Modelos SQLAlchemy + Alembic, según `docs/especificacion/05_datos.md` |
| Pruebas `tests/api` y `tests/db` con supertest | `backend/tests` con pytest y el cliente de pruebas de FastAPI |
| Usuario con `activo` y validación después de la contraseña | Igual (no revelar qué correos existen) |

## No copiar

- `api/config/.env.development`: tiene un `JWT_SECRET` y una `DATABASE_URL` reales. Generar secretos nuevos.
- Las credenciales escritas en `docker-compose.yml` (`admin/admin123`): en SART van en `.env`.
- `base_de_datos_archivos/` (datos del liceo).
