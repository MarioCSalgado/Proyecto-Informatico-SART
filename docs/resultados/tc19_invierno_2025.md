# TC-19 · Historial de alertas con el invierno 2025 (RF-10)

Generado con `herramientas/reproducir_invierno.py` sobre una copia de la base con los datos públicos reales (no
editar a mano). Semanas objetivo del 2025-05-04 al 2025-09-28; umbrales de RB-3 calculados con datos hasta el
2025-02-23 (recálculo de marzo de 2025); cada semana se pronosticó solo con las consultas hasta su fecha
de corte, con el k del sistema. Semana alta: total observado sobre el umbral de alerta original del centro.

- **22 semanas**, 726 pronósticos (726 con observación válida).
- **45 alertas ALERTA** y 96 en atención; 28 semanas realmente altas.
- Aciertos: 14 → **precisión 0,311** y **sensibilidad 0,500** en
  el invierno (RNF-Q-2 pide ≥ 0,70 y ≥ 0,60 sobre el período de prueba completo).
- **Historial (RF-10):** 141 filas (ALERTA y atención); 0 con un
  observado o un nivel distinto del cálculo independiente.

## Corridas

- Pronóstico de la SE 19 de 2025 (fecha de corte: SE 18 de 2025): 33 centros (5 ALERTA, 10 atención, 18 normal); 15 alertas emitidas.
- Pronóstico de la SE 20 de 2025 (fecha de corte: SE 19 de 2025): 33 centros (1 ALERTA, 10 atención, 22 normal); 11 alertas emitidas.
- Pronóstico de la SE 21 de 2025 (fecha de corte: SE 20 de 2025): 33 centros (3 ALERTA, 8 atención, 22 normal); 11 alertas emitidas.
- Pronóstico de la SE 22 de 2025 (fecha de corte: SE 21 de 2025): 33 centros (9 ALERTA, 10 atención, 14 normal); 19 alertas emitidas.
- Pronóstico de la SE 23 de 2025 (fecha de corte: SE 22 de 2025): 33 centros (4 ALERTA, 4 atención, 25 normal); 8 alertas emitidas.
- Pronóstico de la SE 24 de 2025 (fecha de corte: SE 23 de 2025): 33 centros (5 ALERTA, 6 atención, 22 normal); 11 alertas emitidas.
- Pronóstico de la SE 25 de 2025 (fecha de corte: SE 24 de 2025): 33 centros (2 ALERTA, 4 atención, 27 normal); 6 alertas emitidas.
- Pronóstico de la SE 26 de 2025 (fecha de corte: SE 25 de 2025): 33 centros (0 ALERTA, 3 atención, 30 normal); 3 alertas emitidas.
- Pronóstico de la SE 27 de 2025 (fecha de corte: SE 26 de 2025): 33 centros (0 ALERTA, 2 atención, 31 normal); 2 alertas emitidas.
- Pronóstico de la SE 28 de 2025 (fecha de corte: SE 27 de 2025): 33 centros (0 ALERTA, 0 atención, 33 normal); 0 alertas emitidas.
- Pronóstico de la SE 29 de 2025 (fecha de corte: SE 28 de 2025): 33 centros (0 ALERTA, 0 atención, 33 normal); 0 alertas emitidas.
- Pronóstico de la SE 30 de 2025 (fecha de corte: SE 29 de 2025): 33 centros (0 ALERTA, 0 atención, 33 normal); 0 alertas emitidas.
- Pronóstico de la SE 31 de 2025 (fecha de corte: SE 30 de 2025): 33 centros (0 ALERTA, 3 atención, 30 normal); 3 alertas emitidas.
- Pronóstico de la SE 32 de 2025 (fecha de corte: SE 31 de 2025): 33 centros (0 ALERTA, 0 atención, 33 normal); 0 alertas emitidas.
- Pronóstico de la SE 33 de 2025 (fecha de corte: SE 32 de 2025): 33 centros (0 ALERTA, 0 atención, 33 normal); 0 alertas emitidas.
- Pronóstico de la SE 34 de 2025 (fecha de corte: SE 33 de 2025): 33 centros (0 ALERTA, 3 atención, 30 normal); 3 alertas emitidas.
- Pronóstico de la SE 35 de 2025 (fecha de corte: SE 34 de 2025): 33 centros (1 ALERTA, 5 atención, 27 normal); 6 alertas emitidas.
- Pronóstico de la SE 36 de 2025 (fecha de corte: SE 35 de 2025): 33 centros (2 ALERTA, 4 atención, 27 normal); 6 alertas emitidas.
- Pronóstico de la SE 37 de 2025 (fecha de corte: SE 36 de 2025): 33 centros (2 ALERTA, 10 atención, 21 normal); 12 alertas emitidas.
- Pronóstico de la SE 38 de 2025 (fecha de corte: SE 37 de 2025): 33 centros (5 ALERTA, 9 atención, 19 normal); 14 alertas emitidas.
- Pronóstico de la SE 39 de 2025 (fecha de corte: SE 38 de 2025): 33 centros (1 ALERTA, 2 atención, 30 normal); 3 alertas emitidas.
- Pronóstico de la SE 40 de 2025 (fecha de corte: SE 39 de 2025): 33 centros (5 ALERTA, 3 atención, 25 normal); 8 alertas emitidas.

## Alertas ALERTA frente a lo observado

| Semana | Centro | Pronóstico + margen | Umbral de alerta | Observado | ¿Semana alta? |
|---|---|---|---|---|---|
| SE 19 de 2025 | Hospital Las Higueras (Talcahuano) | 325,2 | 323,0 | 285 | no |
| SE 19 de 2025 | SAPU O'HIGGINS | 217,1 | 209,5 | 240 | sí |
| SE 19 de 2025 | SAR Chiguayante | 726,0 | 651,0 | 643 | no |
| SE 19 de 2025 | SAR San Pedro | 439,5 | 436,0 | 376 | no |
| SE 19 de 2025 | SAR San Vicente | 332,3 | 322,5 | 281 | no |
| SE 20 de 2025 | SAPU O'HIGGINS | 240,4 | 209,5 | 198 | no |
| SE 21 de 2025 | SAR Chiguayante | 814,7 | 651,0 | 682 | sí |
| SE 21 de 2025 | SAR San Pedro | 488,4 | 436,0 | 499 | sí |
| SE 21 de 2025 | SUR Dichato | 122,3 | 115,5 | 112 | no |
| SE 22 de 2025 | Hospital Clínico Regional Dr. Guillermo Grant Benavente (Concepción) | 396,9 | 382,0 | 313 | no |
| SE 22 de 2025 | Hospital Las Higueras (Talcahuano) | 372,4 | 323,0 | 314 | no |
| SE 22 de 2025 | SAPU Juan Soto Fernández | 252,0 | 250,5 | 205 | no |
| SE 22 de 2025 | SAPU La Floresta | 355,5 | 342,0 | 258 | no |
| SE 22 de 2025 | SAPU O'HIGGINS | 245,0 | 209,5 | 192 | no |
| SE 22 de 2025 | SAPU Paulina Avendaño Pereda | 217,4 | 208,5 | 204 | no |
| SE 22 de 2025 | SAR Penco | 326,7 | 306,0 | 264 | no |
| SE 22 de 2025 | SAR San Pedro | 501,8 | 436,0 | 403 | no |
| SE 22 de 2025 | SUR Dichato | 117,7 | 115,5 | 135 | sí |
| SE 23 de 2025 | Hospital Las Higueras (Talcahuano) | 335,0 | 323,0 | 329 | sí |
| SE 23 de 2025 | SAPU Paulina Avendaño Pereda | 227,0 | 208,5 | 216 | sí |
| SE 23 de 2025 | SAR Chiguayante | 681,2 | 651,0 | 695 | sí |
| SE 23 de 2025 | SUR Dichato | 136,4 | 115,5 | 151 | sí |
| SE 24 de 2025 | Hospital Las Higueras (Talcahuano) | 347,4 | 323,0 | 326 | sí |
| SE 24 de 2025 | SAPU Paulina Avendaño Pereda | 234,4 | 208,5 | 147 | no |
| SE 24 de 2025 | SAR Chiguayante | 661,4 | 651,0 | 674 | sí |
| SE 24 de 2025 | SAR San Pedro | 454,1 | 436,0 | 416 | no |
| SE 24 de 2025 | SUR Dichato | 146,5 | 115,5 | 94 | no |
| SE 25 de 2025 | Hospital Las Higueras (Talcahuano) | 344,4 | 323,0 | 297 | no |
| SE 25 de 2025 | SAPU O'HIGGINS | 224,5 | 209,5 | 189 | no |
| SE 35 de 2025 | Hospital Las Higueras (Talcahuano) | 333,8 | 323,0 | 274 | no |
| SE 36 de 2025 | SAPU O'HIGGINS | 219,6 | 209,5 | 219 | sí |
| SE 36 de 2025 | SAPU Paulina Avendaño Pereda | 210,5 | 208,5 | 179 | no |
| SE 37 de 2025 | SAPU O'HIGGINS | 224,4 | 209,5 | 223 | sí |
| SE 37 de 2025 | SAR Chiguayante | 741,7 | 651,0 | 755 | sí |
| SE 38 de 2025 | SAPU O'HIGGINS | 226,2 | 209,5 | 163 | no |
| SE 38 de 2025 | SAPU Paulina Avendaño Pereda | 227,9 | 208,5 | 122 | no |
| SE 38 de 2025 | SAR Chiguayante | 728,3 | 651,0 | 658 | sí |
| SE 38 de 2025 | SAR San Pedro | 444,7 | 436,0 | 358 | no |
| SE 38 de 2025 | SUR Dichato | 118,2 | 115,5 | 75 | no |
| SE 39 de 2025 | SAR Penco | 306,3 | 306,0 | 255 | no |
| SE 40 de 2025 | SAPU Bellavista | 235,6 | 223,0 | 153 | no |
| SE 40 de 2025 | SAPU O'HIGGINS | 215,7 | 209,5 | 188 | no |
| SE 40 de 2025 | SAR Chiguayante | 675,2 | 651,0 | 557 | no |
| SE 40 de 2025 | SAR Tucapel | 451,6 | 429,5 | 389 | no |
| SE 40 de 2025 | SUR Dichato | 133,5 | 115,5 | 103 | no |
