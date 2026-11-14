import { tienePermiso, type Permiso } from '../acceso/permisos.ts';
import { useSesion } from '../contexto/sesion.tsx';

/** Rol del usuario de la sesión y si puede hacer algo (RNF-S-2). */
export function usePermisos() {
  const { usuario } = useSesion();
  const rol = usuario?.rol;

  return {
    rol,
    puede: (permiso: Permiso) => tienePermiso(rol, permiso),
  };
}
