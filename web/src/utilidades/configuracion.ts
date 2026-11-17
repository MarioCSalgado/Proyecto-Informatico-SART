const ETIQUETAS: Record<string, string> = {
  'regla_alerta.k_margen': 'Margen de alerta (k)',
  'umbrales.cuantil_atencion': 'Cuantil de Atención',
  'umbrales.cuantil_alerta': 'Cuantil de Alerta',
  'umbrales.anios_umbral': 'Ventana de umbrales (años)',
  'dotacion.minutos_por_atencion': 'Minutos por atención',
  'dotacion.factor_hora_punta': 'Factor de hora punta',
  'dotacion.espera_objetivo_min': 'Espera objetivo (minutos)',
  'dotacion.horas_funcionamiento_semana.SAPU': 'Horas semanales de un SAPU',
  'dotacion.horas_funcionamiento_semana.SAR': 'Horas semanales de un SAR',
  'dotacion.horas_funcionamiento_semana.SUR': 'Horas semanales de un SUR',
  'dotacion.horas_funcionamiento_semana.hospital': 'Horas semanales de un hospital',
  'notificaciones.reenvio_horas': 'Plazo de reenvío (horas)',
  'notificaciones.escalamiento_horas': 'Plazo de escalamiento (horas)',
}

export function etiquetaParametro(clave: string): string {
  return Object.hasOwn(ETIQUETAS, clave) ? ETIQUETAS[clave]! : clave
}

export function leerNumeroNoNegativo(texto: string): number | null {
  if (!texto.trim()) return null
  const numero = Number(texto)
  return Number.isFinite(numero) && numero >= 0 ? numero : null
}
