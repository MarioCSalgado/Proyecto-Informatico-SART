import CheckCircleOutlineIcon from '@mui/icons-material/CheckCircleOutlineOutlined'
import ErrorOutlineIcon from '@mui/icons-material/ErrorOutlineOutlined'
import WarningAmberIcon from '@mui/icons-material/WarningAmberOutlined'
import type { ComponentType } from 'react'
import type { NivelAlerta as Nivel } from '../tipos/index.ts'

// RNF-U-1: el nivel nunca se indica solo con color. Siempre va con texto y con un ícono de forma distinta
// (círculo con visto, círculo con «!» y triángulo), legible también en blanco y negro (DESIGN.md).
const NIVELES: Record<Nivel, { texto: string; Icono: ComponentType<{ className?: string }>; corto: string }> = {
  normal: { texto: 'Normal', Icono: CheckCircleOutlineIcon, corto: 'N' },
  atencion: { texto: 'Atención', Icono: ErrorOutlineIcon, corto: 'At' },
  alerta: { texto: 'Alerta', Icono: WarningAmberIcon, corto: 'Al' },
}

/** Ícono del nivel, decorativo: siempre acompaña al texto del nivel. */
export function IconoNivel({ nivel, className = '' }: { nivel: Nivel; className?: string }) {
  const { Icono } = NIVELES[nivel]
  return <Icono className={className} aria-hidden="true" />
}

export function NivelAlerta({ nivel }: { nivel: Nivel }) {
  return (
    <span className={`nivel nivel--${nivel}`}>
      <IconoNivel nivel={nivel} className="nivel__icono" />
      {NIVELES[nivel].texto}
    </span>
  )
}

/** Celda del calendario de calor de la vista de red: abreviatura con su nombre completo para lectores de pantalla. */
export function NivelCorto({ nivel }: { nivel: Nivel }) {
  const { texto, corto } = NIVELES[nivel]
  return (
    <abbr className={`nivel-corto nivel--${nivel}`} title={texto}>
      {corto}
    </abbr>
  )
}
