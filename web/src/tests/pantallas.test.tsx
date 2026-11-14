import { cleanup, render, screen, within } from '@testing-library/react'
import { userEvent } from '@testing-library/user-event'
import { MemoryRouter } from 'react-router'
import { afterEach, describe, expect, it, vi } from 'vitest'
import App from '../App.tsx'
import type { Role } from '../auth/permissions.ts'
import { AuthProvider } from '../context/authContext.tsx'
import axiosInstance from '../services/axiosInstance.ts'

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

function abrir(ruta: string, rol: Role, { referenciasFallan = false } = {}) {
  vi.spyOn(axiosInstance, 'get').mockImplementation(async (url: string) => {
    if (url.includes('referencias')) {
      if (referenciasFallan) throw new Error('sin conexión')
      return { data: REFERENCIAS }
    }
    return { data: { usuario: { id: 1, nombre: `${rol} Demo`, rol } } }
  })
  return render(
    <MemoryRouter initialEntries={[ruta]}>
      <AuthProvider>
        <App />
      </AuthProvider>
    </MemoryRouter>,
  )
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

  it('tiene tres pestañas y cada una muestra su sección', async () => {
    const usuario = userEvent.setup()
    abrir('/administracion', 'Administrador')

    const pestanas = await screen.findAllByRole('tab')
    expect(pestanas.map((p) => p.textContent)).toEqual(['Usuarios', 'Umbrales', 'Historial'])

    const usuarios = screen.getByRole('table', { name: /Usuarios y permisos/ })
    expect(within(usuarios).getAllByRole('columnheader').map((c) => c.textContent)).toEqual([
      'Usuario / correo', 'Rol', 'Centro o alcance', 'Acción',
    ])

    await usuario.click(screen.getByRole('tab', { name: 'Umbrales' }))
    expect(screen.getByRole('heading', { name: 'Umbrales por centro' })).toBeInTheDocument()
    expect(screen.getByLabelText('Motivo del cambio')).toBeDisabled()

    await usuario.click(screen.getByRole('tab', { name: 'Historial' }))
    const historial = screen.getByRole('table', { name: /Historial de cambios/ })
    expect(within(historial).getAllByRole('columnheader').map((c) => c.textContent)).toEqual([
      'Fecha', 'Autor', 'Centro', 'Anterior → nuevo', 'Motivo',
    ])
  })
})
