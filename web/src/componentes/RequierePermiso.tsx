import LockOutlinedIcon from '@mui/icons-material/LockOutlined';
import type { ReactNode } from 'react';
import type { Permiso } from '../acceso/permisos.ts';
import { usePermisos } from '../hooks/usePermisos.ts';
import { EstadoVacio } from './EstadoVacio.tsx';

type Props = {
  permiso: Permiso;
  children: ReactNode;
  alternativa?: ReactNode; // lo que se muestra sin el permiso; por defecto, «Acceso restringido»
};

// Envuelve cualquier región (pantalla, sección, botón) que requiera un permiso (RNF-S-2). La API también lo
// niega: esto solo decide qué se muestra.
export function RequierePermiso({ permiso, children, alternativa }: Props) {
  const { puede } = usePermisos();

  if (puede(permiso)) return <>{children}</>;
  if (alternativa !== undefined) return <>{alternativa}</>;

  return (
    <section className="tarjeta" role="alert">
      <EstadoVacio
        icono={<LockOutlinedIcon />}
        titulo="Acceso restringido"
        descripcion="Tu rol no tiene permiso para ver esta sección."
      />
    </section>
  );
}
