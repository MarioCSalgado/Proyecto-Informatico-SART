import type { ReactNode } from 'react';
import { usePermissions } from '../hooks/usePermissions.ts';
import type { Permission } from '../auth/permissions.ts';

type Props = {
  permission: Permission;
  children: ReactNode;
  fallback?: ReactNode;
};

// Envuelve cualquier región (pantalla, sección, botón) que requiera un permiso (patrón de ing-software2).
// Si el usuario no lo tiene, muestra `fallback` o un aviso genérico de acceso restringido.
export function RequirePermission({ permission, children, fallback }: Props) {
  const { can } = usePermissions();

  if (can(permission)) return <>{children}</>;
  if (fallback !== undefined) return <>{fallback}</>;

  return (
    <div style={{ padding: '2rem', textAlign: 'center' }} role="alert">
      <h2>Acceso restringido</h2>
      <p>Tu rol no tiene permiso para ver esta sección.</p>
    </div>
  );
}
