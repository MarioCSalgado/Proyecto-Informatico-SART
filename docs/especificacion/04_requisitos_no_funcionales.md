# 4. Requisitos no funcionales

## 4.1 Rendimiento y capacidad

| ID | Métrica o control | Objetivo | Justificación del valor | Método de verificación |
|---|---|---|---|---|
| RNF-R-1 | Tiempo de respuesta p95 | ≤ 2 s en red 4G | Google considera «buena» una carga cuando el contenido principal aparece en 2,5 s o menos (LCP, Core Web Vitals); 2 s deja margen. Se mide en 4G porque las jefaturas podrían consultar desde el teléfono durante el turno, un supuesto por validar en las entrevistas (Anexo A, pregunta 5); si solo usan el computador de la oficina, se mide en red fija. Cada vista muestra a lo más 33 centros, así que el límite viene de la red y no del volumen de datos. | Prueba de carga con 70 usuarios simulados que abren el boletín en 5 minutos (escenario de RNF-R-2), midiendo el p95 de respuesta, más Lighthouse con perfil móvil y red 4G simulada en la vista principal |
| RNF-R-2 | Throughput sostenido | ≥ 10 solicitudes/s | Unos 70 usuarios: 2 jefaturas por cada uno de los 33 centros, más los subdirectores asistenciales de los dos Servicios de Salud y el administrador. Se toma el peor caso: todos abren el boletín en los mismos 5 minutos, con unas 10 solicitudes por apertura (la página, sus archivos y unas 6 consultas a la API; se medirá en el MVP). Eso da 2,3 solicitudes/s, y el objetivo de 10 deja un margen de algo más de 4 veces. Las 2 jefaturas por centro son un supuesto por validar (Anexo A, pregunta 1). | Misma prueba de carga |
| RNF-R-3 | Volumen de datos y duración de la corrida semanal | ≤ 15 min con 2 vCPU y 4 GB | Archivo nacional de 68,6 MB; panel de unas 19.900 filas que crece 1.700 por año. La corrida parte a las 06:00 y el boletín sale a las 08:00: con 15 minutos se puede repetir completa varias veces si falla, dentro del RTO de 2 h (RNF-D-2). | Duración en el log de cada corrida |

## 4.2 Disponibilidad y continuidad

| ID | Métrica o control | Objetivo | Justificación del valor | Método de verificación |
|---|---|---|---|---|
| RNF-D-1 | Disponibilidad | ≥ 99 % mensual de abril a septiembre | Período de gestión de episodios críticos del PPDA del Concepción Metropolitano, de abril a septiembre (REF-8), que coincide con las alzas respiratorias de invierno. 99 % equivale a unas 7 horas de caída al mes. Un objetivo mayor exigiría servidores redundantes, que la restricción cost de §2.6 no permite. | Monitor externo cada 5 min (por ejemplo, el plan gratuito de UptimeRobot) |
| RNF-D-2 | RPO / RTO | RPO 24 h / RTO 2 h | Lo propio del sistema (usuarios, aceptaciones de RF-16, notificaciones, acuses y auditoría) se respalda una vez al día con una copia de la base guardada fuera del proveedor de base de datos, para no depender de las condiciones de un plan gratuito. Perder a lo más un día de acuses se corrige reenviando las alertas según RB-2. Las fuentes públicas se vuelven a descargar. La ingesta corre a las 05:00 y el boletín sale a las 08:00: un RTO de 2 h deja una hora de holgura para emitirlo a tiempo (RNF-D-3). | Restauración de prueba por entrega (TC-14) |
| RNF-D-3 | Boletines a tiempo | ≥ 95 % antes de las 08:00 del lunes | Supuesto por validar en las entrevistas (Anexo A, preguntas 1 y 5): las jefaturas armarían los turnos al inicio de la semana. Si la validación indica otro día u otra hora, el horario del boletín se cambia como parámetro (RNF-M-4) sin tocar código. De abril a septiembre hay unas 26 semanas: el 95 % admite a lo más un boletín atrasado en toda la temporada. | Hora de emisión registrada |

## 4.3 Seguridad

| ID | Métrica o control | Objetivo | Justificación del valor | Método de verificación |
|---|---|---|---|---|
| RNF-S-1 | Autenticación | Contraseña con hash (Argon2) y MFA para administradores | OWASP recomienda Argon2id como primera opción para guardar contraseñas. Se exige MFA solo a los administradores porque son quienes pueden cambiar umbrales y ver los correos de todos; las jefaturas solo leen su centro. Son pocas decenas de usuarios y no hay integración con la identidad del Servicio de Salud (§2.6). | Pruebas automáticas de inicio de sesión |
| RNF-S-2 | Autorización | 3 roles con mínimo privilegio (jefatura, subdirector, administrador) | Corresponde a los perfiles de §2.4; una jefatura solo necesita su centro. | Pruebas por rol: 0 accesos indebidos |
| RNF-S-3 | Protección de datos | TLS 1.2+ en tránsito; AES-256 en reposo | TLS 1.2 es el mínimo que exige la guía NIST SP 800-52 Rev. 2 para servidores. Los únicos datos personales son el nombre y el correo de los usuarios (§5.3). El cifrado en reposo lo entrega el proveedor de base de datos y se verifica en su configuración. | SSL Labs nota A y revisión del cifrado en reposo en la configuración del proveedor de base de datos |
| RNF-S-4 | Auditoría y registro | Cambios de umbral, alertas, envíos y confirmaciones registrados 12 meses | Un cambio de umbral cambia quién recibe alerta, y RB-2 exige registrar las confirmaciones. 12 meses cubren una campaña completa de abril a septiembre y permiten compararla con el inicio de la siguiente o responder un reclamo posterior. | Cambiar un umbral y revisar el registro |
| RNF-S-5 | Cumplimiento | 0 registros individuales de pacientes y 0 datos personales de usuarios enviados al LLM | Restricción legal de §2.6 (Leyes 19.628 y 21.719). El LLM solo recibe cifras agregadas (§5.2), nunca nombres ni correos. | Auditoría del esquema y revisión de lo que se envía al LLM |

## 4.4 Usabilidad y accesibilidad

| ID | Métrica o control | Objetivo | Justificación del valor | Método de verificación |
|---|---|---|---|---|
| RNF-U-1 | Accesibilidad | WCAG 2.1 AA; nivel nunca indicado solo con color | Cerca del 8 % de los hombres tiene daltonismo; un nivel mal leído es el error más costoso. | Lighthouse ≥ 90 en accesibilidad y axe sin errores en las vistas principales, más revisión manual de navegación por teclado y de contraste, porque ninguna herramienta automática detecta que un nivel se distinga solo por color. |
| RNF-U-2 | Tarea principal sin ayuda | ≥ 80 % de participantes en 4 clics o menos | Mismo valor de la restricción usability de §2.6. | Prueba de uso con 3 a 5 personas del perfil (§10). Con esos tamaños, el 80 % se cumple con 3 de 3, 4 de 4 o 4 de 5. |
| RNF-U-3 | Dispositivos e idiomas | Español; 360 a 1920 px de ancho | Uso en teléfono durante el turno y en computador en la oficina. 360 px es uno de los anchos más comunes de los teléfonos Android y 1920 px el de un monitor Full HD. | Prueba en 3 tamaños de pantalla |

## 4.5 Compatibilidad e interoperabilidad

| ID | Métrica o control | Objetivo | Justificación del valor | Método de verificación |
|---|---|---|---|---|
| RNF-C-1 | Navegadores / plataformas | Chrome, Edge, Firefox y Safari (última versión y la anterior), en computador y en el navegador del teléfono | Los computadores de los consultorios usan Windows con Chrome o Edge (§2.5). Safari se incluye porque cubre los iPhone, y el uso desde el teléfono es el supuesto que valida RNF-R-1. Limitarse a la última versión y la anterior evita comprometerse con navegadores que ya no reciben actualizaciones de seguridad. | Matriz de pruebas manuales |
| RNF-C-2 | APIs y formatos | REST/JSON con OpenAPI 3.0; exportación CSV UTF-8 | Aunque se eligió el panel propio (ALT-2, §8), la exportación CSV deja abierta la opción de usar los resultados en Excel o Power BI, que era la ventaja de ALT-3. | Validación del contrato en CI |

## 4.6 Mantenibilidad y calidad interna

| ID | Métrica o control | Objetivo | Justificación del valor | Método de verificación |
|---|---|---|---|---|
| RNF-M-1 | Cobertura de pruebas | ≥ 70 % en datos, modelo, alertas y colas | Esos módulos calculan las alertas: ahí un error llega a las jefaturas. Google considera aceptable 60 %, recomendable 75 % y ejemplar 90 % (Google Testing Blog, 2020); 70 % solo en el núcleo es una meta realista con 10 h semanales por integrante. | pytest-cov en CI |
| RNF-M-2 | Estilo y linting en CI | 0 errores de ruff y revisión por otro integrante | 6 integrantes con unas 10 h semanales en el mismo código (§2.6). | GitHub Actions |
| RNF-M-3 | Observabilidad | Log por corrida y aviso si una fuente falla 2 veces seguidas | La caída de fuentes externas es el riesgo más probable (§12); ya pasó en el prototipo. | Simular una fuente caída |
| RNF-M-4 | Parámetros configurables | Umbrales y supuestos editables sin tocar código | Los supuestos de dotación de CI-2, los umbrales de RB-3 y el margen k de la regla de alerta (RF-3) se validan con datos y entrevistas, y van a cambiar; también el horario del boletín de RNF-D-3. Poder cambiarlos sin tocar código es lo que obliga a que RF-9 sea Must. | Cambiar un parámetro y verificar |

## 4.7 Portabilidad y despliegue

| ID | Métrica o control | Objetivo | Justificación del valor | Método de verificación |
|---|---|---|---|---|
| RNF-P-1 | Entornos | Desarrollo y producción reproducibles con Docker | El prototipo dio resultados distintos con pandas 2 y 3 entre computadores del equipo. | Construir desde cero y correr pruebas |
| RNF-P-2 | Contenedores y límites | ≤ 2 vCPU y 4 GB de RAM en total | Los datos son pequeños (RNF-R-3) y la restricción cost de §2.6 fija el techo. La corrida semanal se ejecuta como tarea programada con esos mismos límites y se cobra por minuto (§9.3), así que pedir más recursos sube el costo mensual de forma directa. | docker stats en la corrida |
| RNF-P-3 | Despliegue y rollback | ≤ 15 min / ≤ 10 min | Ambos tiempos caben varias veces dentro del RTO de 2 h (RNF-D-2): un despliegue que sale mal el lunes temprano se revierte antes del boletín de las 08:00. | Despliegue cronometrado |

## 4.8 Calidad del pronóstico y de las alertas

Categoría agregada: mide si el pronóstico y las alertas sirven. Valores actuales del prototipo.

| ID | Métrica o control | Objetivo | Justificación del valor | Método de verificación |
|---|---|---|---|---|
| RNF-Q-1 | Error del pronóstico (WAPE) | ≤ 15 % y ≤ repetir la semana anterior | Hoy: 14,9 %, frente a 15,0 % de repetir la semana anterior y 23,6 % de repetir la misma semana del año anterior. El modelo apenas empata con el más simple de esos dos, así que su aporte no es el número central sino el intervalo, el umbral propio de cada centro y el efecto del MP2,5 (riesgo R-1). El techo de 15 % es justamente el valor de esa línea base: un modelo que no la alcance no justifica su complejidad. | Backtest 2024–2026 (TC-03) |
| RNF-Q-2 | Calidad de las alertas | Sensibilidad ≥ 0,60 y precisión ≥ 0,70 | Los mínimos no vienen de una norma: se fijaron para que el aviso sirva en la práctica. Con precisión 0,70, 7 de cada 10 alertas corresponden a una semana realmente alta; con sensibilidad 0,60, se anticipan 3 de cada 5 semanas altas. Se exige más precisión que sensibilidad porque, si llegan muchas falsas alarmas, las jefaturas dejan de leer el correo y ni las alertas correctas sirven. Hoy, con la regla ajustada de RF-3 (k = 0,4): precisión 0,73 y sensibilidad 0,66, es decir, por centro y por año unas 4 alertas, 3 correctas y 1 falsa, y 1 o 2 semanas altas sin aviso. Repetir la semana anterior logra 0,69 y 0,68: el modelo gana en precisión y empata en F1 (0,69), así que su aporte está en el intervalo, el umbral por centro y el efecto del MP2,5 (riesgo R-1). | Backtest 2024–2026 (TC-04). Como k se eligió con los mismos años, el resultado es optimista: en E3 se fija k con 2024 y se prueba en 2025–2026. |
| RNF-Q-3 | Cobertura del intervalo de 90 % | Entre 85 % y 95 % de las semanas observadas dentro del intervalo | RF-2 promete un intervalo de 90 % y hoy se calcula solo con la varianza del modelo de conteo, sin el error de los parámetros. Si la cobertura real quedara muy por debajo, las jefaturas confiarían de más en el pronóstico; si quedara muy por encima, el intervalo sería tan ancho que no serviría para decidir. Se aceptan 5 puntos de tolerancia porque el intervalo es aproximado y las semanas de un mismo centro no son independientes entre sí. | Backtest 2024–2026 (TC-11) |
| RNF-Q-4 | Acierto del pronóstico de MP2,5 | Sensibilidad ≥ 0,50 en los días sobre 50 µg/m³, con un día de anticipación | RF-4 depende del pronóstico de MP2,5 de Open-Meteo, que viene del modelo global CAMS con celdas de unos 45 km: a esa escala no distingue bien los episodios locales del valle de Concepción. Avisar la mitad de los días sobre la norma es el mínimo para que la alerta ambiental aporte algo; si no lo alcanza, RF-4 debe apoyarse en la medición de SINCA y avisar el mismo día en vez de anticipar. | Desde la semana 10 se compara cada pronóstico guardado con la medición de Kingston College (TC-12) |

