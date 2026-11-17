import { cleanup, render, screen, within } from '@testing-library/react'
import { MemoryRouter } from 'react-router'
import { afterEach, describe, expect, it, vi } from 'vitest'
import App from '../App.tsx'
import type { Rol } from '../acceso/permisos.ts'
import { rutaInicio } from '../acceso/rutas.ts'
import { ProveedorSesion } from '../contexto/sesion.tsx'
import clienteApi from '../servicios/clienteApi.ts'

const NOMBRES: Record<Rol, string> = {
  Jefatura: 'Jefatura Demo',
  Subdirector: 'Subdirector Demo',
  Administrador: 'Administrador Demo',
}

function abrir(ruta: string, rol: Rol) {
  vi.spyOn(clienteApi, 'get').mockImplementation(async (url: string) =>
    url.includes('referencias')
      ? { data: { mp25_niveles: [], comunas: [] } }
      : { data: { usuario: { id: 1, nombre: NOMBRES[rol], rol } } },
  )
  return render(
    <MemoryRouter initialEntries={[ruta]}>
      <ProveedorSesion>
        <App />
      </ProveedorSesion>
    </MemoryRouter>,
  )
}

describe('pantalla de inicio según el rol (RNF-S-2)', () => {
  afterEach(() => {
    cleanup()  // desmontar antes de restaurar los mocks: así ninguna petición pendiente sale a la red
    vi.restoreAllMocks()
  })

  it('cada rol tiene su pantalla de inicio', () => {
    expect(rutaInicio('Jefatura')).toBe('/mi-centro')
    expect(rutaInicio('Subdirector')).toBe('/red')
    expect(rutaInicio('Administrador')).toBe('/administracion')
  })

  it.each([
    ['Jefatura', 'Mi centro'],
    ['Subdirector', 'Red de centros'],
    ['Administrador', 'Administración'],
  ] as const)('%s llega desde / a «%s»', async (rol, titulo) => {
    abrir('/', rol)

    expect(await screen.findByRole('heading', { level: 1, name: titulo })).toBeInTheDocument()
  })

  it('una jefatura no entra a administración ni a la red', async () => {
    abrir('/administracion', 'Jefatura')
    expect(await screen.findByText('Acceso restringido')).toBeInTheDocument()
  })
})

describe('encabezado', () => {
  afterEach(() => {
    cleanup()  // desmontar antes de restaurar los mocks: así ninguna petición pendiente sale a la red
    vi.restoreAllMocks()
  })

  it('muestra nombre y rol, y un botón para salir con nombre accesible', async () => {
    abrir('/red', 'Subdirector')
    const encabezado = await screen.findByRole('banner')

    expect(within(encabezado).getByText('Subdirector Demo')).toBeInTheDocument()
    expect(within(encabezado).getByText('Subdirector')).toBeInTheDocument()
    expect(within(encabezado).getByRole('button', { name: 'Cerrar sesión' })).toBeInTheDocument()
  })

  it.each([
    ['Jefatura', ['Mi centro', 'Historial de alertas']],
    ['Subdirector', ['Red de centros', 'Historial de alertas']],
    ['Administrador', ['Red de centros', 'Historial de alertas', 'Administración']],
  ] as const)('%s ve solo sus secciones en la navegación', async (rol, secciones) => {
    abrir(rutaInicio(rol), rol)
    const navegacion = await screen.findByRole('navigation', { name: 'Secciones' })

    expect(within(navegacion).getAllByRole('link').map((enlace) => enlace.textContent)).toEqual(secciones)
  })

  it('el pie recuerda que la herramienta no reemplaza el criterio clínico', async () => {
    abrir('/mi-centro', 'Jefatura')

    expect(await screen.findByText(/no reemplaza el criterio clínico/)).toBeInTheDocument()
  })
})
