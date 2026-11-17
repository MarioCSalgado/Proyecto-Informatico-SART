import { act, cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import { userEvent } from '@testing-library/user-event'
import type { AxiosRequestConfig } from 'axios'
import { MemoryRouter } from 'react-router'
import { afterEach, describe, expect, it, vi } from 'vitest'
import App from '../App.tsx'
import type { Rol } from '../acceso/permisos.ts'
import { ProveedorSesion } from '../contexto/sesion.tsx'
import clienteApi from '../servicios/clienteApi.ts'

const CHIGUAYANTE = { codigo_deis: 100001, nombre: 'SAR Chiguayante', tipo: 'SAR', comuna: 'Chiguayante' }
const LORENZO = { codigo_deis: 100002, nombre: 'SAPU Lorenzo Arenas', tipo: 'SAPU', comuna: 'Concepción' }
const ALERTA = {
  id: 1, centro: CHIGUAYANTE, fecha_emision: '2025-07-07T09:00:00Z', nivel: 'alerta',
  pronostico: {
    anio: 2025, semana: 28, inicio_semana: '2025-07-06', fecha_corte: '2025-06-29',
    valor: 105, limite_inferior: 70, limite_superior: 150, vigente: false,
    umbral_alerta: 100, k_margen: 0.4, valor_con_margen: 115,
  },
  dotacion: {
    profesionales: 3, llegadas_hora_punta: 7.1, espera_media_min: 4.2, espera_con_uno_menos_min: 55,
    supuestos: { supuestos_validados: false }, por_validar: true,
  },
  observacion: { consultas: 110, semana_alta: true },
  notificaciones: { tipo: 'propia', estado: null, fecha_confirmacion: null },
}

function abrir(
  consultar: (config?: AxiosRequestConfig) => Promise<unknown> = async () => [ALERTA],
  rol: Rol | null = 'Jefatura',
) {
  const peticiones = vi.spyOn(clienteApi, 'get').mockImplementation(async (url: string, config) => {
    if (url === 'auth/yo') {
      if (!rol) throw new Error('Sin sesión')
      return { data: { usuario: { id: 1, nombre: `${rol} Demo`, rol } } }
    }
    if (url === 'centros/estado') {
      return { data: [{ centro: CHIGUAYANTE, pronostico: null, mp25: {}, ultimas_semanas: [] }] }
    }
    if (url === 'alertas/historial') return { data: await consultar(config) }
    return { data: { mp25_niveles: [], comunas: [] } }
  })
  render(
    <MemoryRouter initialEntries={['/historial-alertas']}>
      <ProveedorSesion><App /></ProveedorSesion>
    </MemoryRouter>,
  )
  return peticiones
}

afterEach(() => {
  cleanup()
  vi.restoreAllMocks()
})

describe('RF-10 · Historial de alertas', () => {
  it('TC-19 muestra los datos guardados y distingue cero, ausencia de observación y ausencia de umbral', async () => {
    abrir(async () => [
      ALERTA,
      { ...ALERTA, id: 2, dotacion: null, nivel: 'atencion', observacion: { consultas: 0, semana_alta: false },
        notificaciones: { tipo: 'no_aplica' } },
      { ...ALERTA, id: 3, dotacion: null, observacion: { consultas: null, semana_alta: null } },
      { ...ALERTA, id: 4, dotacion: null, pronostico: { ...ALERTA.pronostico, umbral_alerta: null },
        observacion: { consultas: 90, semana_alta: null } },
    ])
    const tabla = await screen.findByRole('table', { name: 'Historial de alertas emitidas' })
    const filas = within(tabla).getAllByRole('row').slice(1).map((fila) => within(fila))
    expect(filas).toHaveLength(4)
    expect(filas[0]!.getByRole('rowheader')).toHaveTextContent(CHIGUAYANTE.nombre)
    expect(filas[0]!.getByText('SE 28 · 2025')).toBeInTheDocument()
    expect(filas[0]!.getByText('Alerta')).toBeInTheDocument()
    expect(filas[0]!.getByText('105')).toBeInTheDocument()
    expect(filas[0]!.getByText('110')).toBeInTheDocument()
    expect(filas[0]!.getByText('3 profesionales')).toBeInTheDocument()
    expect(filas[0]!.getByText('Supuestos por validar')).toBeInTheDocument()
    expect(filas[0]!.getByText('Superó el umbral')).toBeInTheDocument()
    expect(tabla.querySelector('time')).toHaveAttribute('datetime', ALERTA.fecha_emision)
    expect(filas[1]!.getByText('0')).toBeInTheDocument()
    expect(filas[1]!.getByText('No superó el umbral')).toBeInTheDocument()
    expect(filas[2]!.getByText('Sin observación válida')).toBeInTheDocument()
    expect(filas[3]!.getByText('Sin umbral registrado')).toBeInTheDocument()
    expect(filas[1]!.getByText('No aplica: Atención no genera correo.')).toBeInTheDocument()
  })

  it('RF-10 distingue el acuse propio de envío, confirmación, ausencia y seguimiento', async () => {
    const fecha = '2025-07-07T11:00:00Z'
    const casos = [
      [null, 'Sin notificación registrada'],
      ['enviada', 'Enviada sin confirmar'],
      ['confirmada', 'Confirmada'],
      ['fallida', 'Fallida'],
      ['reenviada', 'Reenviada'],
      ['escalada', 'Escalada'],
    ] as const
    abrir(async () => casos.map(([estado], id) => ({
      ...ALERTA, id,
      notificaciones: { tipo: 'propia', estado, fecha_confirmacion: estado === 'confirmada' ? fecha : null },
    })))

    const tabla = await screen.findByRole('table', { name: 'Historial de alertas emitidas' })
    expect(within(tabla).getByRole('columnheader', { name: 'Notificación y acuse' })).toBeInTheDocument()
    const filas = within(tabla).getAllByRole('row').slice(1)
    casos.forEach(([, etiqueta], i) => expect(within(filas[i]!).getByText(etiqueta)).toBeInTheDocument())
    const fechas = Array.from(filas[2]!.querySelectorAll('time')).map((hora) => hora.dateTime)
    expect(fechas).toEqual([ALERTA.fecha_emision, fecha])
  })

  it.each(['Subdirector', 'Administrador'] as const)('RF-10 muestra a %s conteos por alerta', async (rol) => {
    abrir(async () => [
      { ...ALERTA, id: 1, notificaciones: { tipo: 'resumen', estados: [
        { estado: 'enviada', total: 1 }, { estado: 'fallida', total: 1 }, { estado: 'confirmada', total: 2 },
        { estado: 'reenviada', total: 2 }, { estado: 'escalada', total: 2 },
      ] } },
      { ...ALERTA, id: 2, notificaciones: { tipo: 'resumen', estados: [] } },
    ], rol)

    const tabla = await screen.findByRole('table', { name: 'Historial de alertas emitidas' })
    const [, primera, segunda] = within(tabla).getAllByRole('row')
    expect(within(primera!).getByText('1 enviada sin confirmar')).toBeInTheDocument()
    expect(within(primera!).getByText('1 fallida')).toBeInTheDocument()
    expect(within(primera!).getByText('2 confirmadas')).toBeInTheDocument()
    expect(within(primera!).getByText('2 reenviadas')).toBeInTheDocument()
    expect(within(primera!).getByText('2 escaladas')).toBeInTheDocument()
    expect(within(segunda!).getByText('Sin notificaciones registradas')).toBeInTheDocument()
    expect(primera!.querySelectorAll('time')).toHaveLength(1)
  })

  it('RF-10 envía los cuatro filtros a la API, limita el selector a los centros visibles y permite limpiar', async () => {
    const usuario = userEvent.setup()
    const consultar = vi.fn(async (config?: AxiosRequestConfig) => config?.params?.nivel ? [] : [ALERTA])
    abrir(consultar)
    await screen.findByRole('table', { name: 'Historial de alertas emitidas' })
    const centro = screen.getByLabelText('Centro')
    await within(centro).findByRole('option', { name: CHIGUAYANTE.nombre })
    expect(within(centro).queryByRole('option', { name: LORENZO.nombre })).not.toBeInTheDocument()

    await usuario.selectOptions(centro, '100001')
    fireEvent.change(screen.getByLabelText('Desde'), { target: { value: '2025-07-06' } })
    fireEvent.change(screen.getByLabelText('Hasta'), { target: { value: '2025-07-19' } })
    await usuario.selectOptions(screen.getByLabelText('Nivel'), 'atencion')
    await usuario.click(screen.getByRole('button', { name: 'Aplicar filtros' }))

    expect(await screen.findByText('Ninguna alerta coincide con los filtros')).toBeInTheDocument()
    expect(consultar).toHaveBeenLastCalledWith(expect.objectContaining({
      params: { codigo_deis: 100001, desde: '2025-07-06', hasta: '2025-07-19', nivel: 'atencion' },
    }))
    await usuario.click(screen.getByRole('button', { name: 'Limpiar filtros' }))
    expect(await screen.findByRole('table', { name: 'Historial de alertas emitidas' })).toBeInTheDocument()
    expect(consultar).toHaveBeenLastCalledWith(expect.objectContaining({ params: {} }))
    expect(centro).toHaveValue('')
  })

  it('RF-10 avisa si el rango está invertido sin enviarlo a la API', async () => {
    const usuario = userEvent.setup()
    const consultar = vi.fn(async () => [ALERTA])
    abrir(consultar)
    await screen.findByRole('table', { name: 'Historial de alertas emitidas' })
    fireEvent.change(screen.getByLabelText('Desde'), { target: { value: '2025-07-19' } })
    fireEvent.change(screen.getByLabelText('Hasta'), { target: { value: '2025-07-06' } })
    await usuario.click(screen.getByRole('button', { name: 'Aplicar filtros' }))
    expect(screen.getByRole('alert')).toHaveTextContent('La fecha desde debe ser anterior o igual a hasta.')
    expect(consultar).toHaveBeenCalledTimes(1)
  })

  it('RF-10 descarta una respuesta anterior que llega después de aplicar un filtro', async () => {
    const usuario = userEvent.setup()
    let completarAnterior!: (filas: unknown) => void
    const consultar = vi.fn<(config?: AxiosRequestConfig) => Promise<unknown>>()
      .mockImplementationOnce(() => new Promise((resolve) => { completarAnterior = resolve }))
      .mockResolvedValue([])
    abrir(consultar)
    await waitFor(() => expect(consultar).toHaveBeenCalledTimes(1))

    await usuario.selectOptions(screen.getByLabelText('Nivel'), 'atencion')
    await usuario.click(screen.getByRole('button', { name: 'Aplicar filtros' }))
    expect(await screen.findByText('Ninguna alerta coincide con los filtros')).toBeInTheDocument()
    expect(consultar.mock.calls[0]?.[0]?.signal?.aborted).toBe(true)

    await act(async () => { completarAnterior([ALERTA]) })
    expect(screen.getByText('Ninguna alerta coincide con los filtros')).toBeInTheDocument()
    expect(screen.queryByRole('rowheader', { name: /SAR Chiguayante/ })).not.toBeInTheDocument()
  })

  it('RF-10 anuncia la carga y permite reintentar tras un error', async () => {
    const usuario = userEvent.setup()
    const consultar = vi.fn<() => Promise<unknown>>().mockResolvedValue([])
    let rechazar!: (error: Error) => void
    consultar.mockImplementationOnce(() => new Promise((_, reject) => { rechazar = reject }))
    abrir(consultar)
    expect(await screen.findByRole('status')).toHaveTextContent('Cargando historial de alertas')
    await waitFor(() => expect(consultar).toHaveBeenCalledTimes(1))
    rechazar(new Error('Red no disponible'))
    expect(await screen.findByRole('alert')).toHaveTextContent('No se pudo cargar el historial de alertas.')
    await usuario.click(screen.getByRole('button', { name: 'Reintentar' }))
    expect(await screen.findByText('Todavía no hay alertas emitidas')).toBeInTheDocument()
  })

  it('RNF-S-2 protege la ruta sin sesión', async () => {
    const peticiones = abrir(undefined, null)
    expect(await screen.findByRole('button', { name: 'Ingresar' })).toBeInTheDocument()
    expect(peticiones.mock.calls.some(([ruta]) => ruta === 'alertas/historial')).toBe(false)
  })
})
