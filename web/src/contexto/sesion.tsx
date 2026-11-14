import { createContext, useContext, useEffect, useState } from 'react';
import type { ReactNode } from 'react';
import type { Usuario } from '../tipos/index.ts';
import { cerrarSesion, obtenerSesion } from '../servicios/sesion.ts';

// Sesión del usuario en la web. La sesión vive en una cookie httpOnly que pone la API (RNF-S-1), así que aquí
// solo se guarda el usuario en memoria; al recargar la página se le pregunta a la API con GET /auth/yo.
// (Patrón derivado de ing-software2, licencia MIT: ver web/LICENSE-ing-software2.)

interface ContextoSesion {
    usuario: Usuario | null;
    autenticado: boolean;
    cargando: boolean;
    iniciar: (usuario: Usuario) => void;
    cerrar: () => Promise<void>;
}

const Contexto = createContext<ContextoSesion | undefined>(undefined);

export const ProveedorSesion = ({ children }: { children: ReactNode }) => {
    const [usuario, setUsuario] = useState<Usuario | null>(null);
    const [cargando, setCargando] = useState<boolean>(true);

    useEffect(() => {
        let vigente = true;
        obtenerSesion().then((encontrado) => {
            if (!vigente) return;
            setUsuario(encontrado);
            setCargando(false);
        });
        return () => { vigente = false; };
    }, []);

    const iniciar = (nuevo: Usuario) => setUsuario(nuevo);

    const cerrar = async () => {
        await cerrarSesion();
        setUsuario(null);
    };

    return (
        <Contexto.Provider value={{ usuario, autenticado: !!usuario, cargando, iniciar, cerrar }}>
            {children}
        </Contexto.Provider>
    );
};

// eslint-disable-next-line react-refresh/only-export-components
export const useSesion = () => {
    const contexto = useContext(Contexto);
    if (contexto === undefined) {
        throw new Error('useSesion debe usarse dentro de un ProveedorSesion');
    }
    return contexto;
};
