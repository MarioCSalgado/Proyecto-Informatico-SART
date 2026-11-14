import type { ReactNode } from 'react';
import { Navigate, useLocation } from 'react-router';
import { useSesion } from '../contexto/sesion.tsx';
import { BloqueCarga } from './BloqueCarga.tsx';

// Protege las rutas que necesitan sesión: sin sesión, lleva al inicio de sesión y recuerda a dónde se iba
// (después de entrar se vuelve ahí si el rol puede verlo; lo usará el enlace de acuse del correo, RF-15).
export function RequiereSesion({ children }: { children: ReactNode }) {
  const { autenticado, cargando } = useSesion();
  const ubicacion = useLocation();

  if (cargando) return <BloqueCarga alto="2rem" />;
  if (!autenticado) return <Navigate to="/login" replace state={{ desde: ubicacion.pathname }} />;
  return <>{children}</>;
}
