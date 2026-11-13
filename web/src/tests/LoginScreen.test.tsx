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
          <Route path="/centros" element={<p>pantalla de centros</p>} />
        </Routes>
      </MemoryRouter>
    </AuthProvider>,
  )
}

describe('LoginScreen con MFA de administradores (RNF-S-1)', () => {
  afterEach(() => vi.restoreAllMocks())

  it('pide el código cuando la API lo exige y entra al enviarlo', async () => {
    vi.spyOn(axiosInstance, 'get').mockRejectedValue(new Error('sin sesión'))
    const post = vi
      .spyOn(axiosInstance, 'post')
      .mockResolvedValueOnce({ data: { mfa_requerido: true } })
      .mockResolvedValueOnce({ data: { usuario: { id: 3, nombre: 'Admin', rol: 'Administrador' } } })
    const usuario = userEvent.setup()
    pantalla()

    await usuario.type(await screen.findByLabelText(/Correo institucional/), 'admin@demo.sart')
    await usuario.type(screen.getByLabelText(/Contraseña/), 'clave larga de prueba')
    expect(screen.queryByLabelText(/Código de verificación/)).not.toBeInTheDocument()
    await usuario.click(screen.getByRole('button', { name: /Iniciar sesión/ }))

    const campoCodigo = await screen.findByLabelText(/Código de verificación/)
    expect(screen.getByText(/aplicación de autenticación/)).toBeInTheDocument()
    await usuario.type(campoCodigo, '123456')
    await usuario.click(screen.getByRole('button', { name: /Verificar/ }))

    expect(await screen.findByText('pantalla de centros')).toBeInTheDocument()
    expect(post.mock.calls[1]?.[1]).toEqual({
      correo: 'admin@demo.sart',
      contrasena: 'clave larga de prueba',
      codigo: '123456',
    })
  })

  it('una jefatura entra sin que aparezca el campo de código', async () => {
    vi.spyOn(axiosInstance, 'get').mockRejectedValue(new Error('sin sesión'))
    vi.spyOn(axiosInstance, 'post').mockResolvedValue({
      data: { usuario: { id: 1, nombre: 'Jefatura', rol: 'Jefatura' } },
    })
    const usuario = userEvent.setup()
    pantalla()

    await usuario.type(await screen.findByLabelText(/Correo institucional/), 'jefatura@demo.sart')
    await usuario.type(screen.getByLabelText(/Contraseña/), 'clave larga de prueba')
    await usuario.click(screen.getByRole('button', { name: /Iniciar sesión/ }))

    expect(await screen.findByText('pantalla de centros')).toBeInTheDocument()
  })
})
