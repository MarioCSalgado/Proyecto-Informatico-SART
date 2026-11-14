import type { NivelAlerta as Nivel } from '../tipos/index.ts'

// RNF-U-1: el nivel nunca se indica solo con color. Siempre va con texto y con un signo de forma distinta
// (✓, ! y △, como en el diseño de Figma), legible también en blanco y negro.
const NIVELES: Record<Nivel, { texto: string; signo: string; corto: string }> = {
  normal: { texto: 'Normal', signo: '✓', corto: 'N' },
  atencion: { texto: 'Atención', signo: '!', corto: 'At' },
  alerta: { texto: 'Alerta', signo: '△', corto: 'Al' },
}

export function NivelAlerta({ nivel }: { nivel: Nivel }) {
  const { texto, signo } = NIVELES[nivel]
  return (
    <span className={`nivel nivel--${nivel}`}>
      <span aria-hidden="true">{signo}</span>
      {texto}
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
