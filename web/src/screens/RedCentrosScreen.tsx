import ApartmentOutlinedIcon from '@mui/icons-material/ApartmentOutlined'
import DownloadOutlinedIcon from '@mui/icons-material/DownloadOutlined'
import SearchOutlinedIcon from '@mui/icons-material/SearchOutlined'
import { useState } from 'react'
import { AvisoPendiente } from '../components/AvisoPendiente.tsx'
import { CabeceraPagina } from '../components/CabeceraPagina.tsx'
import { NivelAlerta, NivelCorto } from '../components/NivelAlerta.tsx'
import { TablaVacia } from '../components/TablaVacia.tsx'
import { useReferencias } from '../hooks/useReferencias.ts'
import type { NivelAlerta as Nivel } from '../types/index.ts'

const NIVELES: Nivel[] = ['alerta', 'atencion', 'normal']

// Vista de red del subdirector (diseño «Vista de red»; RF-7 con todos los centros). Partes fijas: resumen por
// nivel, filtros, leyenda y la tabla de seguimiento con sus columnas. Los números, las alertas sin confirmar
// (RF-15) y las filas llegan cuando la API los entregue. Las comunas del filtro vienen de la API (RNF-M-4).
export function RedCentrosScreen() {
  const { referencias } = useReferencias()
  const comunas = referencias?.comunas ?? []
  const [comuna, setComuna] = useState('')
  const [busqueda, setBusqueda] = useState('')

  return (
    <div className="pagina">
      <CabeceraPagina
        antetitulo="Vista de red"
        titulo="Red de centros"
        subtitulo="Gran Concepción · centros de urgencia"
        acciones={
          <button type="button" className="boton-secundario" disabled>
            <DownloadOutlinedIcon aria-hidden="true" /> Exportar red CSV
          </button>
        }
      />

      <ul className="kpis" aria-label="Resumen de la red">
        <li className="kpi">
          <span className="kpi__valor">—</span>
          <span className="kpi__etiqueta">Centros en la red</span>
        </li>
        {NIVELES.map((nivel) => (
          <li key={nivel} className="kpi">
            <span className="kpi__valor">—</span>
            <NivelAlerta nivel={nivel} />
          </li>
        ))}
      </ul>

      <div className="filtros">
        <div className="campo">
          <label htmlFor="filtro-comuna">Comuna</label>
          <div className="campo__caja">
            <select id="filtro-comuna" value={comuna} onChange={(e) => setComuna(e.target.value)}>
              <option value="">Todas las comunas ({comunas.length})</option>
              {comunas.map((c) => <option key={c} value={c}>{c}</option>)}
            </select>
          </div>
        </div>
        <div className="campo">
          <label htmlFor="filtro-centro">Buscar centro</label>
          <div className="campo__caja">
            <input id="filtro-centro" type="search" placeholder="Nombre o código del centro" value={busqueda}
              onChange={(e) => setBusqueda(e.target.value)} />
            <SearchOutlinedIcon className="campo__icono" aria-hidden="true" />
          </div>
        </div>
        <p className="filtros__orden">
          <strong>Orden: Alerta → Atención → Normal</strong>
          <span>Dentro de cada nivel, el mayor pronóstico primero.</span>
        </p>
      </div>

      <section className="tarjeta" aria-labelledby="titulo-seguimiento">
        <div className="tarjeta__encabezado">
          <div>
            <h2 id="titulo-seguimiento" className="tarjeta__titulo">Seguimiento de centros</h2>
            <p className="tarjeta__bajada">
              Calendario de calor por centro, últimas 12 semanas · N = Normal · At = Atención · Al = Alerta
            </p>
          </div>
        </div>
        <ul className="leyenda-chips" aria-label="Niveles del calendario">
          {NIVELES.slice().reverse().map((nivel) => (
            <li key={nivel}><NivelCorto nivel={nivel} /><NivelAlerta nivel={nivel} /></li>
          ))}
        </ul>
        <p className="nota">Umbrales de cada centro: percentiles 75 y 90 de sus últimos 3 años (RB-3).</p>
        <TablaVacia
          titulo="Seguimiento de centros"
          columnas={['Centro', 'Comuna', 'Pronóstico', 'Nivel', 'Confirmación', 'Últimas 12 semanas']}
          icono={<ApartmentOutlinedIcon />}
          mensaje="Todavía no hay pronósticos de la red"
          detalle="Aparecerá cada centro con su nivel, el estado de su confirmación y sus últimas semanas."
        />
        <AvisoPendiente>Los filtros y la exportación se activan cuando la API entregue la red (RF-7, RF-11).</AvisoPendiente>
      </section>
    </div>
  )
}
