# 3. Requisitos funcionales

## 3.1 Lista resumida

| ID | Título | Descripción breve | Prioridad (MoSCoW) | Criterios de aceptación |
|---|---|---|---|---|
| RF-1 | Ingesta y validación de datos | Descarga DEIS, SINCA y Open-Meteo y arma el panel semanal | Must | La semana incompleta queda marcada |
| RF-2 | Pronóstico semanal por centro | Consultas de la semana en curso, con intervalo de 90 % | Must | Todo centro con historia tiene pronóstico |
| RF-3 | Alerta de demanda por centro | Nivel normal, atención o ALERTA según umbrales del centro | Must | Pronóstico con margen sobre el percentil 90 → ALERTA |
| RF-4 | Alerta ambiental diaria | Clasifica el MP2,5 pronosticado según la norma y los niveles de episodio | Must | 95 µg/m³ → nivel Alerta (RB-1) |
| RF-5 | Envío de la notificación de alerta | Correo con nivel, pronóstico y dotación a la jefatura del centro y al Subdirector | Must | Un correo por alerta, antes de las 08:00 |
| RF-6 | Recomendación de dotación | Profesionales necesarios en hora punta (Erlang C) | Must | Espera media bajo el objetivo |
| RF-7 | Consulta del estado de alerta | Cada usuario ve el estado de sus centros | Must | Estado del centro en 4 clics o menos |
| RF-8 | Resumen en lenguaje natural | Boletín redactado con un LLM desde los resultados | Should | Dado el boletín del lunes, cuando se revisa, entonces sus cifras coinciden con las del sistema y no cambia ningún nivel |
| RF-9 | Administración | Usuarios, centros asignados, umbrales y supuestos | Must | Dado un cambio de umbral, cuando se guarda, entonces queda registrado y se aplica en la corrida siguiente |
| RF-10 | Historial de alertas | Alertas pasadas frente a lo observado | Should | Dado el invierno 2025, cuando se abre el historial, entonces muestra cada alerta emitida y si se cumplió |
| RF-11 | Exportación CSV | Pronóstico y alertas para Excel o Power BI | Should | Dada una jefatura, cuando exporta, entonces recibe un CSV UTF-8 solo con sus centros |
| RF-12 | Mapa de centros | Nivel de cada centro y su estación | Could | Dado el mapa, cuando se abre, entonces cada centro muestra su nivel y su estación asignada |
| RF-13 | Aplicación móvil nativa | Cubierta por la consulta responsiva | Won't | Descartada por schedule (§2.6) |
| RF-14 | Integración con sistemas clínicos | Datos por paciente de los centros | Won't | Descartada por legal considerations (§2.6) |
| RF-15 | Confirmación de lectura y escalamiento | Registra el acuse de la jefatura, reenvía a las 24 h y escala al Subdirector a las 48 h (RB-2) | Must | Sin confirmación en 48 h → aviso al Subdirector |
| RF-16 | Alta de cuentas y consentimiento | El administrador crea la cuenta después de que el funcionario acepta la finalidad declarada en §5.3 | Must | Sin aceptación registrada no se crea la cuenta |

Los identificadores no se reutilizan ni se renumeran: un requisito nuevo toma el siguiente número libre, para que las referencias de las demás secciones sigan siendo válidas. Por eso RF-15 y RF-16 aparecen después de los Won't. RF-9 pasó de Should a Must porque RF-5 y RF-16 necesitan que existan usuarios con correo y centros asignados, y RF-7 restringe la consulta a los centros asignados: un requisito Must no puede depender de uno Should. RF-5 quedó dividido en el envío (RF-5) y el control del acuse y el escalamiento (RF-15), para que cada uno tenga un criterio de aceptación verificable por separado.

## 3.2 Detalle por requisito funcional

### RF-1 · Ingesta y validación de datos — Prioridad: Must

- **Descripción:** Cada día descarga las fuentes públicas y arma el panel semanal por centro: consultas (6 causas J00–J98), MP2,5, temperatura y actividad viral (consultas por influenza y COVID-19 del mismo archivo del DEIS).
- **Actores:** Planificador (tarea programada) · Administrador · DEIS, SINCA y Open-Meteo.
- **Precondiciones:** Fuentes accesibles; tabla de los 33 centros y sus estaciones cargada.

**Flujo principal:**

1. A las 05:00 descarga las fuentes y guarda una copia sin modificar.
2. Asigna cada atención a su semana epidemiológica y filtra las 10 comunas.
3. Une contaminación y clima por comuna y semana.
4. Marca la última semana si está incompleta: solo se usa el último reporte confirmado (RB-4).
5. Publica un reporte de calidad.


**Flujos alternos y excepciones:**

E1 · Fuente caída: 3 reintentos; si falla, conserva el último dato válido y avisa al administrador.
E2 · Falta una columna obligatoria: no actualiza esa fuente y avisa.

- **Datos involucrados:** Atenciones semanales, establecimientos, MP2,5 diario, clima diario.
- **Reglas de negocio aplicables:** RB-4, RB-5

**Criterios de aceptación (Gherkin):**

```gherkin
Escenario: Semana publicada a medias
Dado que la semana del 4 de octubre de 2026 trae datos de 29 de los 33 centros
Cuando corre la ingesta
Entonces esa semana queda marcada como incompleta
Y el pronóstico parte de la semana del 27 de septiembre
```

- **RNF asociados:** RNF-R-3, RNF-D-2, RNF-M-3

### RF-2 · Pronóstico semanal por centro — Prioridad: Must

- **Descripción:** Cada lunes estima las consultas respiratorias de la semana en curso en cada centro, con intervalo de 90 %, con el modelo de conteo de §2.7 (CI-1).
- **Actores:** Planificador · Subdirector asistencial.
- **Precondiciones:** RF-1 terminado; centro con 52 semanas o más de historia.

**Flujo principal:**

1. El lunes a las 06:00 reentrena el modelo con las semanas completas (sin 2020 ni 2021).
2. Calcula pronóstico e intervalo de cada centro.
3. Guarda cada pronóstico con la versión del modelo y la fecha de corte.


**Flujos alternos y excepciones:**

E1 · Centro sin historia suficiente: no se pronostica y se informa.
E2 · Sin pronóstico de MP2,5: usa el último valor observado y lo indica.

- **Datos involucrados:** Panel semanal, pronóstico de MP2,5, versión del modelo.
- **Reglas de negocio aplicables:** RB-4

**Criterios de aceptación (Gherkin):**

```gherkin
Escenario: Pronóstico de la semana siguiente
Dado que la última semana completa es la del 27 de septiembre de 2026
Cuando corre el pronóstico
Entonces los 31 centros con historia tienen pronóstico e intervalo para la semana 40
```

- **RNF asociados:** RNF-Q-1, RNF-Q-3, RNF-R-3

### RF-3 · Alerta de demanda por centro — Prioridad: Must

- **Descripción:** Compara el pronóstico, más un margen de seguridad, con los umbrales del centro y asigna nivel normal, atención o ALERTA.
- **Actores:** Planificador · Jefatura de urgencia · Subdirector asistencial.
- **Precondiciones:** RF-2 publicado.

**Flujo principal:**

1. Calcula los umbrales de cada centro según RB-3 (percentiles 75 y 90 de sus últimos 3 años válidos).
2. Calcula el margen de seguridad: k veces la desviación estimada del pronóstico, con desviación = (límite superior del intervalo − pronóstico) / 1,645 y k = 0,4 (configurable en RF-9).
3. Asigna ALERTA si el pronóstico más el margen supera el percentil 90; atención si el pronóstico supera el percentil 75; normal en otro caso.
4. Entrega a RF-5 las alertas nuevas o que suben de nivel.


**Flujos alternos y excepciones:**

E1 · Centro con menos de 52 semanas: no se clasifica.
E2 · Pronóstico desactualizado: no emite alertas nuevas y lo informa.

- **Datos involucrados:** Pronóstico, umbrales, alerta (centro, semana, nivel).
- **Reglas de negocio aplicables:** RB-3

**Criterios de aceptación (Gherkin):**

```gherkin
Escenario: Centro en alerta
Dado que el umbral de alerta del SAR Chiguayante es 713 consultas semanales
Y su pronóstico es 760 consultas
Cuando se clasifican los niveles
Entonces el SAR Chiguayante queda en nivel ALERTA
Escenario: Alerta por margen de seguridad
Dado que el umbral de alerta del SAR Chiguayante es 713 consultas semanales
Y su pronóstico es 700 consultas, con límite superior de 760
Cuando se clasifican los niveles con k = 0,4
Entonces el pronóstico con margen es 715 consultas
Y el SAR Chiguayante queda en nivel ALERTA
```

- **RNF asociados:** RNF-Q-2, RNF-M-4

### RF-4 · Alerta ambiental diaria — Prioridad: Must

- **Descripción:** Revisa el pronóstico de MP2,5 de 5 días y clasifica cada día según RB-1: sobre la norma diaria (50 µg/m³) o nivel de episodio del PPDA (Alerta desde 80, Preemergencia desde 110, Emergencia desde 170 µg/m³).
- **Actores:** Planificador · Subdirector asistencial · Jefaturas de urgencia · Open-Meteo.
- **Precondiciones:** Pronóstico de MP2,5 descargado (RF-1).

**Flujo principal:**

1. A las 07:00 calcula el promedio diario pronosticado de los próximos 5 días.
2. Si algún día queda sobre la norma o en nivel de episodio (RB-1), emite la alerta con día, valor y nivel.
3. Entrega la alerta a RF-5.


**Flujos alternos y excepciones:**

E1 · Sin pronóstico: estado "datos insuficientes" (RB-5); no se supone un valor.
E2 · El nivel es un pronóstico propio: el aviso aclara que no es una declaración oficial.

- **Datos involucrados:** Pronóstico horario de MP2,5, alerta ambiental.
- **Reglas de negocio aplicables:** RB-1, RB-5

**Criterios de aceptación (Gherkin):**

```gherkin
Escenario: Episodio crítico pronosticado
Dado un promedio diario pronosticado de 95 µg/m³ para el sábado
Cuando corre el proceso diario
Entonces se emite una alerta ambiental de nivel "Alerta" para el sábado
Y el aviso aclara que no es una declaración oficial
```

- **RNF asociados:** RNF-D-1, RNF-Q-4

### RF-5 · Envío de la notificación de alerta — Prioridad: Must

- **Descripción:** Envía por correo a la jefatura de cada centro afectado y al Subdirector asistencial el nivel, el pronóstico con su intervalo y la dotación sugerida. El control del acuse y el escalamiento son RF-15, para que cada requisito se pueda verificar por separado.
- **Actores:** Planificador · Jefatura de urgencia · Subdirector asistencial · servidor de correo.
- **Precondiciones:** RF-3 o RF-4 ejecutado; cuentas creadas con correo y centros asignados (RF-16 y RF-9).

**Flujo principal:**

1. Reúne las alertas nuevas o que subieron de nivel.
2. Arma un correo por usuario, solo con los centros que le corresponden.
3. Envía antes de las 08:00 y registra el envío con fecha y hora.
4. Entrega el envío registrado a RF-15 para el control del acuse.


**Flujos alternos y excepciones:**

E1 · Falla el envío: 3 reintentos; si falla, la notificación queda «fallida» para el administrador.
E2 · Alerta ya notificada con el mismo nivel: no se envía de nuevo.

- **Datos involucrados:** Alerta, usuario (nombre, correo, centros), notificación (estado y fecha de envío).
- **Reglas de negocio aplicables:** RB-2 (el envío; el acuse y el escalamiento se verifican en RF-15)

**Criterios de aceptación (Gherkin):**

```gherkin
Escenario: Notificación única
Dado que el SAPU Lagunillas pasó a nivel ALERTA
Cuando se emite el boletín del lunes
Entonces su jefatura recibe un correo antes de las 08:00
Y no recibe un segundo correo si el proceso se repite
```

- **RNF asociados:** RNF-D-3, RNF-S-3, RNF-S-4

### RF-15 · Confirmación de lectura y escalamiento — Prioridad: Must

- **Descripción:** Registra la confirmación de lectura de cada notificación enviada por RF-5, reenvía la alerta si no hay acuse en 24 horas y escala al Subdirector asistencial a las 48 horas (RB-2).
- **Actores:** Planificador · Jefatura de urgencia · Subdirector asistencial · servidor de correo.
- **Precondiciones:** RF-5 ejecutado y la notificación registrada como enviada.

**Flujo principal:**

1. El correo de RF-5 incluye un enlace a una página de acuse, con un identificador único por notificación.
2. La notificación queda «confirmada», con fecha y hora, cuando la jefatura presiona «Confirmar lectura» en esa página. Abrir el enlace no basta, porque algunos filtros de correo abren los enlaces solos.
3. Sin acuse a las 24 h, reenvía la alerta una vez y la marca «reenviada».
4. Sin acuse a las 48 h desde la emisión original, avisa al Subdirector asistencial y la marca «escalada».


**Flujos alternos y excepciones:**

E1 · Se presiona «Confirmar lectura» dos veces: la confirmación se registra una sola vez.
E2 · La notificación quedó «fallida» en RF-5: no se reenvía ni se escala, y se avisa al administrador.

- **Datos involucrados:** Notificación (estado, fecha de envío y fecha de confirmación), alerta y usuario.
- **Reglas de negocio aplicables:** RB-2

**Criterios de aceptación (Gherkin):**

```gherkin
Escenario: Escalamiento sin confirmación
Dado que la jefatura no confirmó la lectura en 48 horas
Cuando se cumple el plazo
Entonces el Subdirector asistencial recibe el aviso
Y el escalamiento queda registrado con fecha y hora
```

- **RNF asociados:** RNF-S-3, RNF-S-4

### RF-6 · Recomendación de dotación — Prioridad: Must

- **Descripción:** Calcula con Erlang C (CI-2) los profesionales necesarios en hora punta para que la espera media no supere el objetivo. Solo demanda respiratoria.
- **Actores:** Planificador · Jefatura de urgencia.
- **Precondiciones:** RF-2 publicado; supuestos configurados (RNF-M-4): 15 minutos por atención (supuesto de CI-2, §2.7, que se contrastará con REF-11 y las entrevistas), factor de hora punta 1,6, espera objetivo 30 minutos, y horas de funcionamiento a la semana: 123 h en SAPU y SAR (lunes a viernes de 17:00 a 08:00 y 24 horas los fines de semana y festivos) y 168 h en hospitales.

**Flujo principal:**

1. Convierte el pronóstico en llegadas por hora en hora punta: lo divide por las horas de funcionamiento del centro y lo multiplica por el factor de hora punta.
2. Busca el menor número de profesionales que cumple la espera objetivo.
3. Publica el resultado con los supuestos a la vista.


**Flujos alternos y excepciones:**

E1 · Supuestos sin validar: se muestran como "por validar".

- **Datos involucrados:** Pronóstico, supuestos de dotación.
- **Reglas de negocio aplicables:** — (supuestos configurables en RF-9 y RNF-M-4)

**Criterios de aceptación (Gherkin):**

```gherkin
Escenario: Dotación del centro con más demanda
Dado un pronóstico de 545 consultas semanales para el SAR Chiguayante, que atiende 123 horas a la semana
Cuando se calcula la dotación
Entonces resultan 7,1 llegadas por hora en hora punta
Y se recomiendan 3 profesionales, con 4,2 minutos de espera media
Y con 2 profesionales la espera sería de 55 minutos
```

- **RNF asociados:** RNF-M-4

### RF-7 · Consulta del estado de alerta — Prioridad: Must

- **Descripción:** Cada usuario autenticado consulta nivel, pronóstico, intervalo, dotación y fecha de corte de sus centros, en el panel web propio de SART (ALT-2, elegida en la matriz de decisión de la E2, §8).
- **Actores:** Jefatura de urgencia (su centro) · Subdirector asistencial (todos los centros) · Administrador.
- **Precondiciones:** Usuario autenticado; RF-2 a RF-6 publicados.

**Flujo principal:**

1. El usuario inicia sesión.
2. Ve el nivel de su centro (el Subdirector, la lista ordenada por nivel).
3. Abre el detalle con la fecha de corte y las advertencias de calidad.


**Flujos alternos y excepciones:**

E1 · Datos con más de 8 días: aviso visible.
E2 · Centro no asignado: acceso negado y registrado.
E3 · Estación sin datos: muestra "datos insuficientes" y la última medición válida (RB-5).

- **Datos involucrados:** Usuario y rol, pronósticos, alertas, dotación.
- **Reglas de negocio aplicables:** RB-3, RB-5

**Criterios de aceptación (Gherkin):**

```gherkin
Escenario: Jefatura consulta su centro
Dado que la jefatura del SAPU Loma Colorada inició sesión
Cuando consulta el estado de alerta
Entonces ve el pronóstico de 357 consultas con intervalo de 263 a 450
Y llega a esa información en 4 clics o menos
```

- **RNF asociados:** RNF-R-1, RNF-R-2, RNF-U-1 a U-3, RNF-S-1, RNF-S-2, RNF-C-1

### RF-16 · Alta de cuentas y consentimiento — Prioridad: Must

- **Descripción:** Da de alta la cuenta de un funcionario solo después de que acepta la finalidad del tratamiento de sus datos declarada en §5.3, y deja constancia de esa aceptación.
- **Actores:** Administrador del sistema · Jefatura de urgencia o Subdirector asistencial, como titular de los datos.
- **Precondiciones:** El administrador tiene el nombre, el correo institucional, el rol y los centros que le corresponden al funcionario.

**Flujo principal:**

1. El sistema muestra al funcionario la finalidad declarada en §5.3, los datos que se tratarán y el plazo de conservación.
2. El funcionario acepta y la aceptación queda registrada con fecha, hora y versión del texto.
3. El administrador crea la cuenta con su rol y sus centros asignados (RF-9).
4. La cuenta queda habilitada para recibir notificaciones (RF-5) y para consultar (RF-7).


**Flujos alternos y excepciones:**

E1 · El funcionario no acepta: no se crea la cuenta y no se almacenan sus datos de contacto.
E2 · Baja de la cuenta: se eliminan los datos de contacto y se conserva solo el registro de auditoría, sin datos personales (RNF-S-4).

- **Datos involucrados:** Usuario (nombre, correo institucional, rol y centros asignados) y registro de la aceptación.
- **Reglas de negocio aplicables:** — (base de licitud y finalidad declaradas en §5.3)

**Criterios de aceptación (Gherkin):**

```gherkin
Escenario: Alta sin aceptación
Dado un funcionario que no ha aceptado la finalidad declarada en §5.3
Cuando el administrador intenta crear su cuenta
Entonces el sistema no la crea
Y no almacena su nombre ni su correo
```

- **RNF asociados:** RNF-S-1, RNF-S-2, RNF-S-4, RNF-S-5

