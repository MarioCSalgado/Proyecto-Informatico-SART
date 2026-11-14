import ScheduleOutlinedIcon from '@mui/icons-material/ScheduleOutlined'
import type { ReactNode } from 'react'

// Explica por qué una sección todavía no tiene datos o sus botones están desactivados.
export function AvisoPendiente({ children }: { children: ReactNode }) {
  return (
    <p className="pendiente">
      <ScheduleOutlinedIcon aria-hidden="true" />
      <span>{children}</span>
    </p>
  )
}
