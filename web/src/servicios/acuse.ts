import clienteApi from "./clienteApi.ts";
import RUTAS_API from "./rutasApi.ts";
import type { Acuse } from "../tipos/index.ts";

// Servicio de RF-15. La API responde 404 si el enlace no es de una notificación de la cuenta (pendientes #34).

export async function obtenerAcuse(token: string): Promise<Acuse> {
    return (await clienteApi.get(RUTAS_API.ACUSE.VER(token))).data;
}

export async function confirmarLectura(token: string): Promise<Acuse> {
    return (await clienteApi.post(RUTAS_API.ACUSE.CONFIRMAR(token))).data;
}
