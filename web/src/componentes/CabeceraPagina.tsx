import type { ReactNode } from 'react'

type Props = {
  antetitulo: string
  titulo: string
  subtitulo?: string
  acciones?: ReactNode
}

// Cabecera de cada pantalla (diseño de Figma): antetítulo en mayúsculas, título y bajada.
export function CabeceraPagina({ antetitulo, titulo, subtitulo, acciones }: Props) {
  return (
    <div className="cabecera-pagina">
      <div>
        <p className="cabecera-pagina__antetitulo">{antetitulo}</p>
        <h1 className="cabecera-pagina__titulo">{titulo}</h1>
        {subtitulo && <p className="cabecera-pagina__subtitulo">{subtitulo}</p>}
      </div>
      {acciones && <div className="cabecera-pagina__acciones">{acciones}</div>}
    </div>
  )
}
