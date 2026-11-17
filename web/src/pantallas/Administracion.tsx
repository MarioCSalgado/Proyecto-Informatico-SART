import VerifiedUserOutlinedIcon from '@mui/icons-material/VerifiedUserOutlined'
import { Tab, Tabs } from '@mui/material'
import { useState } from 'react'
import { CabeceraPagina } from '../componentes/CabeceraPagina.tsx'
import { useSesion } from '../contexto/sesion.tsx'
import { HistorialConfiguracion } from './HistorialConfiguracion.tsx'
import { ParametrosAdministracion } from './ParametrosAdministracion.tsx'
import { UmbralesAdministracion } from './UmbralesAdministracion.tsx'
import { UsuariosAdministracion } from './UsuariosAdministracion.tsx'

const PESTANAS = ['Usuarios', 'Umbrales', 'Historial'] as const
type Pestana = (typeof PESTANAS)[number]

// Administración (RF-9, RF-16, RNF-S-4). T6 conecta las cuentas; T7, la configuración y su historial.
export function PantallaAdministracion() {
  const { usuario } = useSesion()
  const [pestana, setPestana] = useState<Pestana>('Usuarios')

  return (
    <div className="pagina">
      <CabeceraPagina
        antetitulo="Alcance global"
        titulo="Administración"
        subtitulo="Cuentas institucionales, umbrales y supuestos, y trazabilidad de cambios."
      />
      <p className="aviso">
        <VerifiedUserOutlinedIcon className="aviso__icono" aria-hidden="true" />
        <span>{usuario?.nombre} · Administrador. Sesión protegida con verificación en dos pasos.</span>
      </p>

      <div className="pestanas">
        <Tabs value={pestana} onChange={(_, valor: Pestana) => setPestana(valor)} aria-label="Secciones de administración"
          variant="scrollable">
          {PESTANAS.map((p) => (
            <Tab key={p} value={p} label={p} id={`pestana-${p}`} aria-controls={`panel-${p}`} />
          ))}
        </Tabs>
      </div>
      <div role="tabpanel" id={`panel-${pestana}`} aria-labelledby={`pestana-${pestana}`}>
        {pestana === 'Usuarios' && <UsuariosAdministracion />}
        {pestana === 'Umbrales' && (
          <div className="pagina">
            <UmbralesAdministracion />
            <ParametrosAdministracion />
          </div>
        )}
        {pestana === 'Historial' && <HistorialConfiguracion />}
      </div>
    </div>
  )
}
