import { tienePermiso, type Permiso, type Rol } from './permisos.ts'

// Secciones de la aplicación (diseño de Figma: una pantalla de inicio por rol). La API vuelve a revisar
// cada permiso (RNF-S-2); esto solo decide qué se muestra y a dónde se llega después de iniciar sesión.
export type Seccion = {
  ruta: string
  etiqueta: string
  permiso: Permiso
  icono: 'pulso' | 'red' | 'ajustes'
}

export const SECCIONES: readonly Seccion[] = [
  { ruta: '/mi-centro', etiqueta: 'Mi centro', permiso: 'ver_mi_centro', icono: 'pulso' },
  { ruta: '/red', etiqueta: 'Red de centros', permiso: 'ver_todos_los_centros', icono: 'red' },
  { ruta: '/administracion', etiqueta: 'Administración', permiso: 'administrar_cuentas', icono: 'ajustes' },
]

const INICIO: Record<Rol, string> = {
  Jefatura: '/mi-centro',
  Subdirector: '/red',
  Administrador: '/administracion',
}

/** Pantalla a la que llega cada rol al iniciar sesión o al abrir la raíz. */
export function rutaInicio(rol: Rol): string {
  return INICIO[rol]
}

/** A dónde ir después de iniciar sesión: a la página que se quería abrir, solo si el rol puede verla (RNF-S-2).
 *  Sin esto, una jefatura que venía de /red llegaba a «Acceso restringido». */
export function destinoTrasLogin(rol: Rol, desde?: string | null): string {
  if (!desde || desde === '/' || desde.startsWith('/login')) return rutaInicio(rol)
  const seccion = SECCIONES.find((s) => desde === s.ruta || desde.startsWith(`${s.ruta}/`))
  if (seccion && !tienePermiso(rol, seccion.permiso)) return rutaInicio(rol)
  return desde
}
