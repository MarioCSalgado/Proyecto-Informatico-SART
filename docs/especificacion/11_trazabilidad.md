# 11. Trazabilidad

| Evidencia / necesidad | RF | RNF asociados | Casos de prueba | Componente o módulo | Estado |
|---|---|---|---|---|---|
| EV-1, EV-2 | RF-1 | R-3, D-2, M-3 | TC-01, TC-02, TC-14 | Tareas programadas (ingesta) | Prototipo |
| EV-1 | RF-2 | Q-1, Q-3, R-3 | TC-03, TC-11 | Tareas programadas (modelo) | Prototipo |
| EV-1 | RF-3 | Q-2, M-4 | TC-04, TC-17 | Tareas programadas (alertas) | Prototipo |
| EV-2, EV-3 | RF-4 | D-1, Q-4 | TC-05, TC-12 | Tareas programadas (alertas) | Parcial |
| §2.3 comp. 4 | RF-5 | D-3, S-3, S-4 | TC-06 | Tareas programadas (notificaciones) | Pendiente |
| EV-1 | RF-6 | M-4 | TC-07 | Tareas programadas (dotación) | Prototipo |
| §2.4 | RF-7 | R-1, R-2, U-1 a U-3, S-1, S-2, C-1 | TC-08, TC-09, TC-10 | Aplicación web y API | Pendiente |
| §2.4 (alfabetización digital) | RF-8 | S-5 | TC-18 | Tareas programadas (resumen) | Pendiente |
| §2.4 (roles) | RF-9 | S-1, S-2, S-4, M-4 | TC-09, TC-17 | Aplicación web y API (administración) | Pendiente |
| §2.4 · riesgo R-8 | RF-10 | Q-2 | TC-19 | Aplicación web y API | Pendiente |
| §8 (ALT-3) | RF-11 | C-2 | TC-15 | API (exportación) | Pendiente |
| EV-2 · CI-3 | RF-12 | U-1, C-1 | TC-20 | Aplicación web | Pendiente |
| §2.3 comp. 4 · RB-2 | RF-15 | S-3, S-4 | TC-06 | API (acuse) y Tareas programadas | Pendiente |
| §5.3 | RF-16 | S-1, S-2, S-4, S-5 | TC-16 | Aplicación web y API (administración) | Pendiente |
| §2.6 | Transversal | P-1 a P-3, M-1, M-2, C-2, S-5 | TC-13, TC-15 | Todos los contenedores (Docker) | Pendiente |

Los RNF se indican sin el prefijo «RNF-». RF-13 y RF-14 son Won't y no se trazan. La columna «Componente o módulo» usa los contenedores de la arquitectura de la E2 (C4 nivel 2): Aplicación web, API, Tareas programadas y Base de datos; esta última la usan todos los requisitos y por eso no se repite. La última fila agrupa los RNF transversales de despliegue, calidad interna y cumplimiento.

Casos de prueba referenciados en la matriz

| Caso | Tipo de prueba | Qué verifica | RF | Criterio de éxito |
|---|---|---|---|---|
| TC-01 | Automática | Semana incompleta y semanas que cruzan el año | RF-1 | Se marca y se reasigna bien |
| TC-02 | Automática | Fuente caída o columna renombrada | RF-1 | Aviso y último dato válido |
| TC-03 | Backtest | Pronóstico 2024–2026 | RF-2 | WAPE ≤ 15 % y ≤ línea base |
| TC-04 | Backtest | Niveles de alerta | RF-3 | Sensibilidad ≥ 0,60, precisión ≥ 0,70 |
| TC-05 | Automática | Clasificación con 45, 50, 51, 80, 110 y 170 µg/m³ (bordes de RB-1) | RF-4 | Normal, Normal, sobre la norma, Alerta, Preemergencia y Emergencia |
| TC-06 | Integración | Envío, confirmación con «Confirmar lectura», reenvío y escalamiento con correo de prueba | RF-5, RF-15 | 1 correo por alerta; reenvío a las 24 h; aviso al Subdirector a las 48 h |
| TC-07 | Automática | Cálculo de Erlang C | RF-6 | 545 consultas en 123 h → 7,1 llegadas/h y 3 profesionales, con 4,2 min de espera media |
| TC-08 | Carga | 70 usuarios simulados que abren el boletín en 5 minutos, más Lighthouse con perfil móvil y red 4G simulada | RF-7 | p95 ≤ 2 s y ≥ 10 solicitudes/s (RNF-R-1, R-2) |
| TC-09 | Automática | Acceso por rol | RF-7, RF-9 | 0 accesos indebidos (RNF-S-2) |
| TC-10 | Con usuarios | Prueba de uso, 3 a 5 personas | RF-7 | ≥ 80 % en 4 clics |
| TC-11 | Backtest | Cobertura del intervalo de 90 % | RF-2 | Entre 85 % y 95 % de las semanas dentro del intervalo (RNF-Q-3) |
| TC-12 | Comparación | Pronóstico de MP2,5 guardado frente a la medición de Kingston College | RF-4 | Sensibilidad ≥ 0,50 en los días sobre 50 µg/m³ (RNF-Q-4) |
| TC-13 | Despliegue | Construcción desde cero con Docker, despliegue y rollback cronometrados, pruebas y linting en CI | Transversal | Todo pasa; ≤ 15 min y ≤ 10 min; cobertura ≥ 70 %; 0 errores de ruff (RNF-P-1 a P-3, M-1, M-2) |
| TC-14 | Restauración | Restaurar el respaldo diario y volver a descargar las fuentes | RF-1 | Sistema operativo en 2 h o menos (RNF-D-2) |
| TC-15 | Auditoría | Esquema de la base de datos, contrato OpenAPI y exportación CSV | RF-11 y transversal | 0 registros de pacientes; contrato válido; CSV UTF-8 solo con los centros del usuario (RNF-S-5, C-2) |
| TC-16 | Integración | Alta de cuenta sin aceptación registrada de la finalidad de §5.3 | RF-16 | La cuenta no se crea y no se almacenan el nombre ni el correo |
| TC-17 | Automática | Regla de alerta con margen y cambio del parámetro k | RF-3, RF-9 | Umbral 713, pronóstico 700 y límite superior 760: con k = 0,4 → ALERTA (715); con k = 0 → sin ALERTA |
| TC-18 | Automática | Contenido enviado al LLM y cifras del boletín | RF-8 | 0 nombres o correos enviados; las cifras coinciden con las del sistema y ningún nivel cambia (RNF-S-5) |
| TC-19 | Backtest | Historial del invierno 2025 | RF-10 | Cada alerta emitida aparece junto a si la semana fue realmente alta |
| TC-20 | Automática | Mapa de centros | RF-12 | Los 33 centros muestran su nivel y su estación asignada (CI-3) |

