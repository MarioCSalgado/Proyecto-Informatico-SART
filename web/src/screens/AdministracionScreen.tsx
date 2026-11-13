import ManageAccountsOutlinedIcon from '@mui/icons-material/ManageAccountsOutlined'
import VerifiedUserOutlinedIcon from '@mui/icons-material/VerifiedUserOutlined'
import { CabeceraPagina } from '../components/CabeceraPagina.tsx'
import { EmptyState } from '../components/EmptyState.tsx'
import { useAuth } from '../context/authContext.tsx'

// Administración (diseño «Administración»; RF-9 y RF-16). Etapa 1: estructura sin datos. En la etapa 2:
// usuarios y permisos, umbrales y supuestos, e historial de cambios (RNF-S-4).
export function AdministracionScreen() {
  const { user } = useAuth()

  return (
    <div className="pagina">
      <CabeceraPagina
        antetitulo="Alcance global"
        titulo="Administración"
        subtitulo="Cuentas institucionales, umbrales y supuestos, y trazabilidad de cambios."
      />
      <p className="aviso">
        <VerifiedUserOutlinedIcon className="aviso__icono" aria-hidden="true" />
        <span>{user?.nombre} · Administrador. Sesión protegida con verificación en dos pasos.</span>
      </p>
      <section className="tarjeta">
        <EmptyState
          icon={<ManageAccountsOutlinedIcon />}
          title="La gestión de cuentas y umbrales todavía no está en la web"
          description={
            <>
              Mientras tanto, las cuentas se crean y el MFA se activa con el comando{' '}
              <code>python -m sart.cuentas</code> (ver el README).
            </>
          }
        />
      </section>
    </div>
  )
}
