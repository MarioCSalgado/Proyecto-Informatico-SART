// Única fuente de verdad de las reglas de acceso por rol (RNF-S-2). Patrón tomado de ing-software2.
// Cada permiso es una acción o región de la interfaz. Para agregar uno, se agrega aquí con sus roles;
// no se dispersan listas de roles por los componentes.
// La API vuelve a revisar cada permiso: esto solo decide qué se muestra.

export const ROLES = ['Jefatura', 'Subdirector', 'Administrador'] as const;
export type Role = (typeof ROLES)[number];

export const PERMISSIONS = {
  // RF-7: consultar el estado de alerta (la Jefatura solo ve sus centros asignados; lo filtra la API)
  ver_estado_centros:     ['Jefatura', 'Subdirector', 'Administrador'],
  ver_mi_centro:          ['Jefatura'],
  ver_todos_los_centros:  ['Subdirector', 'Administrador'],

  // RF-15: acuse con el botón «Confirmar lectura»
  confirmar_lectura:      ['Jefatura'],

  // RF-11: exportación CSV de sus centros
  exportar_csv:           ['Jefatura'],

  // RF-9 y RF-16: cuentas, centros asignados, umbrales y supuestos (con MFA, RNF-S-1)
  administrar_cuentas:    ['Administrador'],
  cambiar_parametros:     ['Administrador'],
} as const satisfies Record<string, readonly Role[]>;

export type Permission = keyof typeof PERMISSIONS;

// Función pura: usarla fuera de componentes. Dentro de componentes, usar el hook usePermissions().
export function hasPermission(role: Role | undefined | null, permission: Permission): boolean {
  if (!role) return false;
  return (PERMISSIONS[permission] as readonly string[]).includes(role);
}
