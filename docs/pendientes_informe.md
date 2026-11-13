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
| Cobertura del intervalo | No reportada | RNF-Q-3: 85–95 % | Calcular |

## Revisión de la especificación contra el notebook 5 (13/11)

Salió de leer `docs/especificacion/`, `config/parametros.yaml` y el notebook 5 completo. Se ordena por impacto.
«Bloquea» indica qué paso de `PASOS.md` no conviene empezar sin la decisión.

### Decisiones pendientes

| # | Sección (dueño) | Problema y por qué importa | Qué hay que decidir o cambiar en el informe | Bloquea |
|---|---|---|---|---|
| 1 | §2.7 CI-1 (Daniel), §4.8 RNF-Q-1 y Q-2 | Las cifras de referencia (WAPE 14,9 %; k = 0: 0,85/0,48; k = 0,4: 0,73/0,66) salen del modelo `solo_rezagos`, y k = 0,4 se eligió con él. CI-1 describe `con_pronostico` (agrega MP2,5 y temperatura de la semana pronosticada), que es el que el notebook usa en el pronóstico real; su backtest da WAPE 14,6 % y k = 0: 0,82/0,49. Además, ese backtest usa el MP2,5 *observado* de la semana pronosticada, no el pronóstico de Open-Meteo, así que es optimista. | Elegir el modelo del sistema. Si es `con_pronostico`, recalcular k y las cifras de RNF-Q-1/Q-2 con él (idealmente con el pronóstico de MP2,5 y no el observado). Si es `solo_rezagos`, corregir CI-1. | Parte 6 |
| 2 | §3.2 RF-2, §6 RB-4 (Daniel) | La descripción de RF-2 y RB-4 dice que se pronostica «la semana en curso», pero el Gherkin de RF-2 y el notebook pronostican la semana siguiente a la última semana completa (27/09 → SE 40). Si el MINSAL publica con más de una semana de atraso, el boletín del lunes pronostica una semana ya pasada. El atraso de publicación no se ha verificado. | Medir el atraso real de publicación del DEIS y redactar RF-2 y RB-4 con lo que se pronostica de verdad (horizonte en semanas). Si el horizonte es mayor que 1, el modelo debe pronosticar a más de una semana. | Parte 5 |
| 3 | §3.2 RF-1, §6 RB-4 (Daniel) | Con `cobertura_minima_semana: 0.8`, el Gherkin de RF-1 falla: 29 de 33 centros = 88 % ≥ 80 %, así que la semana del 04/10 quedaría como completa. El notebook la marca incompleta por un segundo criterio que no está en el informe ni en el YAML: total semanal < 0,6 × mediana de las 4 semanas previas. Además, el criterio es global: en la «última semana completa» del notebook hay centros con carga a medias (SAPU Alcalde Leocán Portus al 41 % de su mediana, SAPU Talcahuano Sur al 43 %). | Escribir en RB-4 los dos criterios (cobertura de centros y caída del total) con sus valores, y decidir si la incompletitud se marca también por centro. Agregar los valores a `parametros.yaml`. | Parte 5 |
| 4 | §3.2 RF-7 | El Gherkin dice 357 consultas con intervalo 263–450. El notebook da 357,55 (264,08–451,02); redondeando son 358 (264–451). | Definir la regla de redondeo para mostrar cifras (redondear o truncar) y ajustar el Gherkin. | Parte 7 |
| 5 | §3.2 RF-6, §2.7 CI-2 (Daniel), §5.1 | El notebook tomó el tipo de centro de `TipoPertenenciaEstabGlosa` (a qué red pertenece), no de `TipoEstablecimientoGlosa`. Sin el tipo correcto no se puede elegir 123 h o 168 h. El registro trae además `ClasificacionTipoSapu`: si hay SAPU de horario corto, 123 h no vale para todos. En el registro de las 10 comunas no aparece ningún SUR, así que el SUR sin horas no bloquea por ahora. | Confirmar la columna de tipo y si las horas dependen de la clasificación del SAPU. Si dependen, agregar esa distinción en CI-2, RF-6 y `parametros.yaml`. | Parte 5 |
| 6 | §6 RB-3 (Daniel) | «Últimos tres años con datos válidos» no dice si un año en curso o incompleto cuenta. En el pronóstico real, el notebook usa 2024, 2025 y 2026, con 2026 todavía incompleto. | Definir si se usan años calendario completos o las últimas 156 semanas válidas. | Parte 5 |
| 7 | §6 RB-3 (Daniel), §3.2 RF-3 | RB-3 no dice si el nivel «atención» (p75) usa el margen k. RF-3 dice que no lo usa. | Dejarlo explícito en RB-3: el margen se aplica solo al p90. | — |
| 8 | §6 RB-1 (Daniel), TC-05 | No dice cómo tratar los decimales en los bordes (¿50,4 µg/m³ es Normal o «sobre la norma»?) ni si el promedio de 24 h se redondea antes de clasificar, como hace la norma. | Definir el redondeo del promedio diario antes de clasificar. | Parte 5 |
| 9 | §4.6 RNF-M-4 | Varios supuestos del notebook no están en `parametros.yaml`: año de inicio 2014, factor 0,6 de la mediana, ventana de 12 semanas para contar los centros activos, catálogo de estaciones con su asignación a cada comuna y las coordenadas del punto de Open-Meteo. | Agregarlos al YAML al migrar la lógica (no requiere cambiar el informe). | Parte 5 |

### Información que falta

| # | Sección (dueño) | Qué falta | Efecto |
|---|---|---|---|
| 10 | §2.7 CI-3 (Daniel), §6 RB-5 | Faltan los códigos SINCA de 5 de las 6 estaciones (solo Kingston College tiene datos reales). Hoy el 50 % de las semanas del panel usa la estación de respaldo. La asignación con Haversine y Voronoi se prometió para la E2 y no está en el notebook (la asignación sigue siendo manual por comuna). | La marca «de respaldo» de RB-5 será la regla y no la excepción. Hay que actualizar CI-3 o implementar Voronoi. |
| 11 | §3.2 RF-1, TC-01 | El DEIS escribe el año calendario en las semanas que cruzan el año nuevo; el notebook lo corrige con la librería `epiweeks`, que no está en el stack. | Agregar `epiweeks` a las dependencias o reimplementar el calendario del MINSAL (se decide en la parte 4). |
| 12 | §5.2, §9 | Faltan los proveedores de LLM (RF-8), de correo (RF-5) y de nube. | No bloquea el dominio; sí las tareas de notificación y el despliegue. |
| 13 | Anexo A | Siguen sin validar en entrevistas los supuestos de dotación (15 min, factor 1,6, horas por tipo) y el atraso de publicación del MINSAL (ver #2). | RF-6 E1: mostrar los supuestos como «por validar». |
