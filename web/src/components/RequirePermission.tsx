import LockOutlinedIcon from '@mui/icons-material/LockOutlined';
import type { ReactNode } from 'react';
import type { Permission } from '../auth/permissions.ts';
import { usePermissions } from '../hooks/usePermissions.ts';
import { EmptyState } from './EmptyState.tsx';

type Props = {
  permission: Permission;
  children: ReactNode;
  fallback?: ReactNode;
};

// Envuelve cualquier región (pantalla, sección, botón) que requiera un permiso (patrón de ing-software2).
// Si el usuario no lo tiene, muestra `fallback` o un aviso de acceso restringido. La API también lo niega.
export function RequirePermission({ permission, children, fallback }: Props) {
  const { can } = usePermissions();

  if (can(permission)) return <>{children}</>;
  if (fallback !== undefined) return <>{fallback}</>;

  return (
    <section className="tarjeta" role="alert">
      <EmptyState
        icon={<LockOutlinedIcon />}
        title="Acceso restringido"
        description="Tu rol no tiene permiso para ver esta sección."
      />
    </section>
  );
}
