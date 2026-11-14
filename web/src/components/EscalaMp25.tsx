import ErrorOutlineOutlinedIcon from '@mui/icons-material/ErrorOutlineOutlined'
import RemoveCircleOutlineOutlinedIcon from '@mui/icons-material/RemoveCircleOutlineOutlined'
import ShieldOutlinedIcon from '@mui/icons-material/ShieldOutlined'
import SpaOutlinedIcon from '@mui/icons-material/SpaOutlined'
import WarningAmberOutlinedIcon from '@mui/icons-material/WarningAmberOutlined'
import type { ComponentType } from 'react'
import type { NivelMp25 } from '../types/index.ts'
import { Skeleton } from './Skeleton.tsx'

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

type Props = { niveles: NivelMp25[] | null; cargando: boolean; error: boolean }

export function EscalaMp25({ niveles, cargando, error }: Props) {
  return (
    <section className="tarjeta" aria-labelledby="titulo-escala-mp">
      <h2 id="titulo-escala-mp" className="tarjeta__titulo">Calidad del aire · MP2,5</h2>
      <p className="tarjeta__bajada">Escala de 5 niveles · promedio de 24 horas en µg/m³</p>

      {cargando && (
        <div className="escala-mp__carga" aria-hidden="true">
          {Array.from({ length: 5 }).map((_, i) => <Skeleton key={i} height="2.6rem" />)}
        </div>
      )}
      {error && <p className="pendiente" role="status">No se pudo cargar la escala. Intente recargar la página.</p>}
      {niveles && (
        <ul className="escala-mp">
          {niveles.map((nivel) => {
            const { Icono, consejo } = PRESENTACION[nivel.clave] ?? { Icono: ErrorOutlineOutlinedIcon, consejo: '' }
            return (
              <li key={nivel.clave} className={`escala-mp__nivel escala-mp--${nivel.clave}`}>
                <div className="escala-mp__fila">
                  <h3 className="escala-mp__nombre">
                    <Icono className="escala-mp__icono" />
                    {nivel.nombre}
                  </h3>
                  <span className="escala-mp__rango">{rangoMp25(nivel)}</span>
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
