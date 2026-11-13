# Pasos de trabajo para Claude Code

Instrucciones para ejecutar **una parte a la vez**, cuando el usuario diga «haz la parte N».
Antes de cualquier parte, lee `CLAUDE.md`. Al terminar cada parte:
- haz commit en español citando los IDs (RF, RNF, RB, TC) de lo que hiciste;
- actualiza `docs/estado_tc.md` si implementaste o corriste algún TC;
- resume en pocas líneas qué hiciste y qué quedó pendiente, y espera la siguiente instrucción.

Si algo de lo que te pido contradice el informe o la especificación, no lo hagas en silencio:
anótalo en `docs/pendientes_informe.md` y pregúntame.

---

## Parte 1 · Ordenar los archivos

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

- `git init` en esta carpeta.
- `git status` y confirma que **no** aparecen: `datos/crudos`, `datos/procesados`, `referencia/` ni archivos `.env`.
  Sí debe aparecer `datos/prueba/`.
- Primer commit: «Estructura inicial de SART: especificación, parámetros e instrucciones».

## Parte 3 · Entender el proyecto

- Lee `CLAUDE.md`, todo `docs/` y `config/parametros.yaml`, y revisa por encima el notebook 5.
- Resume en unas 10 líneas qué entendiste.
- Lista qué información te falta o qué ves contradictorio.
- **No escribas código en esta parte.**

## Parte 4 · Planificar el backend

Propón, sin crear archivos todavía:
- la estructura de `backend/`: `pyproject.toml` y los paquetes `sart/api`, `sart/tareas`, `sart/dominio` y `sart/db`;
- las dependencias (FastAPI, SQLAlchemy 2, Alembic, pandas, statsmodels, scipy, argon2, pytest, pytest-cov, ruff);
- el `docker-compose.yml` con PostgreSQL 16, con las credenciales en `.env` y un `.env.example`;
- qué funciones del notebook van a qué módulo.

Espera mi visto bueno antes de crear archivos.

## Parte 5 · Migrar la lógica del notebook (pruebas primero)

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

- Migra el ajuste del GLM quasi-Poisson y la predicción a `sart/dominio`.
- Agrega una prueba de regresión del backtest 2024–2026 con los datos reales de `datos/`. Debe reproducir:
  - WAPE 14,9 %;
  - con k = 0: precisión 0,85 y sensibilidad 0,48;
  - con k = 0,4: precisión 0,73 y sensibilidad 0,66;
  - línea base «semana anterior»: precisión 0,69 y sensibilidad 0,68.
- Si no da igual, explícame la diferencia antes de cambiar nada.
- Marca la prueba para que se salte cuando `datos/` no esté (en CI solo hay `datos/prueba/`).

## Parte 7 · Frontend

Arma `web/` a partir de `referencia/ing-software2/main`, siguiendo `docs/plan_reutilizacion_ing-software2.md`:
- conserva Vite, TypeScript, MUI, axios, el contexto de autenticación y el patrón de permisos;
- cambia los roles a Jefatura, Subdirector y Administrador;
- agrega react-router (el correo de RF-15 necesita un enlace con URL a la página de acuse);
- crea la pantalla de estado del centro (RF-7): nivel con texto e ícono, no solo color (RNF-U-1);
- elimina las pantallas de incidentes, intervenciones y estudiantes;
- copia la licencia como `web/LICENSE-ing-software2`;
- no copies ningún `.env` de la referencia.
