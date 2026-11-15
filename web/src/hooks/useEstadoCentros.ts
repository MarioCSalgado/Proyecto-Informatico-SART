import { isAxiosError } from "axios";
import { useEffect, useState } from "react";
import { obtenerEstadoCentro, obtenerEstadoCentros } from "../servicios/centros.ts";
import type { EstadoCentro } from "../tipos/index.ts";

type Error = "red" | "sin_acceso" | "no_existe" | null;

function tipoDeError(error: unknown): Error {
    if (isAxiosError(error) && error.response?.status === 403) return "sin_acceso";
    if (isAxiosError(error) && error.response?.status === 404) return "no_existe";
    return "red";
}

/** Estado de los centros visibles para el usuario (RF-7): carga, datos o error. */
export function useEstadoCentros() {
    const [estado, setEstado] = useState<{ centros: EstadoCentro[] | null; cargando: boolean; error: Error }>(
        { centros: null, cargando: true, error: null },
    );
    useEffect(() => {
        let vigente = true;
        obtenerEstadoCentros()
            .then((centros) => vigente && setEstado({ centros, cargando: false, error: null }))
            .catch((e) => vigente && setEstado({ centros: null, cargando: false, error: tipoDeError(e) }));
        return () => { vigente = false; };
    }, []);
    return estado;
}

/** Estado de un centro por su código DEIS (detalle de RF-7, paso 3). */
export function useEstadoCentro(codigo: number) {
    const [estado, setEstado] = useState<{ centro: EstadoCentro | null; cargando: boolean; error: Error }>(
        { centro: null, cargando: true, error: null },
    );
    useEffect(() => {
        let vigente = true;
        obtenerEstadoCentro(codigo)
            .then((centro) => vigente && setEstado({ centro, cargando: false, error: null }))
            .catch((e) => vigente && setEstado({ centro: null, cargando: false, error: tipoDeError(e) }));
        return () => { vigente = false; };
    }, [codigo]);
    return estado;
}
