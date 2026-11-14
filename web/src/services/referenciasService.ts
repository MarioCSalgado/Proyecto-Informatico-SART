import axiosInstance from "./axiosInstance.ts";
import Paths from "./paths.ts";
import type { Referencias } from "../types/index.ts";

/** GET /referencias. Lanza un error si la respuesta no trae lo esperado. */
export async function obtenerReferencias(): Promise<Referencias> {
    const respuesta = await axiosInstance.get(Paths.REFERENCIAS);
    const datos = respuesta.data as Partial<Referencias> | undefined;
    if (!datos || !Array.isArray(datos.mp25_niveles) || !Array.isArray(datos.comunas)) {
        throw new Error("Respuesta de /referencias inesperada");
    }
    return { mp25_niveles: datos.mp25_niveles, comunas: datos.comunas };
}
