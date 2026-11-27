# Comparación de modelos de pronóstico (CI-1, RF-2, RNF-Q-1 a Q-3)

Generado con `herramientas/comparar_modelos.py` (no editar a mano; la conclusión está en
`docs/pendientes_informe.md` #60). Panel del sistema armado desde los datos públicos reales.

- **Prueba:** 4972 semanas-centro de 33 centros, del 2023-12-31 al 2026-11-15
  (las mismas filas para todos los modelos y líneas base).
- **Calibración (sin la prueba):** entrenamiento con los años anteriores a 2023 (sin 2020 ni 2021) y validación
  en 2023 (1716 semanas-centro). α de la Binomial Negativa con la mejor log-verosimilitud en la
  validación: **α = 0,03** (α = 0,005: -10533 · α = 0,01: -9633 · α = 0,02: -9101 · α = 0,03: -8973 · α = 0,05: -8978 · α = 0,08: -9114 · α = 0,12: -9306 · α = 0,2: -9620). Margen k con la mayor sensibilidad entre los que dan precisión
  ≥ 0,7 en la validación: **k = 0,4** (quasi-Poisson) y **k = 0,3** (Binomial
  Negativa). Después se reentrena con todos los años anteriores a 2024.
- Semana alta: consultas observadas sobre el umbral de alerta del centro (p90 de RB-3 con el entrenamiento).

| Modelo | Regla | WAPE | Precisión | Sensibilidad | Alertas | Semanas altas | Cobertura 90 % |
|---|---|---|---|---|---|---|---|
| GLM quasi-Poisson (actual) | k calibrado = 0,4 | 14,90 % | 0,709 | 0,652 | 323 | 351 | 0,914 |
| GLM quasi-Poisson (actual) | k del sistema = 0,4 | 14,90 % | 0,709 | 0,652 | 323 | 351 | 0,914 |
| GLM Binomial Negativa | k calibrado = 0,3 | 14,74 % | 0,743 | 0,641 | 303 | 351 | 0,888 |
| GLM Binomial Negativa | k del sistema = 0,4 | 14,74 % | 0,699 | 0,661 | 332 | 351 | 0,888 |
| Línea base: semana anterior | sin margen | 14,87 % | 0,683 | 0,681 | 350 | 351 | — |
| Línea base: misma semana del año anterior | sin margen | 24,92 % | 0,459 | 0,507 | 388 | 351 | — |
