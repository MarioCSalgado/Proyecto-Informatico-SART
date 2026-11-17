import GroupOutlinedIcon from '@mui/icons-material/GroupOutlined'
import PersonAddAltOutlinedIcon from '@mui/icons-material/PersonAddAltOutlined'
import VerifiedUserOutlinedIcon from '@mui/icons-material/VerifiedUserOutlined'
import { Tab, Tabs } from '@mui/material'
import { useState } from 'react'
import { AvisoPendiente } from '../componentes/AvisoPendiente.tsx'
import { CabeceraPagina } from '../componentes/CabeceraPagina.tsx'
import { TablaVacia } from '../componentes/TablaVacia.tsx'
import { useSesion } from '../contexto/sesion.tsx'
import { HistorialConfiguracion } from './HistorialConfiguracion.tsx'
import { ParametrosAdministracion } from './ParametrosAdministracion.tsx'
import { UmbralesAdministracion } from './UmbralesAdministracion.tsx'

const PESTANAS = ['Usuarios', 'Umbrales', 'Historial'] as const
type Pestana = (typeof PESTANAS)[number]

const PENDIENTE_RF9 = (
  <>Se habilita con la API de administración (RF-9). Mientras tanto se usa el comando <code>python -m sart.cuentas</code>.</>
)

function Usuarios() {
  return (
    <section className="tarjeta" aria-labelledby="titulo-usuarios">
      <div className="tarjeta__encabezado">
        <div>
          <h2 id="titulo-usuarios" className="tarjeta__titulo">Usuarios y permisos</h2>
          <p className="tarjeta__bajada">Solo el administrador crea cuentas, con la aceptación de la finalidad (RF-16).</p>
        </div>
        <button type="button" className="boton-primario" disabled>
          <PersonAddAltOutlinedIcon aria-hidden="true" /> Crear usuario
        </button>
      </div>
      <TablaVacia
        titulo="Usuarios y permisos"
        columnas={['Usuario / correo', 'Rol', 'Centro o alcance', 'Acción']}
        icono={<GroupOutlinedIcon />}
        mensaje="La lista de cuentas aparecerá aquí"
      />
      <p className="nota">
        Jefatura: solo su centro · Subdirector: lectura y seguimiento de la red · Administrador: cuentas, umbrales
        e historial, con verificación en dos pasos.
      </p>
      <AvisoPendiente>{PENDIENTE_RF9}</AvisoPendiente>
    </section>
  )
}

// Administración (RF-9, RF-16, RNF-S-4). T7 conecta la configuración y su historial.
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
        {pestana === 'Usuarios' && <Usuarios />}
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
