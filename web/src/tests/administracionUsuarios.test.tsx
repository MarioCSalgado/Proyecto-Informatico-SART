import { cleanup, render, screen, within } from '@testing-library/react'
import { userEvent } from '@testing-library/user-event'
import { MemoryRouter } from 'react-router'
import { afterEach, describe, expect, it, vi } from 'vitest'
import App from '../App.tsx'
import { ProveedorSesion } from '../contexto/sesion.tsx'
import clienteApi from '../servicios/clienteApi.ts'

// RF-9 y RF-16 en la pantalla (TC-16): pestaña «Usuarios» de Administración conectada a la API.
const CUENTAS = [
  { id: 1, nombre: 'Admin Demo', correo: 'admin@demo.sart', rol: 'administrador', mfa_activo: true, centros: [] },
  {
    id: 2, nombre: 'Ana Pérez', correo: 'ana@demo.sart', rol: 'jefatura', mfa_activo: false,
    centros: [{ codigo_deis: 100001, nombre: 'SAR Uno' }],
  },
]
const REFERENCIAS = { mp25_niveles: [], comunas: [], finalidad_version: '2026-1', finalidad_texto: 'Texto de §5.3' }
const CENTROS = [100001, 100002].map((codigo, i) => ({
  centro: { codigo_deis: codigo, nombre: `SAR ${['Uno', 'Dos'][i]}` }, mp25: {}, ultimas_semanas: [],
}))

function abrir() {
  vi.spyOn(clienteApi, 'get').mockImplementation(async (url: string) => {
    if (url === 'administracion/usuarios') return { data: CUENTAS }
    if (url === 'referencias') return { data: REFERENCIAS }
    if (url === 'centros/estado') return { data: CENTROS }
    return { data: { usuario: { id: 1, nombre: 'Admin Demo', rol: 'Administrador' } } }
  })
  return render(
    <MemoryRouter initialEntries={['/administracion']}>
      <ProveedorSesion><App /></ProveedorSesion>
    </MemoryRouter>,
  )
}

describe('Administración · Usuarios (RF-9, RF-16)', () => {
  afterEach(() => {
    cleanup()
    vi.restoreAllMocks()
  })

  it('lista las cuentas con su rol y sus centros; el administrador no puede darse de baja', async () => {
    abrir()
    const tabla = await screen.findByRole('table', { name: /Usuarios y permisos/ })

    const filas = within(tabla).getAllByRole('row').slice(1)
    expect(filas[0]).toHaveTextContent('Toda la red')
    expect(filas[1]).toHaveTextContent('SAR Uno')
    expect(screen.queryByRole('button', { name: 'Dar de baja a Admin Demo' })).not.toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Dar de baja a Ana Pérez' })).toBeInTheDocument()
  })

  it('TC-16: sin marcar la aceptación de la finalidad no se puede crear la cuenta', async () => {
    const usuario = userEvent.setup()
    const post = vi.spyOn(clienteApi, 'post').mockResolvedValue({ data: CUENTAS[1] })
    abrir()
    await usuario.click(await screen.findByRole('button', { name: /Crear usuario/ }))
    const dialogo = await screen.findByRole('dialog', { name: 'Crear usuario' })
    await within(dialogo).findByText('Texto de §5.3')

    await usuario.type(within(dialogo).getByLabelText('Nombre'), 'Luis Soto')
    await usuario.type(within(dialogo).getByLabelText('Correo institucional'), 'luis@demo.sart')
    await usuario.type(within(dialogo).getByLabelText('Contraseña inicial'), 'una clave larga y segura')
    await usuario.click(within(dialogo).getByLabelText(/SAR Dos/))
    const crear = within(dialogo).getByRole('button', { name: 'Crear cuenta' })
    expect(crear).toBeDisabled()

    await usuario.click(within(dialogo).getByLabelText('El funcionario leyó y aceptó este texto'))
    await usuario.click(crear)

    expect(post).toHaveBeenCalledWith('administracion/usuarios', {
      nombre: 'Luis Soto', correo: 'luis@demo.sart', rol: 'jefatura', contrasena: 'una clave larga y segura',
      acepta_finalidad: true, version_texto: '2026-1', centros: [100002],
    })
  })

  it('cambia los centros de una jefatura y la da de baja tras confirmar', async () => {
    const usuario = userEvent.setup()
    const put = vi.spyOn(clienteApi, 'put').mockResolvedValue({ data: CUENTAS[1] })
    const borrar = vi.spyOn(clienteApi, 'delete').mockResolvedValue({ data: null })
    vi.spyOn(window, 'confirm').mockReturnValue(true)
    abrir()

    await usuario.click(await screen.findByRole('button', { name: 'Centros de Ana Pérez' }))
    const dialogo = await screen.findByRole('dialog', { name: 'Centros de Ana Pérez' })
    await usuario.click(within(dialogo).getByLabelText(/SAR Dos/))
    await usuario.click(within(dialogo).getByRole('button', { name: 'Guardar centros' }))
    expect(put).toHaveBeenCalledWith('administracion/usuarios/2/centros', { centros: [100001, 100002] })

    await usuario.click(screen.getByRole('button', { name: 'Dar de baja a Ana Pérez' }))
    expect(borrar).toHaveBeenCalledWith('administracion/usuarios/2')
  })
})
