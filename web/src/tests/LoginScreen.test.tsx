import { render, screen } from '@testing-library/react'
import { userEvent } from '@testing-library/user-event'
import { MemoryRouter, Route, Routes } from 'react-router'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { AuthProvider } from '../context/authContext.tsx'
import { LoginScreen } from '../screens/LoginScreen.tsx'
import axiosInstance from '../services/axiosInstance.ts'

function pantalla() {
  return render(
    <AuthProvider>
      <MemoryRouter initialEntries={['/login']}>
        <Routes>
          <Route path="/login" element={<LoginScreen />} />
          <Route path="/mi-centro" element={<p>pantalla de mi centro</p>} />
          <Route path="/administracion" element={<p>pantalla de administración</p>} />
        </Routes>
      </MemoryRouter>
    </AuthProvider>,
  )
}

async function escribirCredenciales(usuario: ReturnType<typeof userEvent.setup>, correo: string) {
  await usuario.type(await screen.findByLabelText('Correo institucional'), correo)
  await usuario.type(screen.getByLabelText('Contraseña'), 'clave larga de prueba')
}

describe('LoginScreen (RNF-S-1)', () => {
  afterEach(() => vi.restoreAllMocks())

  it('una jefatura entra y llega a su centro, sin campo de código', async () => {
    vi.spyOn(axiosInstance, 'get').mockRejectedValue(new Error('sin sesión'))
    vi.spyOn(axiosInstance, 'post').mockResolvedValue({
      data: { usuario: { id: 1, nombre: 'Jefatura', rol: 'Jefatura' } },
    })
    const usuario = userEvent.setup()
    pantalla()

    await escribirCredenciales(usuario, 'jefatura@demo.sart')
    expect(screen.queryByLabelText('Código de verificación')).not.toBeInTheDocument()
    await usuario.click(screen.getByRole('button', { name: /Ingresar/ }))

    expect(await screen.findByText('pantalla de mi centro')).toBeInTheDocument()
  })

  it('a un administrador le pide el código y entra al enviarlo', async () => {
    vi.spyOn(axiosInstance, 'get').mockRejectedValue(new Error('sin sesión'))
    const post = vi
      .spyOn(axiosInstance, 'post')
      .mockResolvedValueOnce({ data: { mfa_requerido: true } })
      .mockResolvedValueOnce({ data: { usuario: { id: 3, nombre: 'Admin', rol: 'Administrador' } } })
    const usuario = userEvent.setup()
    pantalla()

    await escribirCredenciales(usuario, 'admin@demo.sart')
    await usuario.click(screen.getByRole('button', { name: /Ingresar/ }))

    const campoCodigo = await screen.findByLabelText('Código de verificación')
    expect(screen.getByText(/aplicación de autenticación/)).toBeInTheDocument()
    await usuario.type(campoCodigo, '12a3 456')  // solo se aceptan dígitos
    await usuario.click(screen.getByRole('button', { name: /Verificar/ }))

    expect(await screen.findByText('pantalla de administración')).toBeInTheDocument()
    expect(post.mock.calls[1]?.[1]).toEqual({
      correo: 'admin@demo.sart',
      contrasena: 'clave larga de prueba',
      codigo: '123456',
    })
  })

  it('el botón del ojo muestra y oculta la contraseña', async () => {
    vi.spyOn(axiosInstance, 'get').mockRejectedValue(new Error('sin sesión'))
    const usuario = userEvent.setup()
    pantalla()
    const campo = await screen.findByLabelText('Contraseña')

    expect(campo).toHaveAttribute('type', 'password')
    await usuario.click(screen.getByRole('button', { name: 'Mostrar contraseña' }))
    expect(campo).toHaveAttribute('type', 'text')
    await usuario.click(screen.getByRole('button', { name: 'Ocultar contraseña' }))
    expect(campo).toHaveAttribute('type', 'password')
  })

  it('muestra el error de la API en un aviso con rol de alerta', async () => {
    vi.spyOn(axiosInstance, 'get').mockRejectedValue(new Error('sin sesión'))
    vi.spyOn(axiosInstance, 'post').mockRejectedValue(new Error('caída'))
    const usuario = userEvent.setup()
    pantalla()

    await escribirCredenciales(usuario, 'jefatura@demo.sart')
    await usuario.click(screen.getByRole('button', { name: /Ingresar/ }))

    expect(await screen.findByRole('alert')).toHaveTextContent('Error al iniciar sesión')
  })
})
