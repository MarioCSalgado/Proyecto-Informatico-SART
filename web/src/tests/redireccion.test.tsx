import { cleanup, render, screen } from '@testing-library/react'
import { userEvent } from '@testing-library/user-event'
import { MemoryRouter } from 'react-router'
import { afterEach, describe, expect, it, vi } from 'vitest'
import App from '../App.tsx'
import { ProveedorSesion } from '../contexto/sesion.tsx'
import clienteApi from '../servicios/clienteApi.ts'

// Tras iniciar sesión se vuelve a la página que se quería abrir, pero solo si el rol puede verla (RNF-S-2).
function entrarDesde(ruta: string, rol: 'Jefatura' | 'Subdirector') {
  vi.spyOn(clienteApi, 'get').mockImplementation(async (url: string) => {
    if (url.includes('referencias')) return { data: { mp25_niveles: [], comunas: [] } }
    throw new Error('sin sesión')
  })
  vi.spyOn(clienteApi, 'post').mockResolvedValue({ data: { usuario: { id: 1, nombre: `${rol} Demo`, rol } } })
  render(
    <MemoryRouter initialEntries={[ruta]}>
      <ProveedorSesion>
        <App />
      </ProveedorSesion>
    </MemoryRouter>,
  )
}

async function iniciarSesion() {
  const usuario = userEvent.setup()
  await usuario.type(await screen.findByLabelText('Correo institucional'), 'x@demo.sart')
  await usuario.type(screen.getByLabelText('Contraseña'), 'prueba123456')
  await usuario.click(screen.getByRole('button', { name: /Ingresar/ }))
}

describe('a dónde se llega después de iniciar sesión', () => {
  afterEach(() => {
    cleanup()
    vi.restoreAllMocks()
  })

  it('una jefatura que venía de /red llega a su centro, no a «Acceso restringido»', async () => {
    entrarDesde('/red', 'Jefatura')
    await iniciarSesion()

    expect(await screen.findByRole('heading', { level: 1, name: 'Mi centro' })).toBeInTheDocument()
    expect(screen.queryByText('Acceso restringido')).not.toBeInTheDocument()
  })

  it('un subdirector que venía de /red vuelve a /red', async () => {
    entrarDesde('/red', 'Subdirector')
    await iniciarSesion()

    expect(await screen.findByRole('heading', { level: 1, name: 'Red de centros' })).toBeInTheDocument()
  })
})
