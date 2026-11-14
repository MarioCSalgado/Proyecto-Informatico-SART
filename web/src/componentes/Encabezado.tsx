import ApartmentOutlinedIcon from '@mui/icons-material/ApartmentOutlined'
import LogoutOutlinedIcon from '@mui/icons-material/LogoutOutlined'
import TuneOutlinedIcon from '@mui/icons-material/TuneOutlined'
import type { ReactNode } from 'react'
import { NavLink, useNavigate } from 'react-router'
import { SECCIONES, type Seccion } from '../acceso/rutas.ts'
import { useSesion } from '../contexto/sesion.tsx'
import { usePermisos } from '../hooks/usePermisos.ts'
import { IconoPulso, Logo } from './Logo.tsx'

const ICONOS: Record<Seccion['icono'], ReactNode> = {
  pulso: <IconoPulso className="encabezado__icono" />,
  red: <ApartmentOutlinedIcon className="encabezado__icono" aria-hidden="true" />,
  ajustes: <TuneOutlinedIcon className="encabezado__icono" aria-hidden="true" />,
}

/** Iniciales del nombre (dos como máximo) para el círculo del encabezado. */
function iniciales(nombre: string | undefined): string {
  const palabras = (nombre ?? '').trim().split(/\s+/).filter(Boolean)
  return palabras.slice(0, 2).map((p) => p.charAt(0).toUpperCase()).join('')
}

// Barra superior (DESIGN.md · Encabezado): logo, secciones que el rol puede ver (la activa en píldora),
// iniciales, nombre y rol, y salir.
export function Encabezado() {
  const { usuario, cerrar } = useSesion()
  const { puede } = usePermisos()
  const navigate = useNavigate()
  const secciones = SECCIONES.filter((s) => puede(s.permiso))

  async function salir() {
    await cerrar()
    navigate('/login', { replace: true })
  }

  return (
    <header className="encabezado">
      <Logo />
      <nav className="encabezado__nav" aria-label="Secciones">
        {secciones.map((s) => (
          <NavLink key={s.ruta} to={s.ruta} className="encabezado__enlace">
            {ICONOS[s.icono]}
            {s.etiqueta}
          </NavLink>
        ))}
      </nav>
      <div className="encabezado__usuario">
        <span className="encabezado__iniciales" aria-hidden="true">{iniciales(usuario?.nombre)}</span>
        <span className="encabezado__datos">
          <span className="encabezado__nombre">{usuario?.nombre}</span>
          <span className="encabezado__rol">{usuario?.rol}</span>
        </span>
        <button type="button" className="encabezado__salir" onClick={salir} aria-label="Cerrar sesión"
          title="Cerrar sesión">
          <LogoutOutlinedIcon aria-hidden="true" />
        </button>
      </div>
    </header>
  )
}
