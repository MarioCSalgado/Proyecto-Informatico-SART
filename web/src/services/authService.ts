import axios from "axios";
import axiosInstance from "./axiosInstance.ts";
import Paths from "./paths.ts";
import type { Usuario } from "../types/index.ts";

export class ErrorInicioSesion extends Error {}

/** Resultado de POST /auth/sesion: sesión abierta, o falta el código MFA (solo administradores, RNF-S-1). */
export type ResultadoInicioSesion =
    | { tipo: "sesion"; usuario: Usuario }
    | { tipo: "mfa_requerido" };

/** POST /auth/sesion. La cookie de sesión la guarda el navegador; el código MFA se envía solo si lo hay. */
export async function iniciarSesion(
    correo: string,
    contrasena: string,
    codigo?: string,
): Promise<ResultadoInicioSesion> {
    try {
        const datos = codigo ? { correo, contrasena, codigo } : { correo, contrasena };
        const respuesta = await axiosInstance.post(Paths.AUTH.SESION, datos);
        if (respuesta.data?.mfa_requerido) return { tipo: "mfa_requerido" };
        return { tipo: "sesion", usuario: respuesta.data.usuario as Usuario };
    } catch (error) {
        if (axios.isAxiosError(error)) {
            const estado = error.response?.status;
            const detalle = (error.response?.data as { detail?: unknown } | undefined)?.detail;
            if (estado === 404) {
                throw new ErrorInicioSesion("No se encontró el servicio de inicio de sesión. ¿Está corriendo la API?");
            }
            // 401 clave o código incorrectos · 403 administrador sin MFA · 429 bloqueado por códigos fallidos
            if ((estado === 401 || estado === 403 || estado === 429) && typeof detalle === "string") {
                throw new ErrorInicioSesion(detalle);
            }
            if (estado === 401) {
                throw new ErrorInicioSesion("Correo o contraseña incorrectos.");
            }
            if (!error.response) {
                throw new ErrorInicioSesion("No se pudo conectar con el servidor. Intente nuevamente.");
            }
        }
        throw new ErrorInicioSesion("Error al iniciar sesión. Intente nuevamente.");
    }
}

/** GET /auth/yo. Devuelve null si no hay sesión (o si la API aún no lo implementa). */
export async function obtenerSesion(): Promise<Usuario | null> {
    try {
        const respuesta = await axiosInstance.get(Paths.AUTH.YO);
        return respuesta.data.usuario as Usuario;
    } catch {
        return null;
    }
}

/** POST /auth/cerrar-sesion. Si falla, la sesión local se cierra igual. */
export async function cerrarSesion(): Promise<void> {
    try {
        await axiosInstance.post(Paths.AUTH.CERRAR);
    } catch {
        // sin acción: el estado local se limpia en el contexto
    }
}
