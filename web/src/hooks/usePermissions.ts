import { useAuth } from '../context/authContext.tsx';
import { hasPermission, type Permission } from '../auth/permissions.ts';

export function usePermissions() {
  const { user } = useAuth();
  const role = user?.rol;

  return {
    role,
    can: (permission: Permission) => hasPermission(role, permission),
  };
}
