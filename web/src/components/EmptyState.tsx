import InboxOutlinedIcon from '@mui/icons-material/InboxOutlined'
import type { ReactNode } from 'react'

type Props = {
  icon?: ReactNode
  title: string
  description?: ReactNode
  action?: ReactNode
}

export function EmptyState({ icon, title, description, action }: Props) {
  return (
    <div className="estado-vacio">
      <div className="estado-vacio__icono" aria-hidden="true">{icon ?? <InboxOutlinedIcon />}</div>
      <p className="estado-vacio__titulo">{title}</p>
      {description && <p className="estado-vacio__descripcion">{description}</p>}
      {action && <div className="estado-vacio__accion">{action}</div>}
    </div>
  )
}
