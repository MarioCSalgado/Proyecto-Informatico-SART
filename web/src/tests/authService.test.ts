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

    await expect(iniciarSesion('jefatura@demo.sart', 'clave')).resolves.toEqual({ tipo: 'sesion', usuario })
  })

  it('avisa cuando la API pide el código MFA (administradores)', async () => {
    vi.spyOn(axiosInstance, 'post').mockResolvedValue({ data: { mfa_requerido: true } })

    await expect(iniciarSesion('admin@demo.sart', 'clave')).resolves.toEqual({ tipo: 'mfa_requerido' })
  })

  it('envía el código solo cuando lo hay', async () => {
    const post = vi.spyOn(axiosInstance, 'post').mockResolvedValue({ data: { mfa_requerido: true } })

    await iniciarSesion('a@b.cl', 'clave')
    await iniciarSesion('a@b.cl', 'clave', '123456')

    expect(post.mock.calls[0]?.[1]).toEqual({ correo: 'a@b.cl', contrasena: 'clave' })
    expect(post.mock.calls[1]?.[1]).toEqual({ correo: 'a@b.cl', contrasena: 'clave', codigo: '123456' })
  })

  it('con 401 sin detalle dice que el correo o la contraseña son incorrectos', async () => {
    vi.spyOn(axiosInstance, 'post').mockRejectedValue(errorHttp(401))

    await expect(iniciarSesion('a@b.cl', 'x')).rejects.toThrow('Correo o contraseña incorrectos.')
  })

  it.each([
    [401, 'Código de verificación incorrecto.'],
    [403, 'Las cuentas de administrador requieren MFA.'],
    [429, 'Demasiados códigos incorrectos: cuenta bloqueada 15 min.'],
  ])('con %i muestra el motivo que da la API', async (status, detalle) => {
    vi.spyOn(axiosInstance, 'post').mockRejectedValue(errorHttp(status, detalle))

    await expect(iniciarSesion('admin@demo.sart', 'x', '000000')).rejects.toThrow(detalle)
  })
})
