const environment = {
    // Por defecto, el mismo origen que la página: en desarrollo, Vite reenvía /api a la API (vite.config.ts),
    // así la cookie de sesión funciona sin CORS. En producción, el proxy inverso hace lo mismo.
    API_URL: import.meta.env.VITE_API_URL ?? "/api",
} as const

export default environment;
