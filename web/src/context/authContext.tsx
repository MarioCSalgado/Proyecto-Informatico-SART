import { createContext, useContext, useEffect, useState } from 'react';
import type { ReactNode } from 'react';
import type { Usuario } from '../types/index.ts';
import { cerrarSesion, obtenerSesion } from '../services/authService.ts';

// Adaptado de ing-software2: la sesión vive en una cookie httpOnly (RNF-S-1), así que aquí solo se guarda
// el usuario en memoria. Al recargar la página se le pregunta a la API con GET /auth/yo.

interface AuthContextType {
    user: Usuario | null;
    isAuthenticated: boolean;
    loading: boolean;
    login: (user: Usuario) => void;
    logout: () => Promise<void>;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export const AuthProvider = ({ children }: { children: ReactNode }) => {
    const [user, setUser] = useState<Usuario | null>(null);
    const [loading, setLoading] = useState<boolean>(true);

    useEffect(() => {
        let vigente = true;
        obtenerSesion().then((usuario) => {
            if (!vigente) return;
            setUser(usuario);
            setLoading(false);
        });
        return () => { vigente = false; };
    }, []);

    const login = (nuevo: Usuario) => setUser(nuevo);

    const logout = async () => {
        await cerrarSesion();
        setUser(null);
    };

    return (
        <AuthContext.Provider value={{ user, isAuthenticated: !!user, loading, login, logout }}>
            {children}
        </AuthContext.Provider>
    );
};

// eslint-disable-next-line react-refresh/only-export-components
export const useAuth = () => {
    const context = useContext(AuthContext);
    if (context === undefined) {
        throw new Error('useAuth debe ser utilizado dentro de un AuthProvider');
    }
    return context;
};
