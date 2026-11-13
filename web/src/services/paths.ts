// Rutas de la API de SART. Las de AUTH se implementan en la actividad 8 (ver TAREAS.md).
const Paths = {
  SALUD: "salud",
  AUTH: {
    SESION: "auth/sesion",          // POST: inicia sesión y pone la cookie
    CERRAR: "auth/cerrar-sesion",   // POST: borra la cookie
    YO: "auth/yo",                  // GET: usuario de la sesión actual
  },
} as const;

export default Paths;
