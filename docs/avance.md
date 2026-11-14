# Avance del código

Estado al **14 de noviembre de 2026**: primer avance de código funcional, la base del sistema. Este documento
resume qué hay, qué falta y en qué orden seguir. El detalle de cada paso para el asistente de código está en
`PASOS.md`; las desviaciones de la especificación, en `docs/pendientes_informe.md`; los casos de prueba, en
`docs/estado_tc.md`.

## Qué funciona hoy

| Área | Qué hace | IDs | Dónde |
|---|---|---|---|
| Entorno | PostgreSQL 16 en Docker; la API lee el `.env` sola; puerto configurable (5433 si 5432 está ocupado) | RNF-P-1, RNF-P-2 | `docker-compose.yml`, `backend/sart/configuracion.py` |
| Parámetros | Todos los supuestos y umbrales en el YAML; el administrador ajusta solo las claves de `administracion.parametros_editables` y las corridas leen `parametros_vigentes(sesion)` | RNF-M-4, RF-9 | `config/parametros.yaml`, `sart/db/supuestos.py` (pendientes #31) |
| Cuentas | Alta solo con la aceptación de la finalidad, Argon2id, 3 roles, centros asignados, restablecer clave; todo queda en la auditoría | RF-16, RF-9, RNF-S-1, TC-16 | `python -m sart.cuentas …` |
| Sesión | JWT en cookie httpOnly, cierre de sesión, MFA con códigos TOTP para administradores (bloqueo tras 5 fallos) | RNF-S-1, RNF-S-2 | `sart/api/auth.py` |
| Base de datos | 16 tablas: las entidades de §5.1 y las de apoyo (semanas cargadas, umbrales con historia, ajustes de parámetros, corridas, auditoría), con 4 migraciones de Alembic | §5.1 | `sart/db/modelos.py`, `migraciones/` |
| Carga de datos | Catálogo de centros, zonas y estaciones; consultas del DEIS; MP2,5 de SINCA; clima y MP2,5 previsto de Open-Meteo, **desde archivos ya descargados** en `datos/` | RF-1, CI-3 | `python -m sart.catalogo cargar [--prueba]` |
| Corridas | Cada carga queda registrada (inicio, fin, estado, filas); aviso tras fallas seguidas de una fuente | RNF-M-3 | `sart/tareas/corridas.py` |
| Semanas | Semanas epidemiológicas del MINSAL y marca de la semana incompleta | RB-4, TC-01 | `sart/dominio/semanas.py`, `semana_completa.py` |
| Umbrales | p75 y p90 por centro con las últimas 156 semanas válidas, recálculo anual en marzo, respeta los ajustes manuales | RB-3 | `python -m sart.catalogo recalcular-umbrales` |
| Modelo | GLM quasi-Poisson con rezagos (opción C), intervalo de 90 % | RF-2, TC-03, TC-11 | `sart/dominio/modelo.py` |
| Regla de alerta | Normal, atención o ALERTA con el margen k | RF-3, TC-04, TC-17 | `sart/dominio/alerta_demanda.py` |
| MP2,5 | Clasificación en 5 niveles | RB-1, TC-05 | `sart/dominio/mp25.py` |
| Dotación | Erlang C y profesionales mínimos en hora punta | RF-6, TC-07 | `sart/dominio/dotacion.py` |
| Respaldo | Respaldo diario, poda y restauración probada en 59 s | RNF-D-2, TC-14 | `python -m sart.respaldo …` |
| API | `GET /salud`, `POST /auth/sesion`, `GET /auth/yo`, `POST /auth/cerrar-sesion`, `GET /referencias` | RNF-S-2 | `sart/api/` · documentación en http://127.0.0.1:8000/docs |
| Web | Inicio de sesión (con el código MFA), encabezado por rol, permisos, rutas con URL; partes fijas de los diseños de Figma para Mi centro, Red de centros y Administración, de 390 px a 1440 px; la escala de MP2,5 viene de la API | RF-7, RNF-U-1, RNF-S-2 | `web/src/` |

### Cifras verificadas

- Backend: **266 pruebas pasan** sin la base; con PostgreSQL y `datos/` corren además las de integración, TC-14
  y la regresión. Cobertura de `sart/dominio` + `sart/tareas`: **95 %** (RNF-M-1 pide ≥ 70 %). Ruff: 0 errores.
- Web: **37 pruebas** con Vitest, lint y build sin errores.
- Regresión del backtest 2024–2026 con los datos reales: WAPE 14,9 %; k = 0 → precisión 0,85 y sensibilidad
  0,48; k = 0,4 → 0,73 y 0,66; línea base «semana anterior» → 0,69 y 0,68; cobertura del intervalo 91,1 %.

## Qué falta

Lo de dominio está hecho y probado, pero **todavía no está conectado**: ninguna tarea calcula y guarda
pronósticos ni alertas en la base, y la API no tiene endpoints para leerlos. Por eso las pantallas muestran
sus partes fijas con estados vacíos.

| Falta | IDs |
|---|---|
| Corrida semanal que guarda pronósticos y alertas en la base | RF-2, RF-3, RF-6 |
| Endpoints de lectura del estado de los centros y conectarlos a la web | RF-7, TC-09 |
| CI en GitHub Actions y guía para el equipo | TC-13, RNF-M-1, RNF-M-2 |
| Descarga automática de DEIS, SINCA y Open-Meteo, con aviso si una fuente falla | RF-1, TC-02 |
| Alerta ambiental diaria a las 07:00 | RF-4, TC-12 |
| Correo de alerta, «Confirmar lectura», reenvío a las 24 h y escalamiento a las 48 h | RF-5, RF-15, RB-2, TC-06 |
| Administración desde la web: cuentas, centros asignados, umbrales y parámetros | RF-9, RF-16 |
| Historial de alertas | RF-10, TC-19 |
| Exportación CSV | RF-11, TC-15 |
| Mapa de centros | RF-12, TC-20 |
| Boletín redactado con el LLM | RF-8, TC-18 |
| Planificador de horarios (05:00, 06:00, 07:00, 08:00, respaldo 04:30) y Docker Compose con API y web | RNF-P-1, TC-13 |
| Pruebas de carga y de uso | TC-08, TC-10 |

## Decisiones ya tomadas

Están anotadas en `docs/pendientes_informe.md` para pasarlas al informe. Las principales:

- **RB-4 (1A):** una semana está completa si reportan al menos el 90 % de los centros activos en las últimas
  12 semanas **y** el total es al menos 0,6 × la mediana de las 4 semanas anteriores.
- **RB-3:** recálculo anual en marzo con las últimas 156 semanas válidas (sin 2020–2021 ni semanas incompletas);
  los umbrales fijados a mano se respetan (#32, #36).
- **Modelo, opción C:** `modelo.especificacion: solo_rezagos`; la variante `con_pronostico` queda disponible.
- **Parámetros, opción a:** YAML versionado + ajustes del administrador en la base (#31).
- «Supera» es estrictamente mayor (#37). El enlace de acuse usa un identificador aleatorio (#34).

## Decisiones abiertas para el equipo

- **#29:** ¿el nivel «atención» también genera notificación, o solo «alerta»?
- **#34:** ¿la página de acuse exige iniciar sesión (recomendado) o basta el enlace?
- **#18 y #24:** ¿se puede desactivar una cuenta sin borrarla (por ejemplo, durante una licencia)?
- **#22:** la tarjeta «Virus circulando (ISP)» del diseño no tiene fuente ni requisito: ¿se agrega o se saca?
- **#38:** dónde se copian los respaldos en producción y quién lo revisa.

## Próximos pasos

### 1. Terminar la base (Mario)

En este orden, cada uno es una parte de `PASOS.md`:

1. **Parte 8 · Corrida semanal:** del panel en la base al pronóstico, la alerta y la dotación guardados.
2. **Parte 9 · Estado de los centros (RF-7):** primer endpoint de lectura y las pantallas conectadas, como
   ejemplo que el resto copia.
3. **Parte 10 · Trabajo en equipo:** CI, `CONTRIBUTING.md` y el tablero de tareas `docs/tareas_equipo.md`.

### 2. Repartir

Después de la parte 10, lo de «Qué falta» se reparte desde `docs/tareas_equipo.md`, cada tarea con sus RF y TC,
los archivos que toca, de qué depende y cuándo se da por terminada.
