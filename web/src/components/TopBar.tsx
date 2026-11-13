import { useNavigate } from 'react-router'
import { usePermissions } from '../hooks/usePermissions.ts'
import { useAuth } from '../context/authContext.tsx'

// Adaptado de ing-software2: nombre del sistema, rol, inicial del usuario y botón para salir.
export function TopBar() {
  const { role } = usePermissions()
  const { logout, user } = useAuth()
  const navigate = useNavigate()

  const label = role ?? 'Usuario'
  const slug = (role ?? 'usuario').toLowerCase()
  const inicial = (user?.nombre ?? label).charAt(0).toUpperCase()

  async function handleLogout() {
    await logout()
    navigate('/login', { replace: true })
  }

  return (
    <header className="topbar">
      <div className="topbar-brand">
        <span className="topbar-logo" aria-hidden="true">🫁</span>
        <div className="topbar-titles">
          <span className="topbar-name">SART</span>
          <span className="topbar-sub">Alerta Respiratoria Temprana</span>
        </div>
      </div>

      <div className="topbar-user">
        <span className={`badge topbar-rol topbar-rol--${slug}`}>{label}</span>
        <span className="topbar-avatar" aria-hidden="true">{inicial}</span>
        <button className="topbar-logout" onClick={handleLogout} title="Cerrar sesión">
          Salir
        </button>
      </div>
    </header>
  )
}
