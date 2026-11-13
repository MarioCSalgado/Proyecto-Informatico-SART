"""Lógica de dominio de SART: funciones puras, sin base de datos ni red, y probadas (RNF-M-1 ≥ 70 %).

Va aquí (se migra desde ``notebooks/analisis_informatico5.ipynb``):
- Semanas epidemiológicas del MINSAL (domingo a sábado) y semana incompleta (RF-1, RB-4, TC-01).
- Modelo GLM quasi-Poisson e intervalo de 90 % (RF-2, CI-1, TC-03, TC-11).
- Umbrales por centro: percentiles 75 y 90 de los últimos 3 años válidos (RB-3).
- Regla de alerta con margen k (RF-3, TC-17).
- Clasificación del MP2,5 en 5 niveles (RF-4, RB-1, TC-05).
- Erlang C y dotación mínima (RF-6, CI-2, TC-07).

Todos los supuestos se reciben como argumentos o se leen con ``sart.parametros``; nunca se escriben aquí.
"""
