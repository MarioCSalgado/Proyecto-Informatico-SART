// Rutas de la API de SART.
const RUTAS_API = {
  SALUD: "salud",
  REFERENCIAS: "referencias",  // GET: escala de MP2,5 y comunas (parametros.yaml)
  CENTROS: {
    ESTADO: "centros/estado",  // GET: estado de los centros que el usuario puede ver (RF-7)
    DETALLE: (codigo: number) => `centros/${codigo}/estado`,  // GET: un centro (403 si es ajeno)
  },
  AUTH: {
    SESION: "auth/sesion",          // POST: inicia sesión y pone la cookie
    CERRAR: "auth/cerrar-sesion",   // POST: borra la cookie
    YO: "auth/yo",                  // GET: usuario de la sesión actual
  },
} as const;

export default RUTAS_API;
