import { cleanup, render, screen, within } from '@testing-library/react'
import { userEvent } from '@testing-library/user-event'
import { AxiosError, AxiosHeaders } from 'axios'
import { MemoryRouter } from 'react-router'
import { afterEach, describe, expect, it, vi } from 'vitest'
import type { ReactNode } from 'react'
import App from '../App.tsx'
import type { Rol } from '../acceso/permisos.ts'
import { ProveedorSesion } from '../contexto/sesion.tsx'
import clienteApi from '../servicios/clienteApi.ts'
import type { EstadoCentro, NivelAlerta } from '../tipos/index.ts'

// RF-7 con datos: lo que entrega GET /centros/estado se muestra en Mi centro, en la red y en el detalle.

vi.mock('react-leaflet', async () => {
  const React = await import('react')
  return {
    MapContainer: ({ children }: { children: ReactNode }) =>
      React.createElement('div', { 'data-testid': 'mapa-centros' }, children),
    TileLayer: () => null,
    CircleMarker: ({ children, center, pathOptions }: {
      children: ReactNode
      center: [number, number]
      pathOptions: { fillColor: string }
    }) => {
      const [abierto, setAbierto] = React.useState(false)
      const [rotulo, popup] = React.Children.toArray(children)
      return React.createElement(
        'div',
        { 'data-testid': 'marcador-centro', 'data-posicion': center.join(','), 'data-color': pathOptions.fillColor },
        rotulo,
        React.createElement('button', { type: 'button', onClick: () => setAbierto(true) }, 'Abrir detalles'),
        abierto ? popup : null,
      )
    },
    Tooltip: ({ children, className }: { children: ReactNode; className?: string }) =>
      React.createElement('span', { className }, children),
    Popup: ({ children }: { children: ReactNode }) => React.createElement('div', null, children),
    useMap: () => ({ fitBounds: vi.fn(), setView: vi.fn() }),
  }
})

const REFERENCIAS = {
  mp25_niveles: [
    { clave: 'normal', nombre: 'Normal', desde: 0, hasta: 50 },
    { clave: 'sobre_la_norma', nombre: 'Sobre la norma', desde: 51, hasta: 79 },
    { clave: 'alerta', nombre: 'Alerta', desde: 80, hasta: 109 },
    { clave: 'preemergencia', nombre: 'Preemergencia', desde: 110, hasta: 169 },
    { clave: 'emergencia', nombre: 'Emergencia', desde: 170, hasta: null },
  ],
  comunas: ['Chiguayante', 'Concepción'],
}

function semanas(nivel: NivelAlerta) {
  return Array.from({ length: 12 }, (_, i) => {
    const inicio = new Date(2026, 6, 12 + 7 * i)
    const iso = `${inicio.getFullYear()}-${String(inicio.getMonth() + 1).padStart(2, '0')}-${String(inicio.getDate()).padStart(2, '0')}`
    return { anio: 2026, semana: 28 + i, inicio: iso, consultas: 600 + 10 * i, nivel_observado: nivel }
  })
}

function centro(codigo: number, nombre: string, comuna: string, nivel: NivelAlerta, valor: number,
  extra: Partial<EstadoCentro['pronostico']> = {}): EstadoCentro {
  return {
    centro: {
      codigo_deis: codigo,
      nombre,
      tipo: 'SAR',
      comuna,
      latitud: -36.8 - (codigo % 100) / 1000,
      longitud: -73.0 - (codigo % 100) / 1000,
      estacion_asignada: 'Kingston College',
    },
    pronostico: {
      anio: 2026, semana: 40, inicio_semana: '2026-10-04', fecha_corte: '2026-09-27',
      valor, limite_inferior: valor - 60, limite_superior: valor + 60, nivel,
      valor_con_margen: valor + 15, k_margen: 0.4, version_modelo: 'glm-quasipoisson/solo_rezagos/v1',
      desactualizado: false, datos_antiguos: false,
      umbrales: { atencion: 650, alerta: 713, origen: 'calculado' },
      ...extra,
    },
    dotacion: {
      profesionales: 3, llegadas_hora_punta: 7.1, espera_media_min: 4.2, espera_con_uno_menos_min: 55,
      supuestos: { minutos_por_atencion: 15, factor_hora_punta: 1.6, horas_funcionamiento_semana: 123,
        espera_objetivo_min: 30, supuestos_validados: false },
      por_validar: true,
    },
    mp25: { estado: 'ok', estacion: 'Kingston College', de_respaldo: true, fecha: '2026-10-04', valor: 23.4,
      nivel: { clave: 'normal', nombre: 'Normal' } },
    ultimas_semanas: semanas(nivel),
  }
}

const CHIGUAYANTE = centro(100001, 'SAR Chiguayante', 'Chiguayante', 'alerta', 760)
const LORENZO = centro(100002, 'SAPU Lorenzo Arenas', 'Concepción', 'normal', 300)

function abrir(ruta: string, rol: Rol, centros: EstadoCentro[]) {
  vi.spyOn(clienteApi, 'get').mockImplementation(async (url: string) => {
    if (url.includes('referencias')) return { data: REFERENCIAS }
    if (url === 'centros/estado') return { data: centros }
    const detalle = /^centros\/(\d+)\/estado$/.exec(url)
    if (detalle) {
      const encontrado = centros.find((c) => c.centro.codigo_deis === Number(detalle[1]))
      if (!encontrado) {
        throw new AxiosError('Prohibido', '403', undefined, undefined,
          { status: 403, data: {}, statusText: '', headers: {}, config: { headers: new AxiosHeaders() } })
      }
      return { data: encontrado }
    }
    return { data: { usuario: { id: 1, nombre: `${rol} Demo`, rol } } }
  })
  return render(
    <MemoryRouter initialEntries={[ruta]}>
      <ProveedorSesion>
        <App />
      </ProveedorSesion>
    </MemoryRouter>,
  )
}

afterEach(() => {
  cleanup()
  vi.restoreAllMocks()
})

describe('Mi centro con datos (RF-7)', () => {
  it('muestra el pronóstico, su rango, el nivel con texto y la fecha de corte', async () => {
    abrir('/mi-centro', 'Jefatura', [CHIGUAYANTE])

    expect(await screen.findByRole('heading', { level: 1, name: 'SAR Chiguayante' })).toBeInTheDocument()
    const bloque = screen.getByRole('region', { name: 'Pronóstico de consultas' })
    expect(within(bloque).getByText('760')).toBeInTheDocument()
    expect(within(bloque).getByText('700 a 820')).toBeInTheDocument()
    expect(within(bloque).getByText('Alerta')).toBeInTheDocument()  // RNF-U-1: con texto
    expect(within(bloque).getByText(/Atención sobre 650 · Alerta sobre 713/)).toBeInTheDocument()
    expect(within(bloque).getByText(/hasta la semana del 27 sept al 3 oct/)).toBeInTheDocument()
    expect(within(bloque).getByRole('img', { name: /pronóstico de la SE 40: 760/ })).toBeInTheDocument()
  })

  it('la dotación guardada muestra la espera, la alternativa y los supuestos por validar (RF-6)', async () => {
    abrir('/mi-centro', 'Jefatura', [CHIGUAYANTE])
    const dotacion = await screen.findByRole('region', { name: 'Dotación sugerida' })

    expect(within(dotacion).getByText('3')).toBeInTheDocument()
    expect(within(dotacion).getByText(/Espera media de 4,2 min/)).toBeInTheDocument()
    expect(within(dotacion).getByText(/Con 2, la espera sería de 55 min/)).toBeInTheDocument()
    expect(within(dotacion).getByText('Supuestos por validar (RF-6)')).toBeInTheDocument()
  })

  it('el MP2,5 de la zona dice si viene de la estación de respaldo (RB-5)', async () => {
    abrir('/mi-centro', 'Jefatura', [CHIGUAYANTE])
    const escala = await screen.findByRole('region', { name: /Calidad del aire/ })

    expect(within(escala).getByText('23,4')).toBeInTheDocument()
    expect(within(escala).getByText('de respaldo')).toBeInTheDocument()
    expect(within(escala).getByText('Ahora')).toBeInTheDocument()
  })

  it('«Ver como tabla» muestra las mismas cifras en una tabla', async () => {
    const usuario = userEvent.setup()
    abrir('/mi-centro', 'Jefatura', [CHIGUAYANTE])

    await usuario.click(await screen.findByRole('button', { name: /Ver como tabla/ }))
    const tabla = screen.getByRole('table', { name: /Consultas respiratorias semanales/ })
    expect(within(tabla).getAllByRole('row')).toHaveLength(1 + 12 + 1)  // encabezado, 12 semanas y pronóstico
    expect(screen.getByRole('button', { name: /Ver como gráfico/ })).toBeInTheDocument()
  })

  it('avisa si el pronóstico está desactualizado o los datos son antiguos (RF-3 E2, RF-7 E1)', async () => {
    abrir('/mi-centro', 'Jefatura', [centro(100001, 'SAR Chiguayante', 'Chiguayante', 'normal', 500,
      { desactualizado: true, datos_antiguos: true })])

    expect(await screen.findByText('Pronóstico desactualizado.')).toBeInTheDocument()
    expect(screen.getByText('Datos antiguos.')).toBeInTheDocument()
  })

  it('con dos centros asignados, la jefatura elige cuál ver', async () => {
    const usuario = userEvent.setup()
    abrir('/mi-centro', 'Jefatura', [CHIGUAYANTE, LORENZO])

    await usuario.selectOptions(await screen.findByLabelText('Centro'), 'SAPU Lorenzo Arenas')
    expect(screen.getByRole('heading', { level: 1, name: 'SAPU Lorenzo Arenas' })).toBeInTheDocument()
  })
})

describe('Red de centros con datos (RF-7)', () => {
  it('cuenta los centros por nivel y los lista en el orden de la API, con su calendario', async () => {
    abrir('/red', 'Subdirector', [CHIGUAYANTE, LORENZO])
    const tabla = await screen.findByRole('table', { name: /Seguimiento de centros/ })  // aparece con los datos
    const resumen = screen.getByRole('list', { name: 'Resumen de la red' })

    const kpis = within(resumen).getAllByRole('listitem').map((k) => k.textContent)
    expect(kpis).toEqual(['2Centros en la red', '1Alerta', '0Atención', '1Normal'])
    const filas = within(tabla).getAllByRole('row').slice(1)
    expect(filas.map((f) => within(f).getByRole('link').textContent)).toEqual(['SAR Chiguayante', 'SAPU Lorenzo Arenas'])
    expect(within(filas[0]!).getByRole('link')).toHaveAttribute('href', '/red/100001')
    const calendario = within(filas[0]!).getByRole('list', { name: /Nivel observado de SAR Chiguayante/ })
    expect(within(calendario).getAllByRole('listitem')).toHaveLength(12)
  })

  it('los filtros por comuna y por nombre o código funcionan', async () => {
    const usuario = userEvent.setup()
    abrir('/red', 'Subdirector', [CHIGUAYANTE, LORENZO])
    const tabla = await screen.findByRole('table', { name: /Seguimiento de centros/ })

    await usuario.selectOptions(screen.getByLabelText('Comuna'), 'Concepción')
    expect(within(tabla).getAllByRole('link').map((l) => l.textContent)).toEqual(['SAPU Lorenzo Arenas'])
    expect(within(screen.getByRole('region', { name: 'Mapa de centros' })).getAllByTestId('marcador-centro'))
      .toHaveLength(1)

    await usuario.selectOptions(screen.getByLabelText('Comuna'), '')
    await usuario.type(screen.getByLabelText('Buscar centro'), 'chiguay')
    expect(within(tabla).getAllByRole('link').map((l) => l.textContent)).toEqual(['SAR Chiguayante'])

    await usuario.clear(screen.getByLabelText('Buscar centro'))
    await usuario.type(screen.getByLabelText('Buscar centro'), 'zzz')
    expect(screen.getByText('Ningún centro coincide con los filtros')).toBeInTheDocument()
    expect(screen.getByText('No hay centros para mostrar en el mapa con esos filtros.')).toBeInTheDocument()
  })

  it('TC-20: representa cada centro de la respuesta con nivel y estación asignada', async () => {
    const estados = Array.from({ length: 33 }, (_, i) => {
      const nivel: NivelAlerta = i % 3 === 0 ? 'alerta' : i % 3 === 1 ? 'atencion' : 'normal'
      return centro(200000 + i, `Centro ${i + 1}`, 'Concepción', nivel, 500 + i)
    })
    abrir('/red', 'Subdirector', estados)

    const mapa = await screen.findByRole('region', { name: 'Mapa de centros' })
    const marcadores = within(mapa).getAllByTestId('marcador-centro')
    expect(marcadores).toHaveLength(33)
    expect(marcadores[0]).toHaveAttribute('data-posicion', '-36.8,-73')
    expect(marcadores[0]).toHaveAttribute('data-color', '#ad430c')
    expect(within(mapa).getAllByText('Alerta', { selector: '.mapa-centros__rotulo' })).toHaveLength(11)
    expect(within(mapa).getAllByText('Atención', { selector: '.mapa-centros__rotulo' })).toHaveLength(11)
    expect(within(mapa).getAllByText('Normal', { selector: '.mapa-centros__rotulo' })).toHaveLength(11)
    await userEvent.click(within(marcadores[0]!).getByRole('button', { name: 'Abrir detalles' }))
    expect(within(marcadores[0]!).getByText('Estación asignada: Kingston College')).toBeInTheDocument()
  })

  it('avisa si los centros recibidos no tienen coordenadas válidas', async () => {
    const sinCoordenadas = {
      ...CHIGUAYANTE,
      centro: { ...CHIGUAYANTE.centro, latitud: null, longitud: null },
    }
    abrir('/red', 'Subdirector', [sinCoordenadas])

    expect(await screen.findByRole('status')).toHaveTextContent(
      'No hay centros con coordenadas válidas para mostrar.',
    )
  })

  it('el detalle de un centro se abre desde la red (RF-7 paso 3)', async () => {
    abrir('/red/100002', 'Subdirector', [CHIGUAYANTE, LORENZO])

    expect(await screen.findByRole('heading', { level: 1, name: 'SAPU Lorenzo Arenas' })).toBeInTheDocument()
    expect(screen.getByRole('link', { name: /Volver a la red/ })).toHaveAttribute('href', '/red')
  })

  it('si la API niega el centro, lo dice (RF-7 E2)', async () => {
    abrir('/red/999999', 'Subdirector', [CHIGUAYANTE])

    expect(await screen.findByText('Su cuenta no tiene acceso a este centro.')).toBeInTheDocument()
  })
})
