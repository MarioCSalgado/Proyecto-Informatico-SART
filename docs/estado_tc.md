# Estado de los casos de prueba

| Caso | RF | Implementado | Pasa | Archivo |
|---|---|---|---|---|
| TC-01 | RF-1 | ☑ | ☑ | `backend/tests/test_tc01_semanas.py` (calendario y semanas que cruzan el año) y `test_tc01_semana_incompleta.py` (marca de RB-4) |
| TC-02 | RF-1 | ☐ | ☐ | |
| TC-03 | RF-2 | ☑ | ☑ | `backend/tests/test_regresion_backtest.py`: WAPE 14,9 %, bajo la línea base (con los datos reales de `datos/`; en CI se salta) |
| TC-04 | RF-3 | ☑ | ☑ | `backend/tests/test_regresion_backtest.py`: con k = 0,4, precisión 0,73 y sensibilidad 0,66 (cumple ≥ 0,70 y ≥ 0,60) |
| TC-05 | RF-4 | ☑ | ☑ | `backend/tests/test_tc05_mp25.py` |
| TC-06 | RF-5, RF-15 | ◐ | ☑ | `backend/tests/test_tc06_acuse.py` y `web/src/tests/acuse.test.tsx` (parte sin correo: abrir no confirma, «Confirmar lectura» una sola vez, solo el destinatario, plazos de RB-2 con `paso_rb2`). Falta el envío, el reenvío y el aviso al Subdirector con el correo de RF-5 (T4) |
| TC-07 | RF-6 | ☑ | ☑ | `backend/tests/test_tc07_erlang.py`; en la corrida semanal, la dotación se guarda con sus supuestos (`test_rf2_rf3_corrida_semanal.py`, parte 8) |
| TC-08 | RF-7 | ☐ | ☐ | |
| TC-09 | RF-7, RF-9 | ☑ | ☑ | `backend/tests/test_tc09_rf7_estado_centros.py` (RF-7: jefatura solo sus centros, centro ajeno 403 y auditado, subdirector y administrador todos, sin sesión 401). Parte RF-9: `backend/tests/test_tc09_rf9_administracion.py` (las 4 rutas de administración: sin sesión 401, jefatura y subdirector 403) |
| TC-10 | RF-7 | ☐ | ☐ | (con usuarios) |
| TC-11 | RF-2 | ☑ | ☑ | `backend/tests/test_regresion_backtest.py`: el intervalo de 90 % cubre 91,1 % de las semanas (RNF-Q-3; con los datos reales, en CI se salta) |
| TC-12 | RF-4 | ☐ | ☐ | |
| TC-13 | Transversal | ☐ | ☐ | |
| TC-14 | RF-1 | ☑ | ☑ | `backend/tests/test_tc14_restauracion.py` (simulacro con la base de desarrollo el 14/11: 59 s) |
| TC-15 | RF-11 | ☐ | ☐ | |
| TC-16 | RF-16 | ☑ | ☑ | `backend/tests/test_tc16_alta_sin_aceptacion.py` (backend y comando), `test_tc09_rf9_administracion.py` (API: 422 sin aceptación o con versión antigua, nada guardado) y `web/src/tests/administracionUsuarios.test.tsx` (pantalla: sin la casilla no se puede crear) |
| TC-17 | RF-3, RF-9 | ☑ | ☑ | `backend/tests/test_tc17_regla_alerta.py`; de punta a punta en la corrida semanal, con el ajuste de k por el administrador (`test_rf2_rf3_corrida_semanal.py::test_rf3_alerta_solo_por_el_margen_y_cambio_de_k`) |
| TC-18 | RF-8 | ☑ | ☑ | `backend/tests/test_tc18_boletin_llm.py` (con un LLM de prueba: 0 nombres o correos enviados, cifra inventada o nivel cambiado → plantilla). Falta el proveedor real (#12) |
| TC-19 | RF-10 | ☐ | ☐ | |
| TC-20 | RF-12 | ☐ | ☐ | |

