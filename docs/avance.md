# Avance del código

Estado al **14 de noviembre de 2026**: primer avance de código funcional, la base del sistema, con la corrida
semanal conectada a la base (parte 8). Este documento
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
| Base de datos | 17 tablas: las entidades de §5.1 y las de apoyo (semanas cargadas, umbrales con historia, ajustes de parámetros, corridas, auditoría, dotación sugerida), con 5 migraciones de Alembic | §5.1 | `sart/db/modelos.py`, `migraciones/` |
| Carga de datos | Catálogo de centros, zonas y estaciones; consultas del DEIS; MP2,5 de SINCA; clima y MP2,5 previsto de Open-Meteo, **desde archivos ya descargados** en `datos/` | RF-1, CI-3 | `python -m sart.catalogo cargar [--prueba]` |
| Corridas | Cada carga queda registrada (inicio, fin, estado, filas); aviso tras fallas seguidas de una fuente | RNF-M-3 | `sart/tareas/corridas.py` |
| Semanas | Semanas epidemiológicas del MINSAL y marca de la semana incompleta | RB-4, TC-01 | `sart/dominio/semanas.py`, `semana_completa.py` |
| Umbrales | p75 y p90 por centro con las últimas 156 semanas válidas, recálculo anual en marzo, respeta los ajustes manuales | RB-3 | `python -m sart.catalogo recalcular-umbrales` |
| Modelo | GLM quasi-Poisson con rezagos (opción C), intervalo de 90 % | RF-2, TC-03, TC-11 | `sart/dominio/modelo.py` |
| Regla de alerta | Normal, atención o ALERTA con el margen k | RF-3, TC-04, TC-17 | `sart/dominio/alerta_demanda.py` |
| MP2,5 | Clasificación en 5 niveles | RB-1, TC-05 | `sart/dominio/mp25.py` |
| Dotación | Erlang C y profesionales mínimos en hora punta | RF-6, TC-07 | `sart/dominio/dotacion.py` |
| Panel desde la base | Panel semanal armado con `consulta_semanal` y `medicion` (MP2,5 con respaldo, clima, rezagos); con `datos/prueba` coincide exacto con el del notebook | RF-2, CI-3, RB-5 | `sart/tareas/panel.py`, `sart/dominio/panel.py` |
| Corrida semanal | Marca RB-4, reentrena el GLM, guarda un pronóstico vigente por centro y semana con su nivel (umbral y k usados), la alerta si no es «normal» (salvo pronóstico desactualizado) y la dotación con sus supuestos; todo en `corrida` y la auditoría | RF-2, RF-3, RF-6, RNF-M-3, RNF-S-4 | `python -m sart.tareas semanal [--fecha AAAA-MM-DD \| --prueba]`, `sart/tareas/semanal.py` |
| Qué se notifica | Solo ALERTA, por centro y semana; repetir la corrida solo notifica si sube el nivel (#29) | RF-3, RF-5 | `sart/db/alertas.py` (`alertas_por_notificar`, para RF-5) |
| Respaldo | Respaldo diario, poda y restauración probada en 59 s | RNF-D-2, TC-14 | `python -m sart.respaldo …` |
| API | `GET /salud`, `POST /auth/sesion`, `GET /auth/yo`, `POST /auth/cerrar-sesion`, `GET /referencias`, `GET /centros/estado` y `GET /centros/{codigo}/estado` (la jefatura solo ve sus centros; un centro ajeno da 403 y queda en la auditoría), `/administracion/usuarios` (solo el administrador) y `/acuse/{token}` | RF-7, RNF-S-2, TC-09 | `sart/api/` · documentación en http://127.0.0.1:8000/docs |
| Web | Inicio de sesión (con el código MFA), encabezado por rol, permisos, rutas con URL; partes fijas de los diseños de Figma para Mi centro, Red de centros y Administración, de 390 px a 1440 px; la escala de MP2,5 viene de la API | RF-7, RNF-U-1, RNF-S-2 | `web/src/` |
| Estado de los centros | Mi centro con el pronóstico, su rango, el nivel, el gráfico de 12 semanas (o tabla), la dotación guardada y el MP2,5 de la zona (RB-5); Red de centros con conteos, filtros, tabla ordenada por nivel y calendario de calor; detalle de un centro en `/red/<código>`; avisos de datos antiguos y de pronóstico desactualizado | RF-7, RF-6, RB-5, RNF-U-1 | `web/src/pantallas/`, `web/src/componentes/DetalleCentro.tsx`, `GraficoConsultas.tsx` |
| Administración de cuentas | Pestaña «Usuarios»: lista de cuentas, alta con el texto de la finalidad y su aceptación, centros de cada jefatura y baja; solo el administrador; todo en la auditoría sin nombre ni correo | RF-9, RF-16, TC-09, TC-16 | `sart/api/administracion.py`, `web/src/pantallas/UsuariosAdministracion.tsx` (T6, pendientes #51) |
| Acuse | Página `/acuse/<token>` con «Confirmar lectura» (abrir no registra nada; una sola vez; exige sesión y solo el destinatario) y la regla de reenvío a las 24 h y escalamiento a las 48 h; el envío espera el correo (T4) | RF-15, RB-2, TC-06 | `sart/api/acuse.py`, `sart/dominio/acuse.py`, `web/src/pantallas/Acuse.tsx` (T5, pendientes #50) |
| Boletín del LLM | Texto para el LLM solo con cifras agregadas, revisión de cifras y niveles, plantilla de respaldo; sin proveedor todavía | RF-8, TC-18 | `sart/dominio/boletin.py` (T12, pendientes #52) |
| Sistema de diseño | Colores, tipografía (Figtree + Noto Sans), formas y componentes de SART; tokens en `App.scss` y tema de MUI con los mismos valores; contrastes AA verificados; niveles con texto e ícono SVG | RNF-U-1 | `DESIGN.md`, `web/src/tema.ts` |

### Cifras verificadas

- Backend: **329 pruebas pasan** con PostgreSQL y `datos/` (sin la base, se saltan las de integración, TC-14 y la
  regresión); unos 4–5 minutos, porque las de la corrida semanal y de RF-7 cargan `datos/prueba` una vez por
  sesión (~35 s). Cobertura de `sart/dominio` + `sart/tareas`: **97 %** (RNF-M-1 pide ≥ 70 %). Ruff: 0 errores.
- Web: **47 pruebas** con Vitest, lint y build sin errores.
- Regresión del backtest 2024–2026 con los datos reales: WAPE 14,9 %; k = 0 → precisión 0,85 y sensibilidad
  0,48; k = 0,4 → 0,73 y 0,66; línea base «semana anterior» → 0,69 y 0,68; cobertura del intervalo 91,1 %.

## Qué falta

La corrida semanal guarda pronósticos, niveles, alertas y dotación (parte 8), y la API y la web ya los muestran
(parte 9). Siguen con sus partes fijas los umbrales e historial de Administración y la exportación (RF-11).

| Falta | IDs |
|---|---|
| Cargar el archivo **real** del DEIS: `cargar_consultas` solo entiende el formato de `datos/prueba` (pendientes #45); hasta entonces la corrida semanal solo se prueba con datos sintéticos | RF-1, TC-02 |
| Descarga automática de DEIS, SINCA y Open-Meteo, con aviso si una fuente falla | RF-1, TC-02 |
| Alerta ambiental diaria a las 07:00 | RF-4, TC-12 |
| Correo de alerta (sale de `alertas_por_notificar`); con él, el reenvío a las 24 h y el escalamiento a las 48 h (la regla `paso_rb2` y «Confirmar lectura» ya están) | RF-5, RF-15, RB-2, TC-06 |
| Administración desde la web: umbrales y parámetros (las cuentas y sus centros ya están) | RF-9 |
| Historial de alertas | RF-10, TC-19 |
| Exportación CSV | RF-11, TC-15 |
| Mapa de centros | RF-12, TC-20 |
| Boletín: elegir el proveedor de LLM (#12) y enviarlo con el correo | RF-8, TC-18 |
| Planificador de horarios (05:00, 06:00, 07:00, 08:00, respaldo 04:30) y Docker Compose con API y web | RNF-P-1, TC-13 |
| Pruebas de carga y de uso | TC-08, TC-10 |

Cada fila está detallada como tarea (T1 a T14) en `docs/tareas_equipo.md`.

## Decisiones ya tomadas

Están anotadas en `docs/pendientes_informe.md` para pasarlas al informe. Las principales:

- **RB-4 (1A):** una semana está completa si reportan al menos el 90 % de los centros activos en las últimas
  12 semanas **y** el total es al menos 0,6 × la mediana de las 4 semanas anteriores.
- **RB-3:** recálculo anual en marzo con las últimas 156 semanas válidas (sin 2020–2021 ni semanas incompletas);
  los umbrales fijados a mano se respetan (#32, #36).
- **Modelo, opción C:** `modelo.especificacion: solo_rezagos`; la variante `con_pronostico` queda disponible.
- **Parámetros, opción a:** YAML versionado + ajustes del administrador en la base (#31).
- «Supera» es estrictamente mayor (#37). El enlace de acuse usa un identificador aleatorio (#34).
- **#29:** «atención» se guarda y se muestra (RF-7), pero solo ALERTA genera correo, por centro y semana; si se
  repite la corrida de la misma semana, solo se notifica si el nivel sube.
- **Dotación y nivel guardados (#39):** cada pronóstico guarda su nivel, el umbral y el k usados, y su dotación
  con los supuestos; un ajuste posterior del administrador no cambia lo ya recomendado.
- **Semana pronosticada y RF-3 E2 (#41):** se pronostica la semana siguiente a la fecha de corte; si no es la
  semana en curso, el pronóstico se guarda sin emitir alertas.

## Decisiones abiertas para el equipo

- **#34:** ¿la página de acuse exige iniciar sesión (recomendado) o basta el enlace? El código usa la recomendada mientras se decide (#50).
- **#18 y #24:** ¿se puede desactivar una cuenta sin borrarla (por ejemplo, durante una licencia)?
- **#22:** la tarjeta «Virus circulando (ISP)» del diseño no tiene fuente ni requisito: ¿se agrega o se saca?
- **#38:** dónde se copian los respaldos en producción y quién lo revisa.
- **#40:** horas de funcionamiento de un SUR (hoy queda sin dotación sugerida).
- **#42:** ¿RF-2 E2 (usar el último valor medido) cubre también el MP2,5 y el clima de la semana anterior?
- **#45:** adaptar la carga de consultas al archivo real del DEIS (trabajo de RF-1).

## Próximos pasos

### 1. Terminar la base (Mario)

En este orden, cada uno es una parte de `PASOS.md`:

1. ~~**Parte 8 · Corrida semanal**~~ (hecha el 14/11).
2. ~~**Parte 9 · Estado de los centros (RF-7)**~~ (hecha el 14/11).
3. ~~**Parte 10 · Trabajo en equipo**~~ (hecha el 14/11): CI en `.github/workflows/ci.yml`, `CONTRIBUTING.md` y
   el tablero `docs/tareas_equipo.md`. El código está en GitHub y la CI corre con cada push a `main` (en verde desde el 15/11). El 16/11 se sumó la
   plantilla de pull request `.github/pull_request_template.md` (qué hace, IDs, cómo se probó, capturas y la lista
   de revisión con las reglas que no se negocian); la mencionan `CONTRIBUTING.md` (paso 6) y el `README.md`.

### 2. Repartir

Lo de «Qué falta» está repartido en 14 tareas en `docs/tareas_equipo.md` (T1 a T14), cada una con sus RF y TC,
los archivos que toca, de qué depende y cuándo se da por terminada. Responsables asignados por sorteo el 14/11
(Benjamín, Daniel, Juan, Joaquín y Jocabed).
