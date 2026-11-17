import { BloqueCarga } from './BloqueCarga.tsx'

type Props = {
  estado: { tipo: 'cargando' } | { tipo: 'error'; mensaje: string }
  textoCarga: string
  reintentar: () => void
}

export function EstadoConsultaConfiguracion({ estado, textoCarga, reintentar }: Props) {
  if (estado.tipo === 'cargando') {
    return (
      <div className="tabla-carga" role="status">
        <span className="oculto-visual">{textoCarga}</span>
        <BloqueCarga alto="5rem" radio="12px" />
      </div>
    )
  }
  return (
    <div className="pendiente">
      <span role="alert">{estado.mensaje}</span>
      <button type="button" className="boton-secundario" onClick={reintentar}>Reintentar</button>
    </div>
  )
}
