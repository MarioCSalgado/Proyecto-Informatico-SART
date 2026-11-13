# Arquitectura (C4 nivel 2, presentada en la E2)

```
Jefatura / Subdirector ──HTTPS──▶ Aplicación web (React)  ──JSON──▶  API (FastAPI: 3 roles + auditoría)
Administrador ──────────HTTPS──────────────────────────────────────▶       │ SQL
                                                                             ▼
                         Tareas programadas (Python) ───── SQL ─────▶  Base de datos (PostgreSQL)
                         │  ingesta · modelo · alertas · dotación · notificaciones
                         ├──HTTPS──▶ DEIS (datos.gob.cl), SINCA, Open-Meteo
                         ├──────────▶ Servicio de correo
                         └ ─ ─ ─ ─ ▶ Proveedor de LLM (opcional, RF-8)
```

## Decisiones y su porqué

| Decisión | Motivo | RNF |
|---|---|---|
| Las tareas pesadas corren aparte de la API | La corrida semanal (≤ 15 min) no debe frenar la consulta web | RNF-R-3, RNF-R-1 |
| La API es la única puerta a la base | Un solo lugar para permisos por rol y auditoría | RNF-S-2, RNF-S-4 |
| Todo en Docker | Corre igual en la nube y en un notebook: si la nube falla, la demo sigue | RNF-P-1 |
| Respaldo diario fuera del proveedor de base de datos | No depender de las condiciones de un plan gratuito | RNF-D-2 |

## Roles y permisos (RNF-S-2)

| Rol | Ve | Puede |
|---|---|---|
| Jefatura de urgencia | Solo sus centros asignados | Consultar, confirmar lectura, exportar CSV de sus centros |
| Subdirector asistencial | Todos los centros (lista ordenada por nivel) | Consultar, recibir escalamientos |
| Administrador (MFA) | Todo | Crear cuentas (RF-16), asignar centros, cambiar umbrales y parámetros (RF-9) |
