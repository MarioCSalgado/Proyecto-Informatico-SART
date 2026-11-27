# Validación de integración T4 → T5 → T8

Registro del 26/11/2026 (America/Santiago). Rama: `test/t4-t5-t8-integracion`.
Referencia de las pruebas: commit `67fa0ae` y sus cuatro commits anteriores de esta rama.
IDs: RF-5, RF-15, RF-10 y TC-06; evidencia parcial para TC-19.

## Pruebas automatizadas

| Entorno | Alcance | Resultado de la ejecución local |
|---|---|---|
| SQLite en memoria | Selección de pruebas relacionadas: envío simulado, acuse por API, historial, reenvío y escalamiento con tiempo simulado, fallos, permisos y auditoría. Incluye la conservación de umbrales históricos ante ajustes de T7. | **84 pruebas aprobadas**. |
| PostgreSQL 16.16 | Recorrido principal con `crear_base_temporal`, esquema migrado, transportador simulado y APIs reales de T5 y T8. Se comprueban estados, fechas y una sola auditoría al repetir la confirmación. | **1 prueba aprobada**, ejecutada por separado. |

La selección de regresión de SQLite y la prueba PostgreSQL suman 85 pruebas aprobadas. Ruff y
`git diff --check` pasaron. Los nuevos recorridos de integración bloquean SMTP real.
Estos resultados corresponden a la selección de pruebas relacionadas del backend.

Archivos de referencia:

- [Recorridos T4 → T5 → T8](../backend/tests/test_tc06_rf10_integracion.py), incluida
  `test_tc06_rf10_recorrido_principal_en_postgresql`.
- [Configuración T7 y conservación del historial](../backend/tests/test_tc17_rf9_configuracion.py), caso
  `test_tc17_rf10_cambiar_umbral_por_api_conserva_el_historial_de_dos_corridas`.

## Demostración visual con SMTP local y Mailpit

Se utilizaron datos sintéticos de `datos/prueba` en la base aislada
`sart_demo_integracion_0810979b`, con backend en 8001, frontend en 5174, SMTP local en 1025 y bandeja
Mailpit en 8025. Se ajustó un umbral exclusivamente en la base demo para garantizar una alerta.
La preparación conservó la base habitual `sart`, el código de producción y los archivos `.env`.

Mailpit recibió dos correos, dirigidos a las cuentas demo de jefatura y subdirección. La usuaria realizó
personalmente la confirmación desde la interfaz de acuse y comprobó en `/historial-alertas` el estado
**«Confirmada»**, con su fecha y hora. Este resultado visual fue comunicado por la usuaria; no se adjuntan
capturas a este registro.

| Dato observado en pantalla | Valor |
|---|---|
| Centro | Centro de demostración, código 100001 |
| Semana objetivo | SE 40 de 2026 |
| Pronóstico mostrado | 516 consultas |
| Dotación sugerida | 2 profesionales |
| Notificación y acuse | Confirmada, con fecha y hora visibles |

Esta demostración utilizó el envío SMTP de SART hacia Mailpit, sin correos externos. Cubre el recorrido
principal; los reenvíos, escalamientos, fallos y permisos se verificaron mediante las pruebas automatizadas.

## Alcance y pendiente de aceptación

La integración queda validada con datos controlados y sintéticos. **TC-19 sigue parcial y pendiente de
aceptación**: falta reproducir las alertas del invierno de 2025 con datos reales y comparar cada emisión
con las consultas observadas. La demostración de la SE 40 de 2026 no sustituye ese backtest ni acredita
la capacidad predictiva con datos reales.
