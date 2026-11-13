"""Corridas programadas de SART (horarios en ``config/parametros.yaml``, sección ``horarios``).

Va aquí:
- RF-1: ingesta diaria a las 05:00 (DEIS, SINCA, Open-Meteo), copia cruda y panel semanal; marca la
  semana incompleta (RB-4) y la estación de respaldo (RB-5). Actividad 7.
- RF-2 y RF-3: pronóstico y alertas de demanda cada lunes a las 06:00. Actividad 9.
- RF-4: alerta ambiental diaria a las 07:00. Actividad 9.
- RF-5 y RF-6: boletín antes de las 08:00 con nivel, pronóstico y dotación sugerida. Actividad 10.
- RF-15: reenvío a las 24 h y escalamiento al Subdirector a las 48 h (RB-2). Actividad 10.
- RF-8: resumen redactado por el LLM, solo con cifras agregadas (después del MVP).

Las tareas orquestan; los cálculos van en ``sart.dominio``.
"""
