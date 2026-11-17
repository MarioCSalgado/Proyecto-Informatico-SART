import { isAxiosError } from 'axios'
import { z } from 'zod'
import clienteApi from './clienteApi.ts'

const RUTA = 'administracion'
const centro = z.object({ codigo_deis: z.number(), nombre: z.string() })
const umbralPorCentro = z.object({
  centro,
  umbral: z.object({
    umbral_atencion: z.number(),
    umbral_alerta: z.number(),
    origen: z.enum(['calculado', 'manual']),
    anios_usados: z.string().nullable(),
  }).nullable(),
})
const parametro = z.object({ clave: z.string(), valor: z.json() })
const cambioConfiguracion = z.object({
  fecha: z.iso.datetime({ offset: true }),
  autor_id: z.number().nullable(),
  autor_rol: z.string().nullable(),
  accion: z.enum(['cambio_umbral', 'recalculo_umbral', 'cambio_parametro']),
  entidad_id: z.string().nullable(),
  valor_anterior: z.json(),
  valor_nuevo: z.json(),
  motivo: z.string().nullable(),
  centro: centro.nullable(),
})

export type UmbralPorCentro = z.infer<typeof umbralPorCentro>
export type ParametroVigente = z.infer<typeof parametro>
export type CambioConfiguracion = z.infer<typeof cambioConfiguracion>

export async function listarUmbrales(signal: AbortSignal): Promise<UmbralPorCentro[]> {
  const { data } = await clienteApi.get(`${RUTA}/umbrales`, { signal })
  return z.array(umbralPorCentro).parse(data)
}

export async function guardarUmbral(
  codigoDeis: number, cambio: { umbral_atencion: number; umbral_alerta: number; motivo: string },
): Promise<UmbralPorCentro> {
  const { data } = await clienteApi.put(`${RUTA}/umbrales/${codigoDeis}`, cambio)
  return umbralPorCentro.parse(data)
}

export async function listarParametros(signal: AbortSignal): Promise<ParametroVigente[]> {
  const { data } = await clienteApi.get(`${RUTA}/parametros`, { signal })
  return z.array(parametro).parse(data)
}

export async function guardarParametro(
  clave: string, cambio: { valor: number; motivo: string },
): Promise<ParametroVigente> {
  const { data } = await clienteApi.put(`${RUTA}/parametros/${encodeURIComponent(clave)}`, cambio)
  return parametro.parse(data)
}

export async function listarHistorialConfiguracion(signal: AbortSignal): Promise<CambioConfiguracion[]> {
  const { data } = await clienteApi.get(`${RUTA}/historial`, { signal })
  return z.array(cambioConfiguracion).parse(data)
}

export function mensajeErrorConfiguracion(error: unknown, predeterminado: string): string {
  if (!isAxiosError(error)) return predeterminado
  const estado = error.response?.status
  if (estado === 401) return 'Inicie sesión para acceder a la configuración.'
  if (estado === 403) return 'Solo un administrador puede acceder a la configuración.'
  const detalle = error.response?.data?.detail
  return (estado === 404 || estado === 422) && typeof detalle === 'string' ? detalle : predeterminado
}
