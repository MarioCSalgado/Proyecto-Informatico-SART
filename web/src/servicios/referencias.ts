import clienteApi from "./clienteApi.ts";
import RUTAS_API from "./rutasApi.ts";
import type { Referencias } from "../tipos/index.ts";

/** GET /referencias. Lanza un error si la respuesta no trae lo esperado. */
export async function obtenerReferencias(): Promise<Referencias> {
    const respuesta = await clienteApi.get(RUTAS_API.REFERENCIAS);
    const datos = respuesta.data as Partial<Referencias> | undefined;
    if (!datos || !Array.isArray(datos.mp25_niveles) || !Array.isArray(datos.comunas)) {
        throw new Error("Respuesta de /referencias inesperada");
    }
    return { ...datos, mp25_niveles: datos.mp25_niveles, comunas: datos.comunas };
}
