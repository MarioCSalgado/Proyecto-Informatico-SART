"""Persistencia de SART: modelos SQLAlchemy 2 y migraciones Alembic sobre PostgreSQL 16 (actividad 6).

Va aquí: las entidades de ``docs/especificacion/05_datos.md`` (Zona, Estación, Medición, Centro_Salud,
Alerta de demanda y ambiental, Notificación, Pronóstico, Usuario, Consulta_semanal), más el registro de
auditoría (RNF-S-4) y la aceptación de la finalidad (RF-16).

Regla que no se negocia: 0 datos de pacientes (RNF-S-5, TC-15). Los conteos son agregados por centro y semana.
"""
