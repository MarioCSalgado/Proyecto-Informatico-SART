import { z } from 'zod'
import clienteApi from './clienteApi.ts'
import RUTAS_API from './rutasApi.ts'

const nivelEmitido = z.enum(['atencion', 'alerta'])
const estadoNotificacion = z.enum(['enviada', 'fallida', 'confirmada', 'reenviada', 'escalada'])
const notificaciones = z.discriminatedUnion('tipo', [
  z.object({ tipo: z.literal('no_aplica') }),
  z.object({
    tipo: z.literal('propia'),
    estado: estadoNotificacion.nullable(),
    fecha_confirmacion: z.iso.datetime({ offset: true }).nullable(),
  }),
  z.object({
    tipo: z.literal('resumen'),
    estados: z.array(z.object({ estado: estadoNotificacion, total: z.number().int().positive() })),
  }),
])

// Campos que utiliza la pantalla de RF-10, según GET /alertas/historial.
const alertaHistorica = z.object({
  id: z.number(),
  centro: z.object({ codigo_deis: z.number(), nombre: z.string() }),
  fecha_emision: z.iso.datetime({ offset: true }),
  nivel: nivelEmitido,
  pronostico: z.object({
    anio: z.number(),
    semana: z.number(),
    inicio_semana: z.iso.date(),
    valor: z.number(),
    limite_inferior: z.number(),
    limite_superior: z.number(),
  }),
  dotacion: z.object({ profesionales: z.number(), por_validar: z.boolean() }).nullable(),
  observacion: z.object({
    consultas: z.number().nullable(),
    semana_alta: z.boolean().nullable(),
  }),
  notificaciones,
})
const historial = z.array(alertaHistorica)

export type AlertaHistorica = z.infer<typeof alertaHistorica>
export type EstadoNotificacion = z.infer<typeof estadoNotificacion>
export type FiltrosHistorial = {
  codigo_deis?: number
  desde?: string
  hasta?: string
  nivel?: z.infer<typeof nivelEmitido>
}

export async function obtenerHistorialAlertas(
  filtros: FiltrosHistorial, signal: AbortSignal,
): Promise<AlertaHistorica[]> {
  const { data } = await clienteApi.get(RUTAS_API.HISTORIAL_ALERTAS, { params: filtros, signal })
  return historial.parse(data)
}
