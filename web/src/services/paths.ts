// Rutas de la API de SART.
const Paths = {
  SALUD: "salud",
  REFERENCIAS: "referencias",  // GET: escala de MP2,5 y comunas (parametros.yaml)
  AUTH: {
    SESION: "auth/sesion",          // POST: inicia sesión y pone la cookie
    CERRAR: "auth/cerrar-sesion",   // POST: borra la cookie
    YO: "auth/yo",                  // GET: usuario de la sesión actual
  },
} as const;

export default Paths;
