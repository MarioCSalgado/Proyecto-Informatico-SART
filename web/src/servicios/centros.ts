import clienteApi from "./clienteApi.ts";
import RUTAS_API from "./rutasApi.ts";
import type { EstadoCentro } from "../tipos/index.ts";

// Servicio de RF-7. Patrón para los demás servicios: una función por ruta, que valida la forma de la respuesta
// y lanza un error si no es la esperada (así la pantalla muestra su estado de error en vez de romperse).

function esEstadoCentro(dato: unknown): dato is EstadoCentro {
    const d = dato as Partial<EstadoCentro> | null;
    return !!d && typeof d.centro?.codigo_deis === "number" && !!d.mp25 && Array.isArray(d.ultimas_semanas);
}

/** GET /centros/estado: los centros que el usuario puede ver, ya ordenados por nivel (la API filtra por rol). */
export async function obtenerEstadoCentros(): Promise<EstadoCentro[]> {
    const { data } = await clienteApi.get(RUTAS_API.CENTROS.ESTADO);
    if (!Array.isArray(data) || !data.every(esEstadoCentro)) {
        throw new Error("Respuesta de /centros/estado inesperada");
    }
    return data;
}

/** GET /centros/{codigo}/estado. La API responde 403 si el centro no está asignado (RF-7 E2). */
export async function obtenerEstadoCentro(codigo: number): Promise<EstadoCentro> {
    const { data } = await clienteApi.get(RUTAS_API.CENTROS.DETALLE(codigo));
    if (!esEstadoCentro(data)) throw new Error("Respuesta del estado del centro inesperada");
    return data;
}
