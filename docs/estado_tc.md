# Estado de los casos de prueba

Avance RF-4/RF-5 (27/11/2026): `backend/tests/test_rf4_rf5_integracion.py` verifica el comando ambiental
con envío simulado, persistencia y repetición/recuperación sin duplicados, tanto con pronósticos como con
SINCA, en SQLite aislada. No acredita la sensibilidad real de TC-12 ni el backtest de TC-19; este recorrido
ambiental todavía no se ha validado con PostgreSQL ni SMTP local.

| Caso | RF | Implementado | Pasa | Archivo |
|---|---|---|---|---|
| TC-01 | RF-1 | ☑ | ☑ | `backend/tests/test_tc01_semanas.py` (calendario y semanas que cruzan el año) y `test_tc01_semana_incompleta.py` (marca de RB-4) |
| TC-02 | RF-1 | ☑ | ☑ | `backend/tests/test_tc02_descarga.py` (descargas simuladas, sin red: fuente caída con reintentos, aviso y último dato válido; columna renombrada) y `test_carga_deis_real.py` (archivo real del DEIS, opcional con `SART_DATOS_REALES`) |
| TC-03 | RF-2 | ☑ | ☑ | `backend/tests/test_regresion_backtest.py`: WAPE 14,9 %, bajo la línea base (con los datos reales de `datos/`; en CI se salta) |
| TC-04 | RF-3 | ☑ | ☑ | `backend/tests/test_regresion_backtest.py`: con k = 0,4, precisión 0,73 y sensibilidad 0,66 (cumple ≥ 0,70 y ≥ 0,60) |
| TC-05 | RF-4 | ☑ | ☑ | `backend/tests/test_tc05_mp25.py` |
| TC-06 | RF-5, RF-15 | ☑ | ☑ | Envío: `backend/tests/test_rf5_envio.py` (T4: un correo por usuario, sin duplicar al repetir). Acuse: `backend/tests/test_tc06_acuse.py` y `web/src/tests/acuse.test.tsx` (abrir no confirma, «Confirmar lectura» una sola vez, solo el destinatario). Reenvío y escalamiento con correo de prueba: `backend/tests/test_tc06_reenvio_escalamiento.py` (reenvío una vez a las 24 h, aviso al Subdirector a las 48 h con fecha, fallida → aviso al administrador; pendientes #53 y #54) |
| TC-07 | RF-6 | ☑ | ☑ | `backend/tests/test_tc07_erlang.py`; en la corrida semanal, la dotación se guarda con sus supuestos (`test_rf2_rf3_corrida_semanal.py`, parte 8) |
| TC-08 | RF-7 | ☐ (arnés parcial) | ☐ | Medición local de 5 min en `GET /centros/estado`: 70 usuarios virtuales, sesión compartida, 10,70 solicitudes/s, p95 1.159 ms y 0 fallidas. Falta boletín y Lighthouse móvil/4G. Arnés: `herramientas/pruebas_carga_tc08.mjs` |
| TC-09 | RF-7, RF-9 | ☑ | ☑ | `backend/tests/test_tc09_rf7_estado_centros.py` (RF-7: jefatura solo sus centros, centro ajeno 403 y auditado, subdirector y administrador todos, sin sesión 401). Parte RF-9: `backend/tests/test_tc09_rf9_administracion.py` (las 4 rutas de administración: sin sesión 401, jefatura y subdirector 403) |
| TC-10 | RF-7 | ☐ | ☐ | (con usuarios) |
| TC-11 | RF-2 | ☑ | ☑ | `backend/tests/test_regresion_backtest.py`: el intervalo de 90 % cubre 91,1 % de las semanas (RNF-Q-3; con los datos reales, en CI se salta) |
| TC-12 | RF-4 | ◐ | ☑ | `backend/tests/test_tc12_alerta_ambiental.py`, `test_tc12_integracion.py` y `test_tc12_precision_pronostico.py` (el cálculo de la sensibilidad y la alerta de RF-4). La medición real (`python -m sart.tareas tc12`) necesita pronósticos de MP2,5 guardados durante días con medición en Kingston College; mientras no alcance 0,50, RF-4 usa SINCA (RNF-Q-4) |
| TC-13 | Transversal | ◐ | ☑ | `backend/tests/test_tc13_despliegue.py` (Compose con los 4 servicios dentro de 2 vCPU y 4 GB, planificador con los horarios del YAML, una tarea que falla no frena las demás). Construcción desde cero medida el 17/11: 89 s (≤ 15 min); `docker compose up` probado con `/api/salud` en «ok» y un respaldo desde el planificador. CI: ruff, pruebas y cobertura en cada PR. Falta cronometrar el rollback (≤ 10 min) |
| TC-14 | RF-1 | ☑ | ☑ | `backend/tests/test_tc14_restauracion.py` (simulacro con la base de desarrollo el 14/11: 59 s) |
| TC-15 | RF-11 | ☑ | ☑ | `backend/tests/test_tc15_exportacion_csv.py` (CSV UTF-8 solo con los centros del usuario, centro ajeno 403 auditado, mismas cifras que RF-7, esquema sin columnas de pacientes y contrato OpenAPI) y `web/src/tests/exportacion.test.tsx` |
| TC-16 | RF-16 | ☑ | ☑ | `backend/tests/test_tc16_alta_sin_aceptacion.py` (backend y comando), `test_tc09_rf9_administracion.py` (API: 422 sin aceptación o con versión antigua, nada guardado) y `web/src/tests/administracionUsuarios.test.tsx` (pantalla: sin la casilla no se puede crear) |
| TC-17 | RF-3, RF-9 | ☑ | ☑ | `backend/tests/test_tc17_regla_alerta.py`; de punta a punta en la corrida semanal, con el ajuste de k por el administrador (`test_rf2_rf3_corrida_semanal.py::test_rf3_alerta_solo_por_el_margen_y_cambio_de_k`) |
| TC-18 | RF-8 | ☑ | ☑ | `backend/tests/test_tc18_boletin_llm.py` (con un LLM de prueba: 0 nombres o correos enviados, cifra inventada o nivel cambiado → plantilla) y `test_tc18_boletin_envio.py` (envío: cada jefatura solo sus centros, una vez por semana, el saludo con el nombre no pasa por el LLM). Falta el proveedor real (#12) |
| TC-19 | RF-10 | Parcial | ☐ | `backend/tests/test_tc19_rf10_historial.py` prueba la comparación con lo observado y los permisos, incluido el 403 auditado, con datos controlados en SQLite y PostgreSQL. `web/src/tests/historialAlertas.test.tsx` cubre la pantalla. Falta el backtest con datos reales del invierno de 2025. |
| TC-20 | RF-12 | ☑ | ☑ | `web/src/tests/estadoCentros.test.tsx` (33 centros, coordenadas, nivel, estación y filtros); contrato RF-7 en `backend/tests/test_tc09_rf7_estado_centros.py`; validación visual a 390 px |

