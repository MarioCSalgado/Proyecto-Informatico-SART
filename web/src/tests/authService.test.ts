import { AxiosError, AxiosHeaders } from 'axios'
import { afterEach, describe, expect, it, vi } from 'vitest'
import axiosInstance from '../services/axiosInstance.ts'
import { iniciarSesion } from '../services/authService.ts'

function errorHttp(status: number, detail?: string): AxiosError {
  const config = { headers: new AxiosHeaders() }
  return new AxiosError('error', 'ERR', config, null, {
    status,
    statusText: '',
    headers: {},
    config,
    data: detail ? { detail } : {},
  })
}

describe('iniciarSesion (RNF-S-1)', () => {
  afterEach(() => vi.restoreAllMocks())

  it('devuelve el usuario que entrega la API', async () => {
    const usuario = { id: 1, nombre: 'Jefatura Demo', rol: 'Jefatura' }
    vi.spyOn(axiosInstance, 'post').mockResolvedValue({ data: { usuario } })

    await expect(iniciarSesion('jefatura@demo.sart', 'clave')).resolves.toEqual(usuario)
  })

  it('con 401 dice que el correo o la contraseña son incorrectos', async () => {
    vi.spyOn(axiosInstance, 'post').mockRejectedValue(errorHttp(401))

    await expect(iniciarSesion('a@b.cl', 'x')).rejects.toThrow('Correo o contraseña incorrectos.')
  })

  it('con 403 muestra el motivo que da la API (MFA de administradores)', async () => {
    vi.spyOn(axiosInstance, 'post').mockRejectedValue(errorHttp(403, 'Las cuentas de administrador requieren MFA.'))

    await expect(iniciarSesion('admin@demo.sart', 'x')).rejects.toThrow('requieren MFA')
  })
})
