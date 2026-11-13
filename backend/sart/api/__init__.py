"""API de SART (FastAPI): única puerta de entrada a la base (RNF-S-2, RNF-S-4).

Va aquí:
- RF-7: consulta del estado de alerta de los centros asignados (actividad 8).
- RF-9: administración de usuarios, centros asignados, umbrales y supuestos (actividad 8).
- RF-16: alta de cuentas con aceptación registrada de la finalidad (actividad 8).
- RF-15: página y endpoint de acuse «Confirmar lectura» (actividad 10).
- RF-11: exportación CSV de los centros del usuario (después del MVP).
- Transversal: autenticación Argon2id + JWT en cookie httpOnly y MFA para administradores (RNF-S-1),
  3 roles con mínimo privilegio (RNF-S-2) y auditoría de 12 meses (RNF-S-4).
"""
