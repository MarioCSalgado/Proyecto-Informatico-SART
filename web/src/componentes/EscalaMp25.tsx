import ErrorOutlineOutlinedIcon from '@mui/icons-material/ErrorOutlineOutlined'
import RemoveCircleOutlineOutlinedIcon from '@mui/icons-material/RemoveCircleOutlineOutlined'
import ShieldOutlinedIcon from '@mui/icons-material/ShieldOutlined'
import SpaOutlinedIcon from '@mui/icons-material/SpaOutlined'
import WarningAmberOutlinedIcon from '@mui/icons-material/WarningAmberOutlined'
import type { ComponentType } from 'react'
import type { Mp25Zona, NivelMp25 } from '../tipos/index.ts'
import { decimal, diaMes } from '../utilidades/formato.ts'
import { BloqueCarga } from './BloqueCarga.tsx'

// Escala de MP2,5 en 5 niveles (RB-1, RF-4), del diseño «Inicio de jefatura». Los límites llegan de la API
// (parametros.yaml, RNF-M-4); aquí solo va la presentación. RNF-U-1: cada nivel con nombre, ícono de forma
// distinta y rango, no solo color. Nombres de RB-1 (pendientes #25), no los del diseño.
const PRESENTACION: Record<string, { Icono: ComponentType<{ className?: string }>; consejo: string }> = {
  normal: { Icono: SpaOutlinedIcon, consejo: 'Actividades al aire libre sin restricción.' },
  sobre_la_norma: { Icono: RemoveCircleOutlineOutlinedIcon, consejo: 'Personas sensibles: moderar esfuerzos prolongados.' },
  alerta: { Icono: WarningAmberOutlinedIcon, consejo: 'Población de riesgo: limitar los esfuerzos al aire libre.' },
  preemergencia: {
    Icono: ErrorOutlineOutlinedIcon,
    consejo: 'Evitar esfuerzos al aire libre, especialmente los grupos de riesgo.',
  },
  emergencia: { Icono: ShieldOutlinedIcon, consejo: 'Evitar la actividad al aire libre y seguir las indicaciones sanitarias.' },
}

function rangoMp25(nivel: NivelMp25): string {
  return nivel.hasta === null ? `≥ ${nivel.desde} µg/m³` : `${nivel.desde}–${nivel.hasta} µg/m³`
}

type Props = { niveles: NivelMp25[] | null; cargando: boolean; error: boolean; actual?: Mp25Zona | null }

/** Medición de la zona del centro (RB-5, RF-7 E3): de respaldo marcada, y «datos insuficientes» explícito. */
function MedicionActual({ actual }: { actual: Mp25Zona }) {
  if (actual.estado === 'datos_insuficientes') {
    return (
      <p className="escala-mp__actual escala-mp__actual--insuficiente" role="status">
        <strong>Datos insuficientes (RB-5).</strong>{' '}
        {actual.valor !== null && actual.fecha
          ? <>Última medición válida: {decimal(actual.valor)} µg/m³ el {diaMes(actual.fecha)} en {actual.estacion}.</>
          : <>Ni la estación del centro ni la de respaldo tienen mediciones.</>}
      </p>
    )
  }
  return (
    <p className="escala-mp__actual">
      <span className="escala-mp__valor">{actual.valor !== null ? decimal(actual.valor) : '—'}</span> µg/m³
      {actual.nivel && <> · {actual.nivel.nombre}</>}
      <span className="escala-mp__origen">
        Promedio del {actual.fecha ? diaMes(actual.fecha) : '—'} · {actual.estacion}
        {actual.de_respaldo && <span className="etiqueta-respaldo">de respaldo</span>}
      </span>
    </p>
  )
}

export function EscalaMp25({ niveles, cargando, error, actual = null }: Props) {
  const claveActual = actual?.estado === 'ok' ? actual.nivel?.clave : undefined
  return (
    <section className="tarjeta" aria-labelledby="titulo-escala-mp">
      <h2 id="titulo-escala-mp" className="tarjeta__titulo">Calidad del aire · MP2,5</h2>
      <p className="tarjeta__bajada">Escala de 5 niveles · promedio de 24 horas en µg/m³</p>
      {actual && <MedicionActual actual={actual} />}

      {cargando && (
        <div className="escala-mp__carga" aria-hidden="true">
          {Array.from({ length: 5 }).map((_, i) => <BloqueCarga key={i} alto="2.6rem" />)}
        </div>
      )}
      {error && <p className="pendiente" role="status">No se pudo cargar la escala. Intente recargar la página.</p>}
      {niveles && (
        <ul className="escala-mp">
          {niveles.map((nivel) => {
            const { Icono, consejo } = PRESENTACION[nivel.clave] ?? { Icono: ErrorOutlineOutlinedIcon, consejo: '' }
            return (
              <li key={nivel.clave} aria-current={nivel.clave === claveActual ? 'true' : undefined}
                className={`escala-mp__nivel escala-mp--${nivel.clave}${nivel.clave === claveActual ? ' escala-mp__nivel--actual' : ''}`}>
                <div className="escala-mp__fila">
                  <h3 className="escala-mp__nombre">
                    <Icono className="escala-mp__icono" />
                    {nivel.nombre}
                  </h3>
                  <span className="escala-mp__rango">
                    {nivel.clave === claveActual && <span className="escala-mp__marca">Ahora</span>}
                    {rangoMp25(nivel)}
                  </span>
                </div>
                {consejo && <p className="escala-mp__consejo">{consejo}</p>}
              </li>
            )
          })}
        </ul>
      )}
      <p className="nota">Fuente: SINCA. La escala del aire es independiente de la alerta de demanda.</p>
    </section>
  )
}
