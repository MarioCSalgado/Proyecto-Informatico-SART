import type { ReactNode } from 'react';
import { Navigate, useLocation } from 'react-router';
import { useAuth } from '../context/authContext.tsx';
import { Skeleton } from './Skeleton.tsx';

// Protege las rutas que necesitan sesión: sin sesión, redirige a /login y recuerda a dónde iba
// (lo necesitará el enlace de acuse del correo, RF-15).
export function RequireAuth({ children }: { children: ReactNode }) {
  const { isAuthenticated, loading } = useAuth();
  const location = useLocation();

  if (loading) return <Skeleton height="2rem" />;
  if (!isAuthenticated) return <Navigate to="/login" replace state={{ desde: location.pathname }} />;
  return <>{children}</>;
}
