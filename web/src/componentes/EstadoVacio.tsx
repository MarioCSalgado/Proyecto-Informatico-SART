import InboxOutlinedIcon from '@mui/icons-material/InboxOutlined'
import type { ReactNode } from 'react'

type Props = {
  icono?: ReactNode
  titulo: string
  descripcion?: ReactNode
  accion?: ReactNode
}

/** Mensaje cuando una sección todavía no tiene datos: qué va a aparecer y, si aplica, qué hacer. */
export function EstadoVacio({ icono, titulo, descripcion, accion }: Props) {
  return (
    <div className="estado-vacio">
      <div className="estado-vacio__icono" aria-hidden="true">{icono ?? <InboxOutlinedIcon />}</div>
      <p className="estado-vacio__titulo">{titulo}</p>
      {descripcion && <p className="estado-vacio__descripcion">{descripcion}</p>}
      {accion && <div className="estado-vacio__accion">{accion}</div>}
    </div>
  )
}
