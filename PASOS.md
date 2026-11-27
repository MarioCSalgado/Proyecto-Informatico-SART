# Pasos de trabajo para Claude Code

Instrucciones para ejecutar **una parte a la vez**, cuando el usuario diga «haz la parte N».
Antes de cualquier parte, lee `CLAUDE.md`. Al terminar cada parte:
- haz commit en español citando los IDs (RF, RNF, RB, TC) de lo que hiciste;
- actualiza `docs/estado_tc.md` si implementaste o corriste algún TC;
- resume en pocas líneas qué hiciste y qué quedó pendiente, y espera la siguiente instrucción.

Si algo de lo que te pido contradice el informe o la especificación, no lo hagas en silencio:
anótalo en `docs/pendientes_informe.md` y pregúntame.

## Estado (14/11/2026)

Partes 1 a 10 **hechas**: el resumen de lo que quedó funcionando está en `docs/avance.md`. La base está
terminada; el trabajo sigue repartido en el equipo con `docs/tareas_equipo.md`.

### Integración RF-4/RF-5 · 27/11/2026

Primera conexión del comando ambiental con el envío de T4, probada con transportador simulado y SQLite
aislada. Recupera las alertas que la misma corrida vuelve a evaluar sin duplicar los envíos ya registrados.
No cambia la regla de aumento de nivel ni define antigüedad de pendientes. Alcance y pendientes en
`docs/avance.md`; pruebas en `backend/tests/test_rf4_rf5_integracion.py`.

Segunda etapa: el correo distingue pronóstico de Open-Meteo y observación SINCA de respaldo, e incluye
la aclaración no oficial con texto controlado. Pruebas de contenido ambiental y regresión del cuerpo de
demanda con transportadores simulados; no supone validación completa de RF-4/RF-5 ni de TC-12.

Tercera etapa: seis casos PostgreSQL aprobados reutilizando `crear_base_temporal`, con destino verificado
antes de migrar o insertar y SMTP bloqueado. Cubren generación/envío, repetición y recuperación dentro de
la reevaluación actual, con pronóstico y SINCA. No hubo cambios de producción; la validación real de TC-12
sigue pendiente.

SMTP local preparado con Mailpit y una base nueva aislada: cuatro correos (dos destinatarios por ejemplo),
SINCA de respaldo con 85 µg/m³ el 26/11 y pronóstico con 95 µg/m³ el 28/11. Se verificaron contenido y
repetición sin duplicados por API, con backend 8002 y frontend 5175 separados de los servicios previos.
**La revisión visual personal está pendiente y no se confirmó ningún acuse.** Esta evidencia sintética no
cierra TC-12. Límites y coordinación con las nuevas ramas remotas de RF-4 en `docs/avance.md`.

Revisión final: 23 casos adicionales sin cambios de producción; suite backend completa con 545 aprobadas,
9 omitidas y 22 de integración PostgreSQL aprobadas. Cobertura de dominio/tareas 93,3 %, Ruff y diff sin
errores. El archivo ambiental suma 42 casos (10 PostgreSQL). No hay credenciales, tokens ni datos de la
demo incorporados. La revisión visual personal y la validación real de TC-12 siguen pendientes.

### Seguimiento T13 · 16/11/2026

TC-08 tiene una medición de carga preliminar satisfactoria en `GET /centros/estado` (70 usuarios virtuales,
10,70 solicitudes/s, p95 1.159 ms). No se cierra: falta probar el boletín y Lighthouse móvil con 4G. TC-10 sigue
pendiente de realizar con 3–5 participantes. La interfaz de T6 no es requisito: las cuentas de prueba se pueden
preparar por CLI. Ver `docs/tareas_equipo.md` y `docs/estado_tc.md`.

---

## Parte 1 · Ordenar los archivos

> **Hecha (13/11).**

La carpeta de arriba (`../`, «Proyecto Informatico») tiene material viejo que hay que ordenar
según `../COMO_ARMAR_LA_CARPETA.md`, pasos 2 y 3. **Muéstrame el plan de movimientos antes de mover nada.**

- `../codigo/analisis_informatico5.ipynb` → `notebooks/`
- `../codigo/datos/crudos` y `../codigo/datos/procesados` → `datos/crudos` y `datos/procesados`
- `../codigo/datos_prueba/*` → `datos/prueba/`
- Notebooks 1 a 4, `resultados_prueba/` y los PNG sueltos de `../codigo/` → `../archivo/`
- `../codigo/resultados/` → `../presentaciones/figuras/`
- `../PresentacionData/`: el .docx → `../informe/`; los PNG → `../presentaciones/`
- Verifica que `referencia/ing-software2/` exista y **no** tenga carpeta `.git` (si la tiene, avísame antes de borrarla).

Al final, las carpetas `../codigo/` y `../PresentacionData/` deben quedar vacías. No las borres: dime y lo hago yo.

## Parte 2 · Iniciar el repositorio

> **Hecha (13/11). Repositorio privado en GitHub: `Proyecto-Informatico-SART`.**

- `git init` en esta carpeta.
- `git status` y confirma que **no** aparecen: `datos/crudos`, `datos/procesados`, `referencia/` ni archivos `.env`.
  Sí debe aparecer `datos/prueba/`.
- Primer commit: «Estructura inicial de SART: especificación, parámetros e instrucciones».

## Parte 3 · Entender el proyecto

> **Hecha (13/11). Lo contradictorio quedó en `docs/pendientes_informe.md`.**

- Lee `CLAUDE.md`, todo `docs/` y `config/parametros.yaml`, y revisa por encima el notebook 5.
- Resume en unas 10 líneas qué entendiste.
- Lista qué información te falta o qué ves contradictorio.
- **No escribas código en esta parte.**

## Parte 4 · Planificar el backend

> **Hecha (13/11), y además: cuentas, sesión con MFA, modelo de datos completo y carga (ver `docs/avance.md`).**

Propón, sin crear archivos todavía:
- la estructura de `backend/`: `pyproject.toml` y los paquetes `sart/api`, `sart/tareas`, `sart/dominio` y `sart/db`;
- las dependencias (FastAPI, SQLAlchemy 2, Alembic, pandas, statsmodels, scipy, argon2, pytest, pytest-cov, ruff);
- el `docker-compose.yml` con PostgreSQL 16, con las credenciales en `.env` y un `.env.example`;
- qué funciones del notebook van a qué módulo.

Espera mi visto bueno antes de crear archivos.

## Parte 5 · Migrar la lógica del notebook (pruebas primero)

> **Hecha (14/11): TC-01, TC-05, TC-07 y TC-17; RB-4 con el criterio 1A y RB-3 anual.**

Lleva a `sart/dominio`, leyendo todos los valores desde `config/parametros.yaml`:
- semanas epidemiológicas (domingo a sábado, criterio del MINSAL) y la detección de la semana incompleta (RB-4);
- umbrales por centro (RB-3);
- regla de alerta con margen: ALERTA si pronóstico + k·(límite superior − pronóstico)/1,645 supera el p90 (RF-3);
- clasificación de MP2,5 en 5 niveles (RB-1);
- Erlang C y dotación mínima (RF-6, CI-2).

Orden de trabajo:
1. Escribe primero las pruebas TC-05, TC-07 y TC-17 a partir de los Gherkin de `docs/especificacion/`.
2. Después escribe el código que las hace pasar.
3. Ojo: el notebook usa 168 h para todos los centros; la especificación dice 123 h en SAPU y SAR y 168 h en hospitales. Sigue la especificación. Las horas del SUR no están definidas: déjalo como error claro si aparece un SUR.

## Parte 6 · Prueba de regresión del modelo

> **Hecha (14/11): reproduce todas las cifras con el panel del notebook (`datos/procesados/panel_semanal.parquet`). Opción C del modelo. Quedan pendientes las rutas del notebook (ver la parte 8).**

- Migra el ajuste del GLM quasi-Poisson y la predicción a `sart/dominio`.
- Agrega una prueba de regresión del backtest 2024–2026 con los datos reales de `datos/`. Debe reproducir:
  - WAPE 14,9 %;
  - con k = 0: precisión 0,85 y sensibilidad 0,48;
  - con k = 0,4: precisión 0,73 y sensibilidad 0,66;
  - línea base «semana anterior»: precisión 0,69 y sensibilidad 0,68.
- Si no da igual, explícame la diferencia antes de cambiar nada.
- Marca la prueba para que se salte cuando `datos/` no esté (en CI solo hay `datos/prueba/`).

## Parte 7 · Frontend

> **Hecha (13 y 14/11): partes fijas de los diseños de Figma; nombres en español (ver `docs/plan_reutilizacion_ing-software2.md`). Las pantallas aún no muestran datos (parte 9).**

Arma `web/` a partir de `referencia/ing-software2/main`, siguiendo `docs/plan_reutilizacion_ing-software2.md`:
- conserva Vite, TypeScript, MUI, axios, el contexto de autenticación y el patrón de permisos;
- cambia los roles a Jefatura, Subdirector y Administrador;
- agrega react-router (el correo de RF-15 necesita un enlace con URL a la página de acuse);
- crea la pantalla de estado del centro (RF-7): nivel con texto e ícono, no solo color (RNF-U-1);
- elimina las pantallas de incidentes, intervenciones y estudiantes;
- copia la licencia como `web/LICENSE-ing-software2`;
- no copies ningún `.env` de la referencia.

## Parte 8 · Corrida semanal (RF-2, RF-3, RF-6)

> **Hecha (14/11).** `python -m sart.tareas semanal [--fecha AAAA-MM-DD | --prueba]`. Decisiones: la dotación
> y el nivel se guardan con lo usado (#39); #29 cerrada (solo ALERTA notifica, por centro y semana); RF-3 E2
> definido (#41). Queda para RF-1: cargar el archivo real del DEIS (#45). Ver `docs/avance.md`.

Conecta la lógica de `sart/dominio` con la base: hoy el modelo solo corre sobre el parquet del notebook y no se
guarda ningún pronóstico ni alerta. **Muéstrame el plan antes de escribir código** (en particular, las dos
decisiones de abajo).

- **Panel desde la base:** arma el panel semanal (consultas por centro y semana + clima y MP2,5 agregados a la
  semana) leyendo `consulta_semanal` y `medicion`, con las mismas columnas que espera `sart/dominio/modelo.py`.
  Prueba de regresión: con `datos/prueba`, el panel armado desde la base debe coincidir con
  `datos/prueba/procesados/panel_semanal.parquet`.
- **Tarea** `sart/tareas/semanal.py` y comando `python -m sart.tareas semanal` (con `--prueba` para los datos de
  prueba), registrada en `corrida` (RNF-M-3) y leyendo `parametros_vigentes(sesion)` (RNF-M-4):
  1. `marcar_semanas` (RB-4) → la última semana completa es la `fecha_corte`;
  2. ajusta el modelo y pronostica la semana en curso de **cada centro con historia** (criterio de RF-2), con su
     intervalo de 90 %;
  3. guarda un `pronostico` vigente por centro y semana; si se vuelve a correr, el anterior queda `vigente = false`;
  4. clasifica con el `umbral_centro` vigente y el margen k (RF-3) y guarda una `alerta` de demanda cuando no es
     «normal»;
  5. dotación de hora punta con `recomendar_dotacion` (RF-6).
- **Decisiones que necesito antes:**
  - la dotación ¿se guarda (hoy no hay columna) o se calcula al leer, ya que es una función pura del pronóstico?;
  - #29: ¿«atención» genera alerta y notificación, o solo «alerta»? (hoy se guardan las dos).
- **Pruebas** (primero): todo centro con historia tiene pronóstico; correr dos veces deja uno solo vigente; un
  pronóstico con margen sobre el p90 queda ALERTA; la semana incompleta no se usa (RB-4).
- De paso: corrige las rutas del notebook 5 (`notebooks/analisis_informatico5.ipynb` todavía busca `datos/` y
  `datos_prueba/` junto a sí mismo; ahora están en `../datos/crudos`, `../datos/procesados` y `../datos/prueba/`).

## Parte 9 · Estado de los centros en la API y la web (RF-7)

> **Hecha (14/11).** `GET /centros/estado` y `/centros/{codigo}/estado` (TC-09), Mi centro y Red de centros con
> datos, y el detalle `/red/<código>`. Decisiones en `docs/pendientes_informe.md` #46 a #48. La jefatura llega
> a su pronóstico en 0 clics: Mi centro es su pantalla de inicio.

El primer endpoint de lectura, hecho con cuidado para que sirva de ejemplo al resto del equipo.

- `GET /centros/estado`: por centro, el nivel de la semana, el pronóstico con su intervalo, los umbrales, la
  dotación sugerida y el MP2,5 de su zona. La jefatura recibe **solo sus centros asignados**; el Subdirector y el
  administrador, todos (RNF-S-2). Sin datos de pacientes (RNF-S-5).
- Prueba de acceso por rol (TC-09): 0 accesos indebidos, incluida una jefatura que pide un centro ajeno.
- En la web: servicio en `web/src/servicios/`, y **Mi centro** y **Red de centros** muestran los datos reales,
  con el nivel siempre con texto o ícono (RNF-U-1) y estados de carga y vacío.
- Revisa que el estado del centro quede a 4 clics o menos (RF-7).

## Parte 10 · Preparar el trabajo en equipo

> **Hecha (14/11).** `.github/workflows/ci.yml`, `CONTRIBUTING.md` y `docs/tareas_equipo.md` (T1 a T14). El código ya
> está en GitHub y la CI pasa. Pendiente fuera del repositorio, con el visto bueno de Mario: proteger `main` y crear issues. El 16/11 se agregó
> la plantilla de PR `.github/pull_request_template.md`, citada en `CONTRIBUTING.md` y el `README.md`.

- **CI en GitHub Actions** (`.github/workflows/`): backend con ruff, pytest con un servicio de PostgreSQL 16 y
  cobertura ≥ 70 % en `sart/dominio` y `sart/tareas` (RNF-M-1, RNF-M-2); web con lint, build y Vitest. Es parte
  de TC-13.
- **`CONTRIBUTING.md`:** instalación en 10 minutos, una rama por tarea (`rf-5/correo-alerta`), PR revisado por
  un compañero antes de entrar a `main`, commits en español con IDs, cómo escribir la prueba de un TC, y las
  reglas que no se negocian de `CLAUDE.md`.
- **`docs/tareas_equipo.md`:** el tablero con las tareas de «Qué falta» de `docs/avance.md`. Por tarea: RF y TC,
  qué hacer, archivos que toca, de qué depende, criterio de terminado, tamaño y perfil (back, front, datos o
  docs). La columna «Responsable» la llena Mario.
- Al final, actualiza `docs/avance.md`.
- Lo que se hace fuera del repositorio (subir con `git push`, proteger la rama `main` en GitHub, crear issues)
  **pregúntamelo antes**.