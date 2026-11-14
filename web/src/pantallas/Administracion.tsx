import DownloadOutlinedIcon from '@mui/icons-material/DownloadOutlined'
import GroupOutlinedIcon from '@mui/icons-material/GroupOutlined'
import HistoryOutlinedIcon from '@mui/icons-material/HistoryOutlined'
import PersonAddAltOutlinedIcon from '@mui/icons-material/PersonAddAltOutlined'
import VerifiedUserOutlinedIcon from '@mui/icons-material/VerifiedUserOutlined'
import { Tab, Tabs } from '@mui/material'
import { useState } from 'react'
import { AvisoPendiente } from '../componentes/AvisoPendiente.tsx'
import { CabeceraPagina } from '../componentes/CabeceraPagina.tsx'
import { IconoNivel } from '../componentes/NivelAlerta.tsx'
import { TablaVacia } from '../componentes/TablaVacia.tsx'
import { useSesion } from '../contexto/sesion.tsx'

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

function Umbrales() {
  return (
    <section className="tarjeta" aria-labelledby="titulo-umbrales">
      <h2 id="titulo-umbrales" className="tarjeta__titulo">Umbrales por centro</h2>
      <p className="tarjeta__bajada">
        Se calculan con los percentiles 75 y 90 de los últimos 3 años de cada centro (RB-3). El administrador puede
        corregirlos con un motivo; el cambio queda en el historial y rige en la corrida siguiente.
      </p>
      <form className="formulario-grilla" onSubmit={(e) => e.preventDefault()}>
        <div className="campo">
          <label htmlFor="umbral-centro">Centro a configurar</label>
          <div className="campo__caja">
            <select id="umbral-centro" disabled defaultValue="">
              <option value="">Seleccione un centro</option>
            </select>
          </div>
        </div>
        <div className="campo">
          <label htmlFor="umbral-atencion"><IconoNivel nivel="atencion" className="campo__icono-nivel campo__icono-nivel--atencion" />Atención desde</label>
          <div className="campo__caja"><input id="umbral-atencion" type="number" inputMode="numeric" disabled /></div>
        </div>
        <div className="campo">
          <label htmlFor="umbral-alerta"><IconoNivel nivel="alerta" className="campo__icono-nivel campo__icono-nivel--alerta" />Alerta desde</label>
          <div className="campo__caja"><input id="umbral-alerta" type="number" inputMode="numeric" disabled /></div>
        </div>
        <div className="campo campo--ancho">
          <label htmlFor="umbral-motivo">Motivo del cambio</label>
          <textarea id="umbral-motivo" rows={3} disabled placeholder="Justificación clínica u operativa" />
        </div>
        <div className="formulario-grilla__pie">
          <p className="nota">Consultas por semana. Atención debe ser menor o igual que Alerta. El motivo es obligatorio.</p>
          <button type="submit" className="boton-primario" disabled>Guardar umbrales</button>
        </div>
      </form>
      <AvisoPendiente>{PENDIENTE_RF9}</AvisoPendiente>
    </section>
  )
}

function Historial() {
  return (
    <section className="tarjeta" aria-labelledby="titulo-historial">
      <div className="tarjeta__encabezado">
        <div>
          <h2 id="titulo-historial" className="tarjeta__titulo">Historial de cambios</h2>
          <p className="tarjeta__bajada">Registro de auditoría, el más reciente primero (RNF-S-4)</p>
        </div>
        <button type="button" className="boton-secundario" disabled>
          <DownloadOutlinedIcon aria-hidden="true" /> Descargar registro
        </button>
      </div>
      <TablaVacia
        titulo="Historial de cambios"
        columnas={['Fecha', 'Autor', 'Centro', 'Anterior → nuevo', 'Motivo']}
        icono={<HistoryOutlinedIcon />}
        mensaje="Todavía no hay cambios registrados"
      />
      <p className="nota">Registro de solo lectura, conservado 12 meses. Valores en consultas por semana.</p>
    </section>
  )
}

// Administración (diseño «Administración»; RF-9, RF-16, RNF-S-4). Partes fijas: aviso de la sesión protegida,
// pestañas, encabezados de tabla y el formulario de umbrales (desactivado hasta que exista la API de RF-9).
// Sin la columna «Estado» de las cuentas: la baja borra la cuenta (pendientes #18 y #24).
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
        {pestana === 'Umbrales' && <Umbrales />}
        {pestana === 'Historial' && <Historial />}
      </div>
    </div>
  )
}
