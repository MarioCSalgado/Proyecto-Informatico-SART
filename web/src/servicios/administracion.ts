import { isAxiosError } from "axios";
import clienteApi from "./clienteApi.ts";
import RUTAS_API from "./rutasApi.ts";
import type { AltaCuenta, Cuenta } from "../tipos/index.ts";

// Servicio de RF-9 y RF-16. Solo el administrador llega aquí; la API niega a los demás (TC-09).

/** Mensaje de la API («detail») para mostrarlo tal cual al administrador; si no hay, uno genérico. */
export function mensajeDeError(error: unknown): string {
    const detalle = isAxiosError(error) ? error.response?.data?.detail : undefined;
    return typeof detalle === "string" ? detalle : "No se pudo completar la acción. Intente nuevamente.";
}

export async function listarCuentas(): Promise<Cuenta[]> {
    const { data } = await clienteApi.get(RUTAS_API.ADMINISTRACION.USUARIOS);
    if (!Array.isArray(data)) throw new Error("Respuesta de /administracion/usuarios inesperada");
    return data;
}

export async function crearCuenta(alta: AltaCuenta): Promise<Cuenta> {
    return (await clienteApi.post(RUTAS_API.ADMINISTRACION.USUARIOS, alta)).data;
}

export async function asignarCentros(id: number, centros: number[]): Promise<Cuenta> {
    return (await clienteApi.put(RUTAS_API.ADMINISTRACION.CENTROS(id), { centros })).data;
}

export async function darDeBaja(id: number): Promise<void> {
    await clienteApi.delete(RUTAS_API.ADMINISTRACION.USUARIO(id));
}
