## Qué hace

<!-- Una o dos frases: qué cambia y por qué. -->

## IDs que cubre

<!-- RF-x, RNF-x, RB-x, TC-x. Ejemplo: RF-5, TC-06. Tarea de docs/tareas_equipo.md: T… -->

Closes #

<!-- Número del issue de la tarea (columna «Issue» de docs/tareas_equipo.md). «Closes #N» va en inglés
     porque GitHub solo reconoce esa palabra: así cierra el issue solo al unir el PR. Si el PR no corresponde
     a un issue, borrar la línea. -->

## Cómo se probó

<!-- Pruebas nuevas o cambiadas (archivo y caso) y lo que revisaste a mano. -->

- [ ] `ruff check .` y `pytest` en `backend/`
- [ ] `npm run lint`, `npm run build` y `npx vitest run` en `web/` (si toca la web)

## Capturas

<!-- Si toca pantallas: antes y después. Si no, borrar esta sección. -->

## Revisión

- [ ] Sin datos de pacientes en la base, los logs ni las respuestas (RNF-S-5)
- [ ] Sin supuestos escritos en el código: se leen de `config/parametros.yaml` (RNF-M-4)
- [ ] Las rutas con datos de un centro revisan el rol en la API (RNF-S-2)
- [ ] El nivel no se muestra solo con color (RNF-U-1)
- [ ] No sube `.env`, `datos/` (salvo `datos/prueba/`), `respaldos/` ni nada de `referencia/`
- [ ] Tarea marcada en `docs/tareas_equipo.md` y, si aplica, TC en `docs/estado_tc.md`
- [ ] Si se aparta de la especificación: anotado en `docs/pendientes_informe.md` y explicado aquí
