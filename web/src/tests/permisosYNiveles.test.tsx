import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { tienePermiso, ROLES } from '../acceso/permisos.ts'
import { NivelAlerta } from '../componentes/NivelAlerta.tsx'

describe('permisos por rol (RNF-S-2)', () => {
  it('usa solo los tres roles de SART', () => {
    expect([...ROLES]).toEqual(['Jefatura', 'Subdirector', 'Administrador'])
  })

  it('la Jefatura no ve todos los centros ni administra', () => {
    expect(tienePermiso('Jefatura', 'ver_estado_centros')).toBe(true)
    expect(tienePermiso('Jefatura', 'ver_todos_los_centros')).toBe(false)
    expect(tienePermiso('Jefatura', 'administrar_cuentas')).toBe(false)
    expect(tienePermiso(null, 'ver_estado_centros')).toBe(false)
  })
})

describe('NivelAlerta (RNF-U-1)', () => {
  it.each([
    ['normal', 'Normal'],
    ['atencion', 'Atención'],
    ['alerta', 'Alerta'],
  ] as const)('el nivel %s se muestra con texto, no solo con color', (nivel, texto) => {
    render(<NivelAlerta nivel={nivel} />)
    expect(screen.getByText(texto)).toBeInTheDocument()
  })
})
