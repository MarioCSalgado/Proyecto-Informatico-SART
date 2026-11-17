import { cleanup, render, screen, within } from '@testing-library/react'
import { userEvent } from '@testing-library/user-event'
import { MemoryRouter } from 'react-router'
import { afterEach, describe, expect, it, vi } from 'vitest'
import App from '../App.tsx'
import type { Rol } from '../acceso/permisos.ts'
import { ProveedorSesion } from '../contexto/sesion.tsx'
import clienteApi from '../servicios/clienteApi.ts'

// Partes fijas de los diseños de Figma (etapa 1 bis): estructura sin datos, con los valores de referencia
// (escala de MP2,5 y comunas) pedidos a la API, nunca escritos en la web (RNF-M-4).
const REFERENCIAS = {
  mp25_niveles: [
    { clave: 'normal', nombre: 'Normal', desde: 0, hasta: 50 },
    { clave: 'sobre_la_norma', nombre: 'Sobre la norma', desde: 51, hasta: 79 },
    { clave: 'alerta', nombre: 'Alerta', desde: 80, hasta: 109 },
    { clave: 'preemergencia', nombre: 'Preemergencia', desde: 110, hasta: 169 },
    { clave: 'emergencia', nombre: 'Emergencia', desde: 170, hasta: null },
  ],
  comunas: ['Concepción', 'Talcahuano', 'Hualpén'],
}

function abrir(ruta: string, rol: Rol, {
  referenciasFallan = false, configuracion = {} as Record<string, unknown>,
} = {}) {
  const peticiones = vi.spyOn(clienteApi, 'get').mockImplementation(async (url: string) => {
    if (url.includes('referencias')) {
      if (referenciasFallan) throw new Error('sin conexión')
      return { data: REFERENCIAS }
    }
    if (url === 'centros/estado') return { data: [] }  // sin pronósticos todavía: estados vacíos
    if (url.startsWith('administracion/')) return { data: configuracion[url] ?? [] }
    return { data: { usuario: { id: 1, nombre: `${rol} Demo`, rol } } }
  })
  render(
    <MemoryRouter initialEntries={[ruta]}>
      <ProveedorSesion>
        <App />
      </ProveedorSesion>
    </MemoryRouter>,
  )
  return peticiones
}

describe('Mi centro (jefatura)', () => {
  afterEach(() => {
    cleanup()  // desmontar antes de restaurar los mocks: así ninguna petición pendiente sale a la red
    vi.restoreAllMocks()
  })

  it('muestra la escala de MP2,5 con los límites que entrega la API, con nombre, ícono y rango', async () => {
    abrir('/mi-centro', 'Jefatura')
    const escala = await screen.findByRole('region', { name: /Calidad del aire/ })

    const niveles = await within(escala).findAllByRole('listitem')
    expect(niveles.map((n) => within(n).getByRole('heading').textContent)).toEqual([
      'Normal', 'Sobre la norma', 'Alerta', 'Preemergencia', 'Emergencia',
    ])
    expect(within(escala).getByText('51–79 µg/m³')).toBeInTheDocument()
    expect(within(escala).getByText('≥ 170 µg/m³')).toBeInTheDocument()
  })

  it('el gráfico tiene su leyenda fija aunque todavía no haya datos', async () => {
    abrir('/mi-centro', 'Jefatura')
    const leyenda = await screen.findByRole('list', { name: 'Leyenda del gráfico' })

    expect(within(leyenda).getAllByRole('listitem').map((i) => i.textContent)).toEqual([
      'Observado', 'Pronóstico', 'Intervalo 90 %', 'Umbral de alerta',
    ])
  })

  it('los botones que necesitan datos están desactivados', async () => {
    abrir('/mi-centro', 'Jefatura')

    expect(await screen.findByRole('button', { name: /Descargar CSV/ })).toBeDisabled()
    expect(screen.getByRole('button', { name: /Ver como tabla/ })).toBeDisabled()
  })

  it('no incluye la tarjeta de virus del ISP, que no está en la especificación (pendientes #22)', async () => {
    abrir('/mi-centro', 'Jefatura')
    await screen.findByRole('heading', { level: 1, name: 'Mi centro' })

    expect(screen.queryByText(/Virus circulando/)).not.toBeInTheDocument()
  })

  it('si la API no entrega las referencias, la escala lo dice en vez de quedar en blanco', async () => {
    abrir('/mi-centro', 'Jefatura', { referenciasFallan: true })

    expect(await screen.findByText(/No se pudo cargar la escala/)).toBeInTheDocument()
  })
})

describe('Red de centros (subdirector)', () => {
  afterEach(() => {
    cleanup()  // desmontar antes de restaurar los mocks: así ninguna petición pendiente sale a la red
    vi.restoreAllMocks()
  })

  it('el filtro de comunas usa las comunas de la API', async () => {
    abrir('/red', 'Subdirector')
    const comuna = await screen.findByLabelText('Comuna')

    await screen.findByRole('option', { name: 'Talcahuano' })
    expect(within(comuna).getAllByRole('option').map((o) => o.textContent)).toEqual([
      'Todas las comunas (3)', 'Concepción', 'Talcahuano', 'Hualpén',
    ])
  })

  it('la tabla de seguimiento tiene sus columnas y un estado vacío que orienta', async () => {
    abrir('/red', 'Subdirector')
    const tabla = await screen.findByRole('table', { name: /Seguimiento de centros/ })

    const columnas = within(tabla).getAllByRole('columnheader').map((c) => c.textContent)
    expect(columnas).toEqual(['Centro', 'Comuna', 'Pronóstico', 'Nivel', 'Confirmación', 'Últimas 12 semanas'])
    // el mensaje de vacío queda fuera de la tabla desplazable, para leerse completo en celular
    const seccion = screen.getByRole('region', { name: 'Seguimiento de centros' })
    expect(within(seccion).getByText('Todavía no hay pronósticos de la red')).toBeVisible()
  })

  it('el resumen por nivel muestra cada nivel con texto, no solo color (RNF-U-1)', async () => {
    abrir('/red', 'Subdirector')
    const resumen = await screen.findByRole('list', { name: 'Resumen de la red' })

    expect(within(resumen).getByText('Centros en la red')).toBeInTheDocument()
    for (const nivel of ['Alerta', 'Atención', 'Normal']) {
      expect(within(resumen).getByText(nivel)).toBeInTheDocument()
    }
  })
})

describe('Administración', () => {
  afterEach(() => {
    cleanup()  // desmontar antes de restaurar los mocks: así ninguna petición pendiente sale a la red
    vi.restoreAllMocks()
  })

  it('RF-9 conserva Usuarios, permite actualizar k y consulta la auditoría al abrir Historial', async () => {
    const usuario = userEvent.setup()
    const clave = 'regla_alerta.k_margen'
    const configuracion: Record<string, unknown> = {
      'administracion/umbrales': [{
        centro: { codigo_deis: 100001, nombre: 'SAR de prueba' },
        umbral: { umbral_atencion: 650, umbral_alerta: 713, origen: 'calculado', anios_usados: null },
      }],
      'administracion/parametros': [{ clave, valor: 0.4 }],
    }
    const peticiones = abrir('/administracion', 'Administrador', { configuracion })
    const guardar = vi.spyOn(clienteApi, 'put').mockImplementation(async (_ruta, datos) => {
      const { valor, motivo } = datos as { valor: number; motivo: string }
      const parametro = { clave, valor }
      configuracion['administracion/parametros'] = [parametro]
      configuracion['administracion/historial'] = [{
        fecha: '2025-07-07T09:00:00Z', autor_id: 1, autor_rol: 'administrador', accion: 'cambio_parametro',
        entidad_id: clave, valor_anterior: 0.4, valor_nuevo: valor, motivo, centro: null,
      }]
      return { data: parametro }
    })

    const pestanas = await screen.findAllByRole('tab')
    expect(pestanas.map((p) => p.textContent)).toEqual(['Usuarios', 'Umbrales', 'Historial'])

    const usuarios = await screen.findByRole('table', { name: /Usuarios y permisos/ })
    expect(within(usuarios).getAllByRole('columnheader').map((c) => c.textContent)).toEqual([
      'Usuario / correo', 'Rol', 'Centro o alcance', 'Acción',
    ])

    await usuario.click(screen.getByRole('tab', { name: 'Umbrales' }))
    expect(screen.getByRole('heading', { name: 'Umbrales por centro' })).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: 'Parámetros editables' })).toBeInTheDocument()
    await screen.findByRole('option', { name: 'SAR de prueba' })
    await usuario.selectOptions(screen.getByLabelText('Centro a configurar'), '100001')
    expect(screen.getByLabelText('Alerta desde')).toHaveValue(713)
    await screen.findByRole('option', { name: 'Margen de alerta (k)' })
    await usuario.selectOptions(screen.getByLabelText('Parámetro a configurar'), clave)
    const valor = screen.getByLabelText('Valor del parámetro')
    expect(valor).toHaveValue(0.4)
    await usuario.clear(valor)
    await usuario.type(valor, '0')
    await usuario.type(screen.getByLabelText('Motivo del ajuste'), 'Cambio para TC-17')
    await usuario.click(screen.getByRole('button', { name: 'Guardar parámetro' }))
    expect(await screen.findByText('Parámetro guardado.')).toBeInTheDocument()
    expect(guardar).toHaveBeenCalledWith(`administracion/parametros/${clave}`, { valor: 0, motivo: 'Cambio para TC-17' })

    await usuario.click(screen.getByRole('tab', { name: 'Historial' }))
    const historial = await screen.findByRole('table', { name: /Historial de cambios/ })
    expect(peticiones).toHaveBeenCalledWith('administracion/historial', expect.objectContaining({ signal: expect.anything() }))
    expect(within(historial).getByRole('row', { name: /Margen de alerta.*Cambio para TC-17/ }))
      .toHaveTextContent('0,4')

    await usuario.click(screen.getByRole('tab', { name: 'Umbrales' }))
    await screen.findByRole('option', { name: 'Margen de alerta (k)' })
    await usuario.selectOptions(screen.getByLabelText('Parámetro a configurar'), clave)
    expect(screen.getByLabelText('Valor del parámetro')).toHaveValue(0)
  })

  it.each(['Jefatura', 'Subdirector'] as const)('RNF-S-2 impide que %s abra la configuración', async (rol) => {
    const peticiones = abrir('/administracion', rol)
    expect(await screen.findByText('Acceso restringido')).toBeInTheDocument()
    expect(screen.queryByRole('tab', { name: 'Umbrales' })).not.toBeInTheDocument()
    expect(peticiones.mock.calls.some(([ruta]) => ruta.startsWith('administracion/'))).toBe(false)
  })
})
