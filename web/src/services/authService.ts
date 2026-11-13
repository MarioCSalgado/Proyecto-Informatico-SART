import axios from "axios";
import axiosInstance from "./axiosInstance.ts";
import Paths from "./paths.ts";
import type { Usuario } from "../types/index.ts";

export class ErrorInicioSesion extends Error {}

/** POST /auth/sesion. Devuelve el usuario; la cookie la guarda el navegador. */
export async function iniciarSesion(correo: string, contrasena: string): Promise<Usuario> {
    try {
        const respuesta = await axiosInstance.post(Paths.AUTH.SESION, { correo, contrasena });
        return respuesta.data.usuario as Usuario;
    } catch (error) {
        if (axios.isAxiosError(error)) {
            if (error.response?.status === 404) {
                throw new ErrorInicioSesion("No se encontró el servicio de inicio de sesión. ¿Está corriendo la API?");
            }
            if (error.response?.status === 401) {
                throw new ErrorInicioSesion("Correo o contraseña incorrectos.");
            }
            const detalle = (error.response?.data as { detail?: unknown } | undefined)?.detail;
            if (error.response?.status === 403 && typeof detalle === "string") {
                // p. ej. administradores sin MFA (RNF-S-1): la API explica el motivo
                throw new ErrorInicioSesion(detalle);
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
