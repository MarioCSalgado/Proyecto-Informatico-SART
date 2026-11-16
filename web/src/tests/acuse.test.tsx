import { cleanup, render, screen } from '@testing-library/react'
import { userEvent } from '@testing-library/user-event'
import { MemoryRouter } from 'react-router'
import { afterEach, describe, expect, it, vi } from 'vitest'
import App from '../App.tsx'
import { ProveedorSesion } from '../contexto/sesion.tsx'
import clienteApi from '../servicios/clienteApi.ts'

// TC-06 en la pantalla (RF-15): abrir el enlace no confirma; solo el botón «Confirmar lectura».
const ACUSE = {
  estado: 'enviada', fecha_envio: '2026-11-16T07:30:00Z', fecha_confirmacion: null,
  alerta: { tipo: 'demanda', nivel: 'alerta', mensaje: 'Pronóstico sobre el umbral', fecha_emision: '2026-11-16T06:00:00Z',
    lugar: 'SAPU Lagunillas', dia_pronosticado: null },
}

describe('Acuse (RF-15)', () => {
  afterEach(() => {
    cleanup()
    vi.restoreAllMocks()
  })

  it('abrir la página no confirma; el botón sí, y luego muestra la fecha', async () => {
    vi.spyOn(clienteApi, 'get').mockImplementation(async (url: string) =>
      url === 'acuse/abc' ? { data: ACUSE } : { data: { usuario: { id: 2, nombre: 'Jefa', rol: 'Jefatura' } } })
    const post = vi.spyOn(clienteApi, 'post')
      .mockResolvedValue({ data: { ...ACUSE, estado: 'confirmada', fecha_confirmacion: '2026-11-16T09:00:00Z' } })
    render(<MemoryRouter initialEntries={['/acuse/abc']}><ProveedorSesion><App /></ProveedorSesion></MemoryRouter>)

    const boton = await screen.findByRole('button', { name: /Confirmar lectura/ })
    expect(screen.getByRole('heading', { name: /SAPU Lagunillas · nivel ALERTA/ })).toBeInTheDocument()
    expect(post).not.toHaveBeenCalled()

    await userEvent.setup().click(boton)

    expect(post).toHaveBeenCalledWith('acuse/abc/confirmar')
    expect(await screen.findByRole('status')).toHaveTextContent('Lectura confirmada')
  })
})
