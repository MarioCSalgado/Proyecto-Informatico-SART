import ApartmentOutlinedIcon from '@mui/icons-material/ApartmentOutlined'
import LogoutOutlinedIcon from '@mui/icons-material/LogoutOutlined'
import TuneOutlinedIcon from '@mui/icons-material/TuneOutlined'
import type { ReactNode } from 'react'
import { NavLink, useNavigate } from 'react-router'
import { SECCIONES, type Seccion } from '../auth/rutas.ts'
import { useAuth } from '../context/authContext.tsx'
import { usePermissions } from '../hooks/usePermissions.ts'
import { IconoPulso, Logo } from './Logo.tsx'

const ICONOS: Record<Seccion['icono'], ReactNode> = {
  pulso: <IconoPulso className="encabezado__icono" />,
  red: <ApartmentOutlinedIcon className="encabezado__icono" aria-hidden="true" />,
  ajustes: <TuneOutlinedIcon className="encabezado__icono" aria-hidden="true" />,
}

// Barra superior del diseño de Figma: logo, secciones que el rol puede ver, nombre y rol, y salir.
export function Encabezado() {
  const { user, logout } = useAuth()
  const { can } = usePermissions()
  const navigate = useNavigate()
  const secciones = SECCIONES.filter((s) => can(s.permiso))

  async function salir() {
    await logout()
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
        <span className="encabezado__datos">
          <span className="encabezado__nombre">{user?.nombre}</span>
          <span className="encabezado__rol">{user?.rol}</span>
        </span>
        <button type="button" className="encabezado__salir" onClick={salir} aria-label="Cerrar sesión"
          title="Cerrar sesión">
          <LogoutOutlinedIcon aria-hidden="true" />
        </button>
      </div>
    </header>
  )
}
