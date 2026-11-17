// Única fuente de verdad de las reglas de acceso por rol en la web (RNF-S-2). Cada permiso es una acción o
// región de la interfaz; para agregar uno, se agrega aquí con sus roles y no se reparten listas de roles por los
// componentes. La API vuelve a revisar cada permiso (requiere_rol): esto solo decide qué se muestra.
// (Patrón derivado de ing-software2, licencia MIT: ver web/LICENSE-ing-software2.)

export const ROLES = ['Jefatura', 'Subdirector', 'Administrador'] as const;
export type Rol = (typeof ROLES)[number];

export const PERMISOS = {
  // RF-7: consultar el estado de alerta (la Jefatura solo ve sus centros asignados; lo filtra la API)
  ver_estado_centros:     ['Jefatura', 'Subdirector', 'Administrador'],
  ver_mi_centro:          ['Jefatura'],
  ver_todos_los_centros:  ['Subdirector', 'Administrador'],

  // RF-10: el historial aplica el mismo alcance por centro que RF-7.
  ver_historial_alertas:  ['Jefatura', 'Subdirector', 'Administrador'],

  // RF-15: acuse con el botón «Confirmar lectura»
  confirmar_lectura:      ['Jefatura'],

  // RF-11: exportación CSV de sus centros
  exportar_csv:           ['Jefatura'],

  // RF-9 y RF-16: cuentas, centros asignados, umbrales y supuestos (con MFA, RNF-S-1)
  administrar_cuentas:    ['Administrador'],
  cambiar_parametros:     ['Administrador'],
} as const satisfies Record<string, readonly Rol[]>;

export type Permiso = keyof typeof PERMISOS;

// Función pura, para usar fuera de los componentes. Dentro de ellos, usar el hook usePermisos().
export function tienePermiso(rol: Rol | undefined | null, permiso: Permiso): boolean {
  if (!rol) return false;
  return (PERMISOS[permiso] as readonly string[]).includes(rol);
}
