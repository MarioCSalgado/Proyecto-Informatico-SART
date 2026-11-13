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
