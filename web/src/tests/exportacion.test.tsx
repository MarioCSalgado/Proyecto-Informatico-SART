import { cleanup, render, screen } from '@testing-library/react'
import { userEvent } from '@testing-library/user-event'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { BotonExportarCsv } from '../componentes/BotonExportarCsv.tsx'
import * as sesion from '../contexto/sesion.tsx'
import clienteApi from '../servicios/clienteApi.ts'

// RF-11 (TC-15): el botón pide el CSV a la API, que decide qué centros entran según el rol.
function comoRol(rol: 'Jefatura' | 'Subdirector' | 'Administrador') {
  vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(() => {})  // jsdom no descarga archivos
  vi.spyOn(sesion, 'useSesion').mockReturnValue({
    usuario: { id: 1, nombre: 'Demo', rol },
  } as unknown as ReturnType<typeof sesion.useSesion>)
}

describe('Exportar CSV (RF-11)', () => {
  afterEach(() => {
    cleanup()
    vi.restoreAllMocks()
  })

  it('descarga el CSV de un centro con su código', async () => {
    comoRol('Jefatura')
    URL.createObjectURL = vi.fn(() => 'blob:sart')
    URL.revokeObjectURL = vi.fn()
    const get = vi.spyOn(clienteApi, 'get').mockResolvedValue({
      data: new Blob(['codigo_deis;centro\r\n']),
      headers: { 'content-disposition': 'attachment; filename="sart_centro_100001.csv"' },
    })
    render(<BotonExportarCsv codigo={100001} etiqueta="Descargar CSV" />)

    await userEvent.click(screen.getByRole('button', { name: /Descargar CSV/ }))

    expect(get).toHaveBeenCalledWith('exportar/centros.csv', {
      params: { codigo_deis: 100001 }, responseType: 'blob',
    })
    expect(URL.createObjectURL).toHaveBeenCalled()
  })

  it('la red se exporta sin código: la API entrega los centros que el usuario ve', async () => {
    comoRol('Subdirector')
    URL.createObjectURL = vi.fn(() => 'blob:sart')
    URL.revokeObjectURL = vi.fn()
    const get = vi.spyOn(clienteApi, 'get').mockResolvedValue({ data: new Blob(['x']), headers: {} })
    render(<BotonExportarCsv etiqueta="Exportar red CSV" />)

    await userEvent.click(screen.getByRole('button', { name: /Exportar red CSV/ }))

    expect(get).toHaveBeenCalledWith('exportar/centros.csv', { params: undefined, responseType: 'blob' })
  })

  it('si la descarga falla, lo dice', async () => {
    comoRol('Jefatura')
    vi.spyOn(clienteApi, 'get').mockRejectedValue(new Error('sin conexión'))
    render(<BotonExportarCsv codigo={100001} etiqueta="Descargar CSV" />)

    await userEvent.click(screen.getByRole('button', { name: /Descargar CSV/ }))

    expect(await screen.findByRole('alert')).toHaveTextContent(/No se pudo descargar/)
  })
})
