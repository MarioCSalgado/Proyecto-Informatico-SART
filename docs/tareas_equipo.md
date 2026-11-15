# Tablero de tareas del equipo

Lo que falta para la entrega, a partir de «Qué falta» de `docs/avance.md` (14/11/2026). Cada tarea se hace en su
rama y entra por PR revisado por un compañero (ver `CONTRIBUTING.md`). **Mario asigna la columna «Responsable».**
Al terminar una tarea, se marca aquí y se actualiza `docs/estado_tc.md` si cerró un TC.

Tamaño: **S** ≈ 1 día · **M** ≈ 2–4 días · **L** ≈ una semana. Perfil: back (Python, API, base), front (React),
datos (fuentes y modelo), docs.

## Resumen

| # | Tarea | IDs | Depende de | Tamaño | Perfil | Responsable | Estado |
|---|---|---|---|---|---|---|---|
| T1 | Cargar el archivo real del DEIS | RF-1, TC-02 · #45 | — | M | datos, back | | Pendiente |
| T2 | Descarga automática de DEIS, SINCA y Open-Meteo | RF-1, TC-02, RNF-M-3 | T1 | L | datos, back | | Pendiente |
| T3 | Alerta ambiental diaria (07:00) | RF-4, TC-12 | — | M | back | | Pendiente |
| T4 | Correo de alerta | RF-5, TC-06 | — | M | back | | Pendiente |
| T5 | «Confirmar lectura», reenvío y escalamiento | RF-15, RB-2, TC-06 · #34 | T4 | L | back, front | | Pendiente |
| T6 | Administración de cuentas y centros desde la web | RF-9, RF-16, TC-09, TC-16 | — | L | back, front | | Pendiente |
| T7 | Umbrales y parámetros desde la web | RF-9, RB-3, TC-17 | T6 | M | back, front | | Pendiente |
| T8 | Historial de alertas | RF-10, TC-19 | — | M | back, front | | Pendiente |
| T9 | Exportación CSV | RF-11, TC-15 | — | S | back, front | | Pendiente |
| T10 | Mapa de centros | RF-12, TC-20 | — | M | front | | Pendiente |
| T11 | Planificador de horarios y Docker Compose completo | RNF-P-1, RNF-P-2, TC-13 | T2, T3, T4 | M | back | | Pendiente |
| T12 | Boletín redactado con el LLM | RF-8, TC-18 | T4 | M | back | | Pendiente |
| T13 | Pruebas de carga y de uso | TC-08, TC-10, RNF-R-1, RNF-R-2 | T6 | M | docs, front | | Pendiente |
| T14 | Cerrar las decisiones abiertas con el equipo | #18, #22, #24, #34, #38, #40, #42 | — | S | docs | | Pendiente |

## Detalle

### T1 · Cargar el archivo real del DEIS (RF-1, TC-02 · pendientes #45)
- **Qué hacer:** `cargar_consultas` solo entiende el formato de `datos/prueba` (`IdEstablecimiento`, `Menores_1`…,
  glosas como «Infección respiratoria aguda alta»). El archivo real usa `EstablecimientoCodigo`, `NumTotal`,
  `NumMenor1Anio`…, glosas como «IRA Alta (J00-J06)», y trae subtotales («- Por covid-19…», «- Causas sistema
  respiratorio») y totales que **no** deben sumarse dos veces. Aceptar los dos formatos (o convertir el real) y
  aplicar el calendario del MINSAL a las semanas que cruzan el año (#11).
- **Archivos:** `backend/sart/tareas/carga.py`, `backend/sart/dominio/catalogo.py`, `config/parametros.yaml`
  (`ingesta.causas`), `backend/tests/test_carga_*.py`.
- **Terminado cuando:** el panel armado desde la base con los datos reales coincide con
  `datos/procesados/panel_semanal.parquet` (como `test_rf2_panel_desde_la_base.py` con los de prueba), y
  `python -m sart.tareas semanal --fecha 2026-10-05` da pronóstico a los 31 centros con historia (Gherkin de RF-2).

### T2 · Descarga automática (RF-1, TC-02, RNF-M-3)
- **Qué hacer:** bajar cada día el archivo del DEIS (datos.gob.cl), el MP2,5 de SINCA y el clima y el pronóstico
  de MP2,5 de Open-Meteo, guardar la copia cruda, cargar con las funciones existentes y registrar la corrida; con
  `ingesta.reintentos_fuente` reintentos y aviso si una fuente falla dos veces seguidas (ya existe
  `hay_que_avisar`). Las URL están en el notebook 5.
- **Archivos:** nuevo `backend/sart/tareas/descarga.py`, `backend/sart/tareas/corridas.py`, `config/parametros.yaml`.
- **Depende de:** T1. **Terminado cuando:** TC-02 pasa con las descargas simuladas (sin red en la CI) y una corrida
  real deja las cuatro fuentes cargadas.

### T3 · Alerta ambiental diaria (RF-4, TC-12)
- **Qué hacer:** a las 07:00, promedio diario pronosticado de MP2,5 de los próximos 5 días por zona, clasificado
  con `clasificar_mp25` (RB-1, ya probado en TC-05); guardar una `alerta` ambiental por día sobre la norma, con la
  aclaración de que no es una declaración oficial (E2), y «datos insuficientes» si no hay pronóstico (E1, RB-5).
- **Archivos:** nuevo `backend/sart/tareas/ambiental.py`, `backend/sart/dominio/mp25.py`, pruebas `test_tc12_*.py`.
- **Terminado cuando:** pasa el Gherkin de RF-4 (95 µg/m³ el sábado → nivel «Alerta») y TC-12.

### T4 · Correo de alerta (RF-5, TC-06)
- **Qué hacer:** tomar `alertas_por_notificar` (ya decide qué se envía, #29), armar un correo por usuario solo con
  sus centros, enviar antes de las 08:00 con `notificaciones.reintentos_envio` reintentos y registrar la
  `notificacion` (estado y fecha; «fallida» si no se pudo). Servidor de correo en `.env`, nunca en el código.
  El correo enlaza a `/acuse/<token_acuse>`.
- **Archivos:** nuevo `backend/sart/tareas/notificaciones.py`, `backend/sart/db/alertas.py`, `.env.example`.
- **Terminado cuando:** el Gherkin de RF-5 pasa (un correo y no un segundo si el proceso se repite) con un servidor
  SMTP de prueba, y ningún correo lleva datos de pacientes.

### T5 · «Confirmar lectura», reenvío y escalamiento (RF-15, RB-2, TC-06 · #34)
- **Qué hacer:** página `/acuse/<token>` con el botón «Confirmar lectura» (el acuse no se registra al abrir el
  enlace), ruta de la API que lo registra con fecha, y tarea que reenvía a las 24 h sin acuse y escala al
  Subdirector a las 48 h (`notificaciones.reenvio_horas` y `escalamiento_horas`). Todo en la auditoría.
- **Depende de:** T4 y de decidir #34 (¿exige iniciar sesión?). **Terminado cuando:** TC-06 pasa completo.

### T6 · Administración de cuentas y centros desde la web (RF-9, RF-16, TC-09, TC-16)
- **Qué hacer:** API para listar, crear (con la aceptación de la finalidad), dar de baja y asignar centros, solo
  para el administrador con MFA; conectar la pestaña «Usuarios» de Administración. La lógica ya existe en
  `sart/db/cuentas.py` (hoy se usa desde `python -m sart.cuentas`).
- **Archivos:** nuevo `backend/sart/api/administracion.py`, `web/src/pantallas/Administracion.tsx`, servicio nuevo.
- **Terminado cuando:** TC-16 pasa también en la pantalla y TC-09 cubre las rutas de RF-9 (0 accesos indebidos).

### T7 · Umbrales y parámetros desde la web (RF-9, RB-3, TC-17)
- **Qué hacer:** conectar las pestañas «Umbrales» e «Historial»: `fijar_umbral_manual` y `ajustar_parametro` ya
  existen y auditan; falta la API y la pantalla, con el motivo obligatorio. Solo las claves de
  `administracion.parametros_editables`.
- **Depende de:** T6. **Terminado cuando:** cambiar k desde la web cambia el nivel en la corrida siguiente (TC-17)
  y el cambio aparece en el historial.

### T8 · Historial de alertas (RF-10, TC-19)
- **Qué hacer:** API y pantalla con las alertas pasadas de los centros del usuario, con nivel, semana, pronóstico,
  dotación y estado del acuse (lo guardado, no recalculado: #39). Filtros por centro y fecha.
- **Terminado cuando:** pasa TC-19.

### T9 · Exportación CSV (RF-11, TC-15)
- **Qué hacer:** activar «Descargar CSV» (Mi centro) y «Exportar red CSV» (Red de centros) con los mismos datos de
  `GET /centros/estado`, respetando lo que cada rol puede ver. Sin datos de pacientes; citar la fuente (CC BY-NC).
- **Terminado cuando:** pasa TC-15.

### T10 · Mapa de centros (RF-12, TC-20)
- **Qué hacer:** mapa del Gran Concepción con cada centro coloreado **y rotulado** por nivel (RNF-U-1), a partir de
  la latitud y longitud de `centro_salud` (agregarlas a la respuesta de RF-7). Elegir la librería con el equipo.
- **Terminado cuando:** pasa TC-20 y se ve bien a 390 px.

### T11 · Planificador y Docker Compose completo (RNF-P-1, RNF-P-2, TC-13)
- **Qué hacer:** correr a su hora el respaldo (04:30), la ingesta (05:00), el pronóstico (lunes 06:00), la alerta
  ambiental (07:00) y el boletín (antes de 08:00), con los horarios de `config/parametros.yaml`; agregar la API y
  la web a `docker-compose.yml`, dentro de 2 vCPU y 4 GB.
- **Depende de:** T2, T3 y T4. **Terminado cuando:** `docker compose up` levanta todo y TC-13 pasa.

### T12 · Boletín redactado con el LLM (RF-8, TC-18)
- **Qué hacer:** resumen del lunes redactado por el LLM **solo con cifras agregadas**, sin nombres ni correos, y
  sin poder cambiar un nivel (se comprueba que las cifras del texto coinciden con las de la base).
- **Depende de:** T4. **Terminado cuando:** pasa TC-18. Es posterior al MVP.

### T13 · Pruebas de carga y de uso (TC-08, TC-10)
- **Qué hacer:** TC-08 (70 usuarios en 5 minutos, p95 ≤ 2 s; Lighthouse móvil con 4G) y TC-10 (3 a 5 personas,
  ≥ 80 % llega en 4 clics). Hoy la jefatura llega a su pronóstico en 0 clics (Mi centro es su inicio).
- **Depende de:** T6 (cuentas para los participantes). **Terminado cuando:** los dos TC con su informe en `docs/`.

### T14 · Decisiones abiertas (docs)
- **Qué hacer:** cerrar con el equipo y pasar al informe: #34 (acuse con sesión), #18 y #24 (desactivar cuentas),
  #22 (tarjeta de virus del ISP), #38 (copia de los respaldos), #40 (horas de un SUR), #42 (RF-2 E2 para los
  rezagos ambientales). Ver `docs/pendientes_informe.md`.
- **Terminado cuando:** cada una tiene decisión escrita en `pendientes_informe.md` y su sección del informe.
