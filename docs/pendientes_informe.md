# Diferencias entre el código y el informe

Lista viva. Cuando el código deba apartarse del informe, o el informe tenga una contradicción, se anota aquí
para que el dueño de la sección la corrija.

## Contradicciones en el informe (al 13/11)

| Sección (dueño) | Problema | Lo que sigue el código |
|---|---|---|
| §6 RB-3 (Daniel) | No incluye el margen k de la regla de alerta | RF-3 y RNF-Q-2: pronóstico + k·desviación > p90 |
| §6 RB-1 (Daniel) | Falta el nivel "sobre la norma" (51–79 µg/m³) | RF-4 y TC-05: 5 niveles |
| §6 RB-2 (Daniel) | Dice que la implementa solo RF-5 | RF-5 (envío) y RF-15 (acuse y escalamiento) |
| §2.7 CI-1 (Daniel) | Describe la Binomial Negativa y MAE/RMSE | GLM quasi-Poisson y WAPE (notebook 5) |
| §2.7 CI-2 (Daniel) | No dice 15 min, factor 1,6 ni 123/168 h | `config/parametros.yaml` |
| §9.1 (Benjamín) | RF-9 en Should; faltan RF-15 y RF-16 en Must | Must según §3.1 |
| §5.1 (Jocabed) | Revisar que Pronóstico tenga límites del intervalo y Notificación el estado "escalada" | Versión de `05_datos.md` |
| §8 (Nacho) | No registra la decisión ALT-2 ni la matriz de 6 criterios | ALT-2 |
| §10 (sin dueño) | Dice TC-01 a TC-10 | TC-01 a TC-20 |

## Diferencias entre el notebook y la especificación

| Tema | Notebook 5 | Especificación | Acción |
|---|---|---|---|
| Horas de funcionamiento | 168 h para todos los centros | 123 h en SAPU y SAR, 168 h en hospitales (RF-6, TC-07) | Usar la especificación |
| Horas del SUR | — | No definidas | Preguntar al equipo |
| k = 0,4 | Elegido y evaluado con 2024–2026 | Recalibrar con 2024 y probar en 2025–2026 (RNF-Q-2) | Hacerlo antes de la E3 |
| Cobertura del intervalo | ~~No reportada~~ 91,1 % en el backtest 2024–2026 (89,1 %, 93,5 % y 90,6 % por año) | RNF-Q-3: 85–95 % | Cumple; agregar la cifra al informe |

## Revisión de la especificación contra el notebook 5 (13/11)

Salió de leer `docs/especificacion/`, `config/parametros.yaml` y el notebook 5 completo. Se ordena por impacto.
«Bloquea» indica qué paso de `PASOS.md` no conviene empezar sin la decisión.

### Decisiones pendientes

| # | Sección (dueño) | Problema y por qué importa | Qué hay que decidir o cambiar en el informe | Bloquea |
|---|---|---|---|---|
| 1 | §2.7 CI-1 (Daniel), §4.8 RNF-Q-1 y Q-2 | **Decidido el 14/11 (opción C):** el código tiene las dos especificaciones (`sart/dominio/modelo.py`) y `modelo.especificacion` elige; el sistema parte con `solo_rezagos`, la de las cifras de referencia, que la prueba de regresión reproduce exactamente con los datos reales (WAPE 14,9 %; k = 0: 0,85/0,48; k = 0,4: 0,73/0,66; línea base 0,69/0,68). Se cambia a `con_pronostico` cuando se valide con pronósticos reales de MP2,5, recalculando k y las cifras. | Ajustar CI-1 para que describa `solo_rezagos` como el modelo vigente y `con_pronostico` como alternativa en validación. | — |
| 2 | §3.2 RF-2, §6 RB-4 (Daniel) | La descripción de RF-2 y RB-4 dice que se pronostica «la semana en curso», pero el Gherkin de RF-2 y el notebook pronostican la semana siguiente a la última semana completa (27/09 → SE 40). Si el MINSAL publica con más de una semana de atraso, el boletín del lunes pronostica una semana ya pasada. El atraso de publicación no se ha verificado. | Medir el atraso real de publicación del DEIS y redactar RF-2 y RB-4 con lo que se pronostica de verdad (horizonte en semanas). Si el horizonte es mayor que 1, el modelo debe pronosticar a más de una semana. | Parte 5 |
| 3 | §3.2 RF-1, §6 RB-4 (Daniel) | **Decidido el 14/11 (opción 1A):** una semana reciente está completa si reportan al menos el **90 %** de los centros activos de las últimas 12 semanas **y** su total no cae bajo 0,6 × la mediana de las 4 semanas previas (`ingesta` en parametros.yaml). Se usa el 90 % y no el 80 %: con 80 %, 29 de 33 centros (88 %) contaría como completa y el Gherkin de RF-1 fallaría. | Escribir en RB-4 los dos criterios con sus valores (90 %, 12 semanas, 0,6, 4 semanas). Queda pendiente si la marca debe ser también por centro. | — |
| 4 | §3.2 RF-7 | El Gherkin dice 357 consultas con intervalo 263–450. El notebook da 357,55 (264,08–451,02); redondeando son 358 (264–451). | Definir la regla de redondeo para mostrar cifras (redondear o truncar) y ajustar el Gherkin. | Parte 7 |
| 5 | §3.2 RF-6, §2.7 CI-2 (Daniel), §5.1 | El notebook tomó el tipo de centro de `TipoPertenenciaEstabGlosa` (a qué red pertenece), no de `TipoEstablecimientoGlosa`. Sin el tipo correcto no se puede elegir 123 h o 168 h. El registro trae además `ClasificacionTipoSapu`: si hay SAPU de horario corto, 123 h no vale para todos. En el registro de las 10 comunas no aparece ningún SUR, así que el SUR sin horas no bloquea por ahora. | Confirmar la columna de tipo y si las horas dependen de la clasificación del SAPU. Si dependen, agregar esa distinción en CI-2, RF-6 y `parametros.yaml`. | Parte 5 |
| 6 | §6 RB-3 (Daniel) | **Decidido el 14/11:** los umbrales se recalculan una vez al año con las **últimas 156 semanas válidas** de cada centro hasta la fecha del recálculo (sin 2020-2021 ni semanas incompletas), no con años calendario. Respeta el recálculo anual y usa los datos más recientes. | Cambiar en RB-3 «últimos tres años con datos válidos» por «las últimas 156 semanas válidas al momento del recálculo anual». | — |
| 7 | §6 RB-3 (Daniel), §3.2 RF-3 | RB-3 no dice si el nivel «atención» (p75) usa el margen k. RF-3 dice que no lo usa. | Dejarlo explícito en RB-3: el margen se aplica solo al p90. | — (14/11: el código ya aplica el margen solo al p90, como dice RF-3) |
| 8 | §6 RB-1 (Daniel), TC-05 | No dice cómo tratar los decimales en los bordes (¿50,4 µg/m³ es Normal o «sobre la norma»?) ni si el promedio de 24 h se redondea antes de clasificar, como hace la norma. | Definir el redondeo del promedio diario antes de clasificar. | Parte 5 |
| 9 | §4.6 RNF-M-4 | Varios supuestos del notebook no están en `parametros.yaml`: año de inicio 2014, factor 0,6 de la mediana, ventana de 12 semanas para contar los centros activos, catálogo de estaciones con su asignación a cada comuna y las coordenadas del punto de Open-Meteo. | Agregarlos al YAML al migrar la lógica (no requiere cambiar el informe). | Parte 5 |

### Información que falta

| # | Sección (dueño) | Qué falta | Efecto |
|---|---|---|---|
| 10 | §2.7 CI-3 (Daniel), §6 RB-5 | Faltan los códigos SINCA de 5 de las 6 estaciones (solo Kingston College tiene datos reales). Hoy el 50 % de las semanas del panel usa la estación de respaldo. La asignación con Haversine y Voronoi se prometió para la E2 y no está en el notebook (la asignación sigue siendo manual por comuna). | La marca «de respaldo» de RB-5 será la regla y no la excepción. Hay que actualizar CI-3 o implementar Voronoi. |
| 11 | §3.2 RF-1, TC-01 | ~~El DEIS escribe el año calendario en las semanas que cruzan el año nuevo; el notebook lo corrige con `epiweeks`.~~ **Resuelto (14/11):** calendario del MINSAL reimplementado en `sart/dominio/semanas.py`, sin dependencia nueva, y contrastado con las 666 semanas del panel de prueba que armó `epiweeks`. | Falta aplicarlo en la ingesta con el archivo real del DEIS (ver cómo rotula). |
| 12 | §5.2, §9 | Faltan los proveedores de LLM (RF-8), de correo (RF-5) y de nube. | No bloquea el dominio; sí las tareas de notificación y el despliegue. |
| 13 | Anexo A | Siguen sin validar en entrevistas los supuestos de dotación (15 min, factor 1,6, horas por tipo) y el atraso de publicación del MINSAL (ver #2). | RF-6 E1: mostrar los supuestos como «por validar». |

## Autenticación y cuentas (13/11)

Decisiones tomadas al implementar el inicio de sesión. No contradicen el informe, pero agregan supuestos que
el informe debería declarar.

| # | Sección (dueño) | Qué hace el código | Qué falta en el informe |
|---|---|---|---|
| 14 | §4.3 RNF-S-1 | Contraseña de al menos 12 caracteres (`cuentas.largo_minimo_contrasena`). | Declarar el largo mínimo y justificarlo (NIST SP 800-63B pide al menos 8; 12 deja margen sin MFA). |
| 15 | §4.3 RNF-S-1 | La sesión dura 8 h, un turno (`sesion.duracion_horas`); después hay que volver a entrar. | Declarar la duración de la sesión. |
| 16 | §4.3 RNF-S-1 | ~~Sin MFA, el administrador no podía iniciar sesión.~~ **Resuelto (13/11):** MFA con códigos TOTP; un administrador sin MFA activado sigue sin poder entrar (403). | Nada. |
| 17 | §3.2 RF-16, §5.3 | El texto de §5.3 lleva versión (`cuentas.version_texto_finalidad: "2026-1"`) y la aceptación guarda esa versión. Mientras no exista la pantalla de RF-16, la cuenta se crea con `python -m sart.cuentas crear --acepta-finalidad`: el administrador declara que el funcionario aceptó. El paso 1 del flujo (el sistema le muestra el texto al funcionario) queda para esa pantalla. | Decidir dónde vive el texto versionado de §5.3 y cómo acepta el funcionario (pantalla propia antes del alta o enlace por correo). |
| 18 | §3.2 RF-16 E2, §5.1 | La baja borra la cuenta y sus aceptaciones; no hay cuentas «desactivadas». | Confirmar que no se necesita desactivar sin borrar (por ejemplo, durante una licencia). |
| 19 | §4.3 RNF-S-1, RNF-S-3 | MFA de administradores con códigos TOTP (RFC 6238, aplicaciones como Google Authenticator). Se activa por comando en dos pasos (`activar-mfa` y `confirmar-mfa`), no desde la web, para no dejar entrar a un administrador sin MFA ni una vez. Un código usado no sirve de nuevo. Tras 5 códigos incorrectos la cuenta se bloquea 15 min; se acepta el código de los 30 s anteriores o siguientes (`mfa` en `parametros.yaml`). El secreto TOTP se guarda tal cual en la base y lo protege el cifrado en reposo del proveedor (RNF-S-3). | Declarar el tipo de MFA (TOTP), el bloqueo (5 intentos, 15 min) y que el secreto depende del cifrado en reposo de RNF-S-3. Si un teléfono se pierde, otro administrador usa `reiniciar-mfa`: describir ese procedimiento. |


## Diseño de Figma contra la especificación (13/11)

Los diseños están en `presentaciones/` (fuera del repo): inicio de sesión, inicio de jefatura, vista de red y
administración. La etapa 1 (estilos, inicio de sesión, encabezado, pie y una pantalla por rol) ya está en la web.
Antes de la etapa 2 (llenar las pantallas con datos), el equipo debe decidir estos puntos:

| # | Sección (dueño) | En el diseño | En la especificación | Lo que hace el código mientras tanto |
|---|---|---|---|---|
| 20 | §3.2 RF-15, TC-06 | Botón «Confirmar recepción» | «Confirmar lectura» | Usará «Confirmar lectura» |
| 21 | §6 RB-3, §3.2 RF-9 | El administrador edita umbrales fijos por centro (Atención 400, Alerta 500) | Los umbrales se calculan: percentiles 75 y 90 de los últimos 3 años de cada centro | La leyenda explica los percentiles; no hay edición manual. Si se quiere corregir a mano, agregarlo a RB-3 y RF-9 |
| 22 | §5.2 fuentes, §3.2 | Tarjeta «Virus circulando (ISP)» con positividad viral | No hay datos del ISP entre las fuentes (DEIS, SINCA, Open-Meteo) ni un RF que los use | No se implementa. Agregar la fuente y un RF, o sacar la tarjeta del diseño |
| 23 | §3.2 | Enlace «¿Olvidaste tu contraseña?» | No hay requisito de recuperación de contraseña | Enlace omitido. La clave la restablece el administrador (`python -m sart.cuentas restablecer-clave`, queda en la auditoría) |
| 24 | §5.1, RF-16 E2 | Columna «Estado: Activa» en usuarios | La baja borra la cuenta (ver #18) | Sin estado; se decide con #18 |
| 25 | §6 RB-1, TC-05 | Niveles de MP2,5 «Bueno» y «Regular» | «Normal» y «sobre la norma» | Usará los nombres de RB-1 (los que prueba TC-05) |


## Modelo de datos completo (13/11)

La migración 0003 agrega el resto de §5.1. Decisiones tomadas con el visto bueno del equipo que el informe
debería reflejar:

| # | Sección (dueño) | Qué hace el código | Qué falta en el informe |
|---|---|---|---|
| 26 | §5.1 Consulta_semanal | Se guardan las 6 causas J00–J98 **y el COVID-19 (U07.1 y U07.2)**, que el modelo usa como señal viral junto con la influenza. Las hospitalizaciones y las filas de totales no se cargan (`ingesta.causas`). | La regla «causa dentro de J00–J98» debe admitir U07 como señal viral, o el modelo debe dejar de usarlo. |
| 27 | §5.1 Zona y Estación, CI-3 | **Una zona por comuna** (10 zonas). Open-Meteo, que entrega un punto y no una estación, se registra como estación de fuente «Open-Meteo» en el centro de Concepción. | Definir «zona» en §5.1 y aclarar que una estación puede ser un punto de Open-Meteo. |
| 28 | §5.1 Centro_Salud y Estación | La dirección es opcional: el registro de establecimientos de prueba no la trae y las estaciones de SINCA no la publican en el archivo. | Quitar «dirección obligatoria» o indicar de dónde sale. |
| 29 | §5.1 Alerta, RF-3, RF-4, RF-5 | Solo se guardan alertas que no son «normal»: de demanda, «atención» o «alerta»; ambientales, desde «sobre la norma». Una alerta de demanda guarda su semana a través del pronóstico que la originó. **Decidido el 14/11 (parte 8):** «atención» se guarda y se muestra en la web (RF-7), pero **solo «ALERTA» genera notificación por correo**. Se mira **por centro y semana**: cada lunes con ALERTA sale su correo, con su propio acuse y escalamiento (RB-2); si se repite la corrida de la misma semana, solo se notifica si el nivel sube (atención → ALERTA cuenta como subir). Una notificación «fallida» no cuenta como enviada. Código: `debe_notificarse` y `sart.db.alertas.alertas_por_notificar`. | En RF-5 (paso 1 y E2) y RF-3 paso 4: decir que solo ALERTA notifica, que «sube de nivel» se compara con lo ya notificado del mismo centro y semana, y que cada semana en ALERTA es una alerta nueva. |
| 30 | §6 RB-4 | `semana_carga` guarda cuántos centros reportaron cada semana; la marca «completa» queda sin evaluar hasta la parte 5 (TC-01), porque falta decidir el criterio (#3). | Nada nuevo: depende de #3. |


## Umbrales, supuestos, acuse y corridas (13/11)

Migración 0004 y carga de mediciones. Decisiones que el informe debería reflejar:

| # | Sección (dueño) | Qué hace el código | Qué falta en el informe |
|---|---|---|---|
| 31 | §3.2 RF-9, §4.6 RNF-M-4 | **Opción a:** `config/parametros.yaml` es el valor de partida versionado en git. El administrador puede ajustar desde la web solo las claves de `administracion.parametros_editables` (k, cuantiles, años del umbral, supuestos de dotación, plazos de RB-2); cada ajuste se guarda en `parametro_ajustado` con autor, motivo y auditoría, y rige desde la corrida siguiente. Las demás claves solo se cambian editando el archivo. | RNF-M-4 dice que todo se lee del YAML y RF-9 que el administrador cambia supuestos: aclarar esta convivencia. |
| 32 | §6 RB-3, RF-9 (ver #21) | Los umbrales de cada centro se guardan con historia en `umbral_centro`. Un umbral fijado a mano (con motivo obligatorio) se **respeta en el recálculo anual** hasta que el administrador lo cambie. | Decidir si el recálculo anual debe respetar o reemplazar las correcciones manuales. |
| 33 | §5.2 SINCA, RB-5 | De SINCA se usa el dato validado; si no hay, el preliminar, y si no, el no validado. Los días sin dato o con valor negativo no se guardan (hoy, unos 140 por estación). Las fechas se guardan en UTC a partir de la hora de Santiago. | Declarar la prioridad validado > preliminar y qué se hace con los días sin dato. |
| 34 | §3.2 RF-15 | El enlace de acuse usa un identificador aleatorio de 43 caracteres por notificación (`token_acuse`), no el número correlativo, para que no se pueda adivinar. | Definir si la página de acuse exige iniciar sesión (recomendado) o basta el enlace. |
| 35 | §4.7 RNF-M-3 | Cada carga queda en `corrida` (tarea, fuente, inicio, fin, estado, filas, mensaje). Si una fuente falla `ingesta.avisar_tras_fallas_seguidas` veces seguidas, el comando muestra un aviso; el envío del aviso por correo al administrador llega con RF-5. | Nada nuevo; indicar a quién se avisa. |


## Parte 5: lógica del notebook migrada (14/11)

| # | Sección (dueño) | Qué hace el código | Qué falta en el informe |
|---|---|---|---|
| 36 | §6 RB-3 | El recálculo anual de umbrales se hace en **marzo**, antes del invierno (`umbrales.mes_recalculo: 3`). Por ahora se ejecuta a mano con `python -m sart.catalogo recalcular-umbrales`; la tarea programada llega con el planificador. | Confirmar el mes con el equipo y escribirlo en RB-3. |
| 37 | §3.2 RF-3, §6 RB-3 | «Supera» se implementa como estrictamente mayor: un pronóstico igual al p75 queda «normal» y uno con margen igual al p90 no es ALERTA. | Confirmar y dejarlo explícito. |
| 38 | §4.2 RNF-D-2, §9 | Respaldo diario con `python -m sart.respaldo crear` (04:30, antes de la ingesta; se conservan 14). Se respalda lo propio del sistema; de las consultas y mediciones solo la estructura, porque se vuelven a descargar (respaldo de 0,1 MB). Simulacro de TC-14 con la base de desarrollo: restauración y recarga en 59 s (RTO 2 h). Los respaldos quedan en `respaldos/`, fuera de git porque tienen datos personales. | Definir dónde se copian en producción («fuera del proveedor de base de datos») y quién revisa que se hagan; la tarea programada llega con el planificador. |


## Parte 8: corrida semanal (14/11)

`python -m sart.tareas semanal` (RF-2, RF-3, RF-6). Decisiones tomadas con el visto bueno de Mario que el
informe debería reflejar:

| # | Sección (dueño) | Qué hace el código | Qué falta en el informe |
|---|---|---|---|
| 39 | §5.1 Pronóstico, RF-3, RF-6 | **La dotación se guarda, no se calcula al leer:** tabla nueva `dotacion_sugerida` (una fila por pronóstico) con profesionales, llegadas en hora punta, espera media, espera con un profesional menos y los supuestos usados (minutos por atención, factor de hora punta, horas de funcionamiento, espera objetivo y si están validados). **Con el nivel pasa lo mismo:** el pronóstico guarda su nivel (también «normal»), el umbral vigente (`umbral_id`), k y el valor con margen. Así, si el administrador cambia un supuesto, k o un umbral (RF-9), lo que se recomendó e informó en su momento no cambia en el correo (RF-5), el historial (RF-10) ni la auditoría (RNF-S-4). Cada alerta emitida queda en la auditoría con nivel, pronóstico, umbral, k y dotación. | Agregar a §5.1 Pronóstico los atributos nivel, umbral usado, k y valor con margen, y la entidad «Dotación sugerida» (1 a 1 con Pronóstico). |
| 40 | §3.2 RF-6 E1 | Clave nueva `dotacion.supuestos_validados: false`. Se guarda con cada dotación para que el correo y la web muestren los supuestos «por validar» mientras sea false. Un centro cuyo tipo no tiene horas de funcionamiento (hoy, SUR: `null`) queda con pronóstico y nivel, pero sin dotación, y la corrida lo informa. | Definir las horas de funcionamiento de un SUR, o decir en RF-6 que no se sugiere dotación para ese tipo. |
| 41 | §3.2 RF-2, RF-3 E2, §6 RB-4 | **Semana pronosticada = la siguiente a la fecha de corte** (la última semana completa), como en el Gherkin de RF-2. **Pronóstico desactualizado** (RF-3 E2, decidido el 14/11): si esa semana no es la semana en curso el día de la corrida, el pronóstico y su nivel se guardan, pero no se crean alertas y la corrida lo informa. Pasa si a las 06:00 del lunes el DEIS todavía no tiene la semana anterior completa. | Escribir en RF-3 E2 qué es «desactualizado». Revisar con el desfase real de publicación del DEIS si las 06:00 del lunes alcanzan (si no, casi todos los lunes saldría desactualizado). |
| 42 | §2.7 CI-1, §3.2 RF-2 E2 | La corrida semanal solo acepta `modelo.especificacion: solo_rezagos` (la vigente, #1); con `con_pronostico` falla con un mensaje claro, porque falta usar el MP2,5 pronosticado y el «último valor medido» de RF-2 E2. Además, si falta el MP2,5 de la semana anterior en la estación asignada **y** en la de respaldo, o el clima de la semana anterior, el centro no se puede pronosticar (queda en «sin datos de la semana anterior»): RF-2 E2 hoy solo cubre el pronóstico de MP2,5, no los rezagos. | Decidir si RF-2 E2 se extiende a los rezagos ambientales (usar el último valor medido y avisarlo) e implementarlo junto con `con_pronostico`. |
| 43 | §4.6 RNF-M-4 (ver #9) | Claves nuevas en `parametros.yaml`: `modelo.version` (se guarda en cada pronóstico como `glm-quasipoisson/solo_rezagos/v1`), `modelo.anio_inicio: 2014` (primer año del panel y origen de la tendencia, antes fijo en el notebook) y `modelo.causas_senal_viral` (influenza y COVID-19, #26). | Nada nuevo en el informe; cierra parte de #9. |
| 44 | §3.2 RF-1 (datos de prueba) | El panel sintético `datos/prueba/procesados/panel_semanal.parquet` se generó con el COVID-19 **dentro** de `y`; el panel real y la base, no (6 causas J00–J98, #26). La regresión del panel lo comprueba de las dos formas: con el COVID-19 agregado, el panel desde la base coincide exacto con el del notebook (9.324 filas, todas las columnas). Si alguien regenera ese parquet con el notebook actual, hay que ajustar `test_rf2_panel_desde_la_base.py`. | Nada en el informe. |
| 45 | §3.2 RF-1, §5.2 DEIS | **La carga de consultas solo entiende el formato de `datos/prueba`** (`IdEstablecimiento`, `Menores_1`…, glosas como «Infección respiratoria aguda alta»). El archivo real del DEIS (`datos/crudos/at_urg_respiratorio_semanal.parquet`) usa `EstablecimientoCodigo`, `NumTotal`, `NumMenor1Anio`…, glosas como «IRA Alta (J00-J06)», e incluye subtotales («- Por covid-19…», «- Causas sistema respiratorio») y totales. Hoy no se puede cargar en la base, y por eso la corrida semanal todavía no se puede probar con los datos reales. | Nada en el informe; es trabajo de RF-1 (ingesta, TC-02): adaptar `cargar_consultas` al esquema real sin contar dos veces los subtotales. |


## Parte 9: estado de los centros (14/11)

`GET /centros/estado` y `GET /centros/{codigo}/estado` (RF-7, TC-09), con Mi centro y Red de centros conectados.
Decisiones tomadas con el visto bueno de Mario:

| # | Sección (dueño) | Qué hace el código | Qué falta en el informe |
|---|---|---|---|
| 46 | §3.2 RF-7 E1 y E3, §6 RB-5 | **Datos antiguos (E1):** se cuentan los días desde el sábado que cierra la semana de corte; sobre `consulta.aviso_datos_antiguos_dias` (8), aviso visible. **MP2,5 de la zona (E3, RB-5):** se muestra el último promedio diario medido; si la estación asignada no reportó en los últimos 7 días («una semana completa»), la de respaldo, marcada «de respaldo»; si ninguna, «datos insuficientes» con la última medición válida. El pronóstico de MP2,5 de 5 días llega con RF-4. | Escribir en RF-7 E1 desde cuándo se cuentan los 8 días, y en RB-5 que «semana completa» son los últimos 7 días. |
| 47 | §3.2 RF-7, RF-10 | **Nivel observado:** el gráfico de Mi centro y el calendario de calor de la red muestran las últimas 12 semanas (`consulta.semanas_historial`) con su nivel según las consultas reales contra los umbrales del centro, sin margen k (el margen es para la incertidumbre del pronóstico). Los umbrales que se muestran son los que se usaron al clasificar (#39). | Decir en RF-7 que el calendario de calor compara consultas observadas, no pronósticos (todavía no hay pronósticos pasados guardados). |
| 48 | §3.2 RF-7 paso 3 y E2 | El detalle de un centro para el subdirector y el administrador es `/red/<código>` (el mismo bloque que Mi centro). Si una jefatura pide un centro que no tiene asignado **o que no existe**, recibe 403 (no se revela qué centros existen) y el intento queda en la auditoría (`acceso_denegado`). La jefatura llega a su pronóstico en 0 clics. | Nada nuevo; confirmar que el 403 también vale para códigos inexistentes. |
| 49 | §4.4 RNF-S-1 | **Código MFA fijo para desarrollo:** si el `.env` define `MFA_CODIGO_DESARROLLO` (6 dígitos) **y** `COOKIE_SEGURA=false` (entorno local por http), ese código se acepta además del TOTP para los administradores con MFA activado. No salta el bloqueo tras 5 fallos y `/salud` avisa que está activo. En producción la cookie es segura (RNF-S-3) y el código fijo se ignora. Pedido por Mario para las pruebas del 14/11. | Nada en el informe mientras sea solo de desarrollo; sacarlo del `.env` antes de cualquier despliegue. |

## Tareas T5, T6 y T12 de Juan Carvajal (16/11)

Administración de cuentas desde la web (T6), la parte de RF-15 que no necesita el correo (T5) y el boletín del
LLM sin proveedor (T12). Avisado en el PR; falta el visto bueno del equipo:

| # | Sección (dueño) | Qué hace el código | Qué falta en el informe |
|---|---|---|---|
| 50 | §3.2 RF-15 (#34) | **El acuse exige iniciar sesión** (opción recomendada de #34, tomada de forma provisoria): `/acuse/<token>` pide sesión y solo el destinatario ve su notificación; un token ajeno o inventado da 404 (no revela cuáles existen). Abrir la página no registra nada; «Confirmar lectura» registra la fecha una vez (E1) y queda en la auditoría. Una notificación «fallida» no se puede confirmar (409). La regla de RB-2 (`paso_rb2`: reenvío a las 24 h, escalamiento a las 48 h desde el envío original, una vez cada uno; nada si está confirmada, fallida o ya escalada) está lista, pero el reenvío y el aviso al Subdirector esperan el correo de RF-5 (T4). | Confirmar #34 con el equipo y escribirlo en RF-15. |
| 51 | §3.2 RF-16 paso 1, §5.3 | **El texto de la finalidad lo muestra el administrador:** al crear la cuenta en la web, el diálogo muestra el texto de §5.3 (`cuentas.texto_finalidad`, con su versión) y el administrador marca «El funcionario leyó y aceptó este texto»; no hay una pantalla donde el funcionario acepte por sí mismo. El alta, el cambio de centros y la baja quedan en la auditoría solo con el id, el rol, los códigos de los centros y la versión aceptada, sin nombre ni correo (RNF-S-4). El administrador no puede darse de baja a sí mismo (409). La baja sigue borrando la cuenta (#18 y #24). | RF-16 paso 1 dice «el sistema muestra al funcionario»: ajustarlo a lo que se hace o pedir la pantalla para el funcionario. |
| 52 | §3.2 RF-8, §5.2 (#12) | **Boletín con respaldo de plantilla:** el LLM recibe solo nivel, pronóstico, límite superior y dotación por centro (las cifras guardadas de RF-7, #39); si el texto a enviar nombra a un usuario, no se envía. Su respuesta se acepta solo si cada cifra está en los datos y ningún centro aparece con otro nivel; si no, o si no hay proveedor configurado (#12), sale un boletín de plantilla con las mismas cifras. La revisión de niveles es una heurística por tramo de texto: un falso positivo solo hace salir la plantilla. | Describir en RF-8 la plantilla de respaldo y la revisión de cifras y niveles; elegir el proveedor (#12). |

T1: se corrigió la clasificación de las atenciones COVID y la distribución
de consultas entre semanas que cruzan el año, conservando el total y
evitando cantidades decimales. La justificación y las validaciones
se detallan en la PR de T1.
## Respaldo de T5 y T12 con el correo de T4 (17/11)

Reenvío, escalamiento y envío del boletín, armados sobre el correo de RF-5 (T4). Falta el visto bueno del
equipo:

| # | Sección (dueño) | Qué hace el código | Qué falta en el informe |
|---|---|---|---|
| 53 | §3.2 RF-15, §6 RB-2 | **Solo se reenvía y escala lo enviado a una jefatura** (RB-2 dice «cada alerta enviada a una jefatura»): la copia que recibe el Subdirector no se reenvía ni se escala. Los plazos se cuentan desde el envío original (`fecha_envio` no cambia al reenviar). El reenvío lleva el mismo enlace de acuse. El aviso al Subdirector es un correo por corrida con todas las alertas que cumplieron 48 h, con el centro o la zona, el nivel, la hora de emisión y el nombre de la jefatura. Si no hay ninguna cuenta de Subdirector, la notificación no se marca «escalada» y se vuelve a intentar en la corrida siguiente. Si la tarea no corrió a las 24 h, a las 48 h se escala sin reenviar antes. `python -m sart.tareas seguimiento` está pensada para correr cada hora (T11). | Confirmar en RF-15 que el Subdirector no se escala a sí mismo y que el aviso agrupa las alertas. |
| 54 | §3.2 RF-15 E2 | **Aviso al administrador de las fallidas:** una notificación «fallida» que agotó `notificaciones.reintentos_envio` no se reenvía ni se escala; se manda un correo a los administradores con el centro o la zona, el nivel y la cuenta (nombre y correo, para que revise la dirección), una sola vez por notificación (queda en la auditoría como `avisar_fallida_administrador`). | Nada nuevo; decir que el aviso es por correo. |
| 55 | §3.2 RF-8 | **A quién llega el boletín:** cada jefatura recibe el de sus centros y el Subdirector el de toda la red, los mismos que ve en RF-7; el administrador no lo recibe. No entran los centros con el pronóstico desactualizado (RF-3 E2). Un boletín por usuario y semana (la auditoría guarda solo el id, la semana y el origen del texto). El saludo con el nombre se agrega después de redactar: el nombre no va al LLM. Si dos usuarios tienen los mismos centros, se llama una sola vez al LLM. `python -m sart.tareas boletin` corre antes de las 08:00 (T11). | Escribir en RF-8 los destinatarios y que la jefatura solo ve sus centros. |
## T9 · Exportación CSV (17/11)

| # | Sección (dueño) | Qué hace el código | Qué falta en el informe |
|---|---|---|---|
| 56 | §3.2 RF-11, §5.2 | **Formato del CSV:** UTF-8 con BOM (Excel abre bien las tildes), separador «;» y coma decimal (Excel en español de Chile); una fila por centro con las cifras guardadas de RF-7 (pronóstico, intervalo de 90 %, nivel, umbrales y k usados, dotación, MP2,5 de la zona) y una columna `fuente` que cita DEIS (CC BY-NC), SINCA y Open-Meteo. **Quién exporta:** la jefatura sus centros (un centro ajeno da 403 y queda en la auditoría), el Subdirector y el administrador toda la red. Cada exportación queda en la auditoría (`exportar_csv`, sin nombre ni correo). No incluye el historial de alertas (eso es RF-10). | Escribir en RF-11 el formato, las columnas y que el Subdirector también exporta la red. |

## T11 · Planificador y Docker Compose (17/11)

| # | Sección (dueño) | Qué hace el código | Qué falta en el informe |
|---|---|---|---|
| 57 | §2.6, §4 RNF-P-1, RNF-P-2, §9.3 | **Supuestos nuevos en `horarios`:** `dia_semanal: lunes`, `boletin: "07:30"` (después del pronóstico de las 06:00 y antes de `boletin_limite`) y `seguimiento_cada_minutos: 60` (RB-2). El planificador es un proceso propio (`python -m sart.planificador`) que cada minuto corre lo que toca, cada tarea con `python -m …`; si estuvo detenido no pone al día lo perdido. **Reparto de recursos** (suma 2,0 vCPU y 3,9 GB): base 0,75 vCPU y 1 GB, API 0,5 y 768 MB, planificador 0,6 y 2 GB (la corrida semanal es lo más pesado), web 0,15 y 128 MB. La web es estática con nginx, que reenvía `/api` a la API (mismo origen para la cookie). El respaldo corre desde el planificador con el `pg_dump` 17 de la imagen (respalda la base 16). | Agregar al despliegue (§9) el planificador como contenedor, los horarios nuevos y el reparto de recursos; confirmar la hora del boletín. |

## T14 · Propuesta para cerrar las decisiones abiertas (17/11), por confirmar con el equipo

Cada fila dice qué hace hoy el código y la opción que se propone. **No están decididas:** se confirman en una
reunión corta del equipo y, al confirmarlas, se pasa cada una a su sección del informe y se marca T14 «Hecha».

| # | Pregunta | Qué hace hoy el código | Propuesta | Por qué |
|---|---|---|---|---|
| 34 | ¿La página de acuse exige iniciar sesión? | Sí (#50): solo el destinatario confirma; abrir no registra nada | **Exigir sesión** (como está) | Un filtro de correo o un reenvío no puede confirmar por la jefatura; el acuse identifica a quien leyó (RB-2) |
| 18 y 24 | ¿Desactivar una cuenta sin borrarla? | La baja borra la cuenta; sus notificaciones quedan sin usuario (RF-16 E2) | **No agregar «desactivada»**: en una licencia se asigna el centro al reemplazante y la cuenta se da de baja o se mantiene | Menos datos personales guardados (§5.3, Ley 19.628 y 21.719) y una regla menos que probar |
| 22 | ¿Tarjeta «Virus circulando (ISP)»? | No está en la web (prueba en `pantallas.test.tsx`) | **Sacarla del diseño** | No hay fuente del ISP ni un RF que la use; la señal viral ya entra al modelo desde el DEIS (#26) |
| 38 | ¿Dónde se copian los respaldos y quién lo revisa? | Respaldo diario a las 04:30 en `respaldos/` (14 copias), desde el planificador (T11) | **Copia diaria a un almacenamiento del Servicio fuera del servidor, cifrada; el administrador revisa cada lunes que la última copia exista** y se hace un simulacro de restauración al mes (TC-14) | RNF-D-2 pide RPO 24 h: si se pierde el servidor, la copia local se pierde con él |
| 40 | ¿Horas de funcionamiento de un SUR? | `dotacion.horas_funcionamiento_semana.SUR: null`: el SUR queda sin dotación sugerida | **Dejarlo así hasta confirmarlo en la entrevista** (Anexo A, pregunta 7) y mostrar «sin horario definido» | Inventar un horario daría una dotación sin respaldo; el valor se carga desde la web cuando se sepa (RF-9) |
| 42 | ¿RF-2 E2 («último valor medido») cubre MP2,5 y clima? | La corrida usa `solo_rezagos` (opción C); con `con_pronostico` falla con un mensaje claro | **Sí, cubre los dos**, y se implementa junto con `con_pronostico` cuando se valide | Es la lectura directa de RB-4 y RF-2 E2; con `solo_rezagos` no se necesita todavía |

## Integración del 17/11

| # | Sección (dueño) | Qué hace el código | Qué falta en el informe |
|---|---|---|---|
| 58 | §2.7 CI-1, §3.2 RF-1, RF-2 | **El panel real del sistema no es idéntico al del notebook** (`test_rf2_panel_real_equivalente_al_notebook`, opcional con `SART_DATOS_REALES`): las consultas difieren solo en las semanas que cruzan el año, por el reparto en enteros (máximo 5,75 consultas, mismo total); la **señal viral** suma 641.004 en el sistema y 120.408 en el notebook, por la nueva clasificación de COVID de T1. Con el panel del sistema el backtest 2024–2026 da WAPE 14,89 %, precisión 0,717 y sensibilidad 0,653 con k = 0,4, y cobertura 91,0 %: sigue cumpliendo RNF-Q-1 a Q-3, pero la precisión queda a 0,017 del mínimo. | Decidir con Daniel cuál clasificación de COVID es la correcta; si se acepta la del sistema, regenerar `panel_semanal.parquet` con ella y actualizar las cifras del backtest en el informe (§2.7) y en la prueba de regresión. |
