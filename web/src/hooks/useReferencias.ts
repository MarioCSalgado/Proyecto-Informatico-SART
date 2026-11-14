import { useEffect, useState } from "react";
import { obtenerReferencias } from "../services/referenciasService.ts";
import type { Referencias } from "../types/index.ts";

type Estado = { referencias: Referencias | null; cargando: boolean; error: boolean };

/** Escala de MP2,5 y comunas desde la API (RNF-M-4). */
export function useReferencias(): Estado {
    const [estado, setEstado] = useState<Estado>({ referencias: null, cargando: true, error: false });

    useEffect(() => {
        let vigente = true;
        obtenerReferencias()
            .then((referencias) => vigente && setEstado({ referencias, cargando: false, error: false }))
            .catch(() => vigente && setEstado({ referencias: null, cargando: false, error: true }));
        return () => { vigente = false; };
    }, []);

    return estado;
}
