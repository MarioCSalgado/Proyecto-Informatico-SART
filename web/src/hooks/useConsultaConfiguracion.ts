import { useEffect, useState } from 'react'
import { mensajeErrorConfiguracion } from '../servicios/configuracionAdministracion.ts'

type EstadoConsulta<T> =
  | { tipo: 'cargando' }
  | { tipo: 'error'; mensaje: string }
  | { tipo: 'lista'; datos: T[] }

export function useConsultaConfiguracion<T>(
  listar: (signal: AbortSignal) => Promise<T[]>, mensajeDeCarga: string,
) {
  const [estado, setEstado] = useState<EstadoConsulta<T>>({ tipo: 'cargando' })
  const [intento, setIntento] = useState(0)

  useEffect(() => {
    const solicitud = new AbortController()
    listar(solicitud.signal)
      .then((datos) => {
        if (!solicitud.signal.aborted) setEstado({ tipo: 'lista', datos })
      })
      .catch((error: unknown) => {
        if (!solicitud.signal.aborted) {
          setEstado({ tipo: 'error', mensaje: mensajeErrorConfiguracion(error, mensajeDeCarga) })
        }
      })
    return () => solicitud.abort()
  }, [listar, mensajeDeCarga, intento])

  function recargar() {
    setEstado({ tipo: 'cargando' })
    setIntento((anterior) => anterior + 1)
  }

  function actualizar(reemplazar: (datos: T[]) => T[]) {
    setEstado((anterior) => anterior.tipo === 'lista'
      ? { tipo: 'lista', datos: reemplazar(anterior.datos) }
      : anterior)
  }

  return { estado, recargar, actualizar }
}
