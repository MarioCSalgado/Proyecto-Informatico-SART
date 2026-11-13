"""SART · Sistema de Alerta Respiratoria Temprana.

Paquetes:
- ``sart.api``: API FastAPI, única puerta de entrada a la base (RNF-S-2, RNF-S-4).
- ``sart.tareas``: corridas programadas (ingesta, pronóstico, alertas, notificaciones).
- ``sart.dominio``: lógica pura y probada (semanas, modelo, umbrales, alertas, dotación).
- ``sart.db``: modelos SQLAlchemy y migraciones Alembic.
"""

__version__ = "0.1.0"
