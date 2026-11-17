import { cleanup, render, screen, within } from '@testing-library/react'
import { userEvent } from '@testing-library/user-event'
import { AxiosError, AxiosHeaders } from 'axios'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { HistorialConfiguracion } from '../pantallas/HistorialConfiguracion.tsx'
import { ParametrosAdministracion } from '../pantallas/ParametrosAdministracion.tsx'
import { UmbralesAdministracion } from '../pantallas/UmbralesAdministracion.tsx'
import clienteApi from '../servicios/clienteApi.ts'

const CENTRO = { codigo_deis: 100001, nombre: 'SAR de prueba' }
const SIN_UMBRAL = { codigo_deis: 100002, nombre: 'SAPU sin umbral' }
const UMBRAL = { umbral_atencion: 650, umbral_alerta: 713, origen: 'calculado', anios_usados: '2022–2024' }
const CLAVE_K = 'regla_alerta.k_margen'
const CLAVE_SUR = 'dotacion.horas_funcionamiento_semana.SUR'
const UMBRALES = 'administracion/umbrales'
const PARAMETROS = 'administracion/parametros'
const HISTORIAL = 'administracion/historial'

function errorApi(status: number, detail: string) {
  return new AxiosError(detail, undefined, undefined, undefined, {
    status, statusText: '', data: { detail }, headers: {}, config: { headers: new AxiosHeaders() },
  })
}

afterEach(() => {
  cleanup()
  vi.restoreAllMocks()
})

describe('RF-9 y RB-3 · Umbrales por centro', () => {
  it('carga el umbral vigente, avisa el origen y guarda el nuevo valor con motivo', async () => {
    const usuario = userEvent.setup()
    const get = vi.spyOn(clienteApi, 'get').mockResolvedValue({
      data: [{ centro: CENTRO, umbral: UMBRAL }, { centro: SIN_UMBRAL, umbral: null }],
    })
    const put = vi.spyOn(clienteApi, 'put').mockResolvedValue({
      data: { centro: CENTRO, umbral: { ...UMBRAL, umbral_alerta: 720, origen: 'manual', anios_usados: null } },
    })
    render(<UmbralesAdministracion />)

    await screen.findByRole('option', { name: CENTRO.nombre })
    await usuario.selectOptions(screen.getByLabelText('Centro a configurar'), '100001')
    expect(screen.getByLabelText('Atención desde')).toHaveValue(650)
    expect(screen.getByLabelText('Alerta desde')).toHaveValue(713)
    expect(screen.getByText(/calculado.*2022–2024/i)).toBeInTheDocument()

    await usuario.clear(screen.getByLabelText('Alerta desde'))
    await usuario.type(screen.getByLabelText('Alerta desde'), '720')
    await usuario.type(screen.getByLabelText('Motivo del cambio'), '  Revisión de demanda  ')
    await usuario.click(screen.getByRole('button', { name: 'Guardar umbrales' }))

    expect(await screen.findByText('Umbrales guardados.')).toBeInTheDocument()
    expect(screen.getByText(/Umbral vigente: manual/i)).toBeInTheDocument()
    expect(screen.getByLabelText('Motivo del cambio')).toHaveValue('')
    expect(get).toHaveBeenCalledWith(UMBRALES, expect.objectContaining({ signal: expect.anything() }))
    expect(put).toHaveBeenCalledWith(`${UMBRALES}/100001`, {
      umbral_atencion: 650, umbral_alerta: 720, motivo: 'Revisión de demanda',
    })

    await usuario.selectOptions(screen.getByLabelText('Centro a configurar'), '100002')
    expect(screen.getByText('Este centro aún no tiene umbrales vigentes.')).toBeInTheDocument()
    expect(screen.getByLabelText('Alerta desde')).toHaveValue(null)
    await usuario.selectOptions(screen.getByLabelText('Centro a configurar'), '100001')
    expect(screen.getByLabelText('Alerta desde')).toHaveValue(720)
  })

  it('rechaza un motivo en blanco y una pareja desordenada sin llamar al backend', async () => {
    const usuario = userEvent.setup()
    vi.spyOn(clienteApi, 'get').mockResolvedValue({ data: [{ centro: CENTRO, umbral: UMBRAL }] })
    const put = vi.spyOn(clienteApi, 'put')
    render(<UmbralesAdministracion />)
    await screen.findByRole('option', { name: CENTRO.nombre })
    await usuario.selectOptions(screen.getByLabelText('Centro a configurar'), '100001')
    const guardar = screen.getByRole('button', { name: 'Guardar umbrales' })
    const motivo = screen.getByLabelText('Motivo del cambio')
    await usuario.type(motivo, '   ')
    await usuario.click(guardar)
    expect(screen.getByRole('alert')).toHaveTextContent('El motivo del cambio es obligatorio.')

    await usuario.type(motivo, 'Revisión')
    await usuario.clear(screen.getByLabelText('Atención desde'))
    await usuario.type(screen.getByLabelText('Atención desde'), '800')
    await usuario.click(guardar)
    expect(screen.getByRole('alert')).toHaveTextContent('Atención debe ser menor o igual que Alerta.')
    expect(put).not.toHaveBeenCalled()
  })
})

describe('RF-9 y TC-17 · Parámetros editables', () => {
  it('edita solo los parámetros devueltos, distingue un valor nulo y permite guardar k = 0', async () => {
    const usuario = userEvent.setup()
    const get = vi.spyOn(clienteApi, 'get').mockResolvedValue({
      data: [{ clave: CLAVE_K, valor: 0.4 }, { clave: CLAVE_SUR, valor: null }],
    })
    const put = vi.spyOn(clienteApi, 'put').mockResolvedValue({ data: { clave: CLAVE_K, valor: 0 } })
    render(<ParametrosAdministracion />)
    await screen.findByRole('option', { name: 'Margen de alerta (k)' })
    const selector = screen.getByLabelText('Parámetro a configurar')
    expect(within(selector).getAllByRole('option')).toHaveLength(3)
    await usuario.selectOptions(selector, CLAVE_SUR)
    expect(screen.getByLabelText('Valor del parámetro')).toHaveValue(null)
    expect(screen.getByText('Valor vigente sin definir.')).toBeInTheDocument()
    await usuario.selectOptions(selector, CLAVE_K)
    const valor = screen.getByLabelText('Valor del parámetro')
    const motivo = screen.getByLabelText('Motivo del ajuste')
    const guardar = screen.getByRole('button', { name: 'Guardar parámetro' })
    expect(valor).toHaveValue(0.4)
    await usuario.clear(valor)
    await usuario.type(motivo, 'Calibración')
    await usuario.click(guardar)
    expect(screen.getByRole('alert')).toHaveTextContent('Ingrese un valor numérico no negativo.')
    await usuario.type(valor, '0')
    await usuario.clear(motivo)
    await usuario.type(motivo, '   ')
    await usuario.click(guardar)
    expect(screen.getByRole('alert')).toHaveTextContent('El motivo del cambio es obligatorio.')
    expect(put).not.toHaveBeenCalled()

    await usuario.type(motivo, 'Sin margen para TC-17')
    await usuario.click(guardar)
    expect(await screen.findByText('Parámetro guardado.')).toBeInTheDocument()
    expect(get).toHaveBeenCalledWith(PARAMETROS, expect.objectContaining({ signal: expect.anything() }))
    expect(put).toHaveBeenCalledWith(`${PARAMETROS}/${CLAVE_K}`, { valor: 0, motivo: 'Sin margen para TC-17' })
    expect(valor).toHaveValue(0)
  })

  it('conserva el borrador y muestra el error de validación del backend', async () => {
    const usuario = userEvent.setup()
    vi.spyOn(clienteApi, 'get').mockResolvedValue({ data: [{ clave: 'umbrales.cuantil_alerta', valor: 0.9 }] })
    vi.spyOn(clienteApi, 'put').mockRejectedValue(
      errorApi(422, 'Los cuantiles deben cumplir 0 < atención ≤ alerta < 1.'),
    )
    render(<ParametrosAdministracion />)
    await screen.findByRole('option', { name: 'Cuantil de Alerta' })
    await usuario.selectOptions(screen.getByLabelText('Parámetro a configurar'), 'umbrales.cuantil_alerta')
    const valor = screen.getByLabelText('Valor del parámetro')
    const motivo = screen.getByLabelText('Motivo del ajuste')
    await usuario.clear(valor)
    await usuario.type(valor, '1')
    await usuario.type(motivo, 'Probar cuantil')
    await usuario.click(screen.getByRole('button', { name: 'Guardar parámetro' }))
    expect(await screen.findByRole('alert')).toHaveTextContent('Los cuantiles deben cumplir')
    expect(valor).toHaveValue(1)
    expect(motivo).toHaveValue('Probar cuantil')
  })
})

describe('RF-9 · Historial de configuración', () => {
  it('muestra tanto cambios de parámetros como de umbral con sus datos de auditoría', async () => {
    const fecha = '2025-07-07T09:00:00Z'
    const get = vi.spyOn(clienteApi, 'get').mockResolvedValue({ data: [
      { fecha, autor_id: 7, autor_rol: 'administrador', accion: 'cambio_parametro', entidad_id: CLAVE_K,
        valor_anterior: 0.4, valor_nuevo: 0, motivo: 'Sin margen', centro: null },
      { fecha, autor_id: null, autor_rol: 'sistema', accion: 'recalculo_umbral', entidad_id: '1',
        valor_anterior: null, valor_nuevo: UMBRAL, motivo: 'RB-3', centro: CENTRO },
    ] })
    render(<HistorialConfiguracion />)

    const tabla = await screen.findByRole('table', { name: 'Historial de cambios de configuración' })
    const filas = within(tabla).getAllByRole('row')
    expect(filas).toHaveLength(3)
    expect(filas[1]).toHaveTextContent('Margen de alerta (k)')
    expect(filas[1]).toHaveTextContent('Administrador (#7)')
    expect(filas[1]).toHaveTextContent('0,4')
    expect(within(filas[1]!).getByText('0')).toBeInTheDocument()
    expect(filas[1]).toHaveTextContent('Sin margen')
    expect(filas[1]?.querySelector('time')).toHaveAttribute('datetime', fecha)
    expect(filas[2]).toHaveTextContent(CENTRO.nombre)
    expect(filas[2]).toHaveTextContent('Sistema')
    expect(filas[2]).toHaveTextContent('Sin valor')
    expect(filas[2]).toHaveTextContent('Atención 650 · Alerta 713')
    expect(get).toHaveBeenCalledWith(HISTORIAL, expect.objectContaining({ signal: expect.anything() }))
  })

  it('anuncia la carga y permite reintentar hasta obtener un historial vacío', async () => {
    const usuario = userEvent.setup()
    let fallar!: (error: Error) => void
    vi.spyOn(clienteApi, 'get').mockImplementationOnce(() => new Promise((_, reject) => {
      fallar = reject
    })).mockResolvedValueOnce({ data: [] })
    render(<HistorialConfiguracion />)

    expect(screen.getByRole('status')).toHaveTextContent('Cargando historial de configuración')
    fallar(new Error('Red no disponible'))
    expect(await screen.findByRole('alert')).toHaveTextContent('No se pudo cargar el historial.')
    await usuario.click(screen.getByRole('button', { name: 'Reintentar' }))
    expect(await screen.findByText('Todavía no hay cambios registrados')).toBeInTheDocument()
  })
})
