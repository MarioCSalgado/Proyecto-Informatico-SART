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
| 29 | §5.1 Alerta, RF-3, RF-4 | Solo se guardan alertas que no son «normal»: de demanda, «atención» o «alerta»; ambientales, desde «sobre la norma». Una alerta de demanda guarda su semana a través del pronóstico que la originó. | Confirmar que «atención» también genera alerta y notificación, o solo «alerta». |
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
