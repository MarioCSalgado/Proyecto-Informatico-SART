import ApartmentOutlinedIcon from '@mui/icons-material/ApartmentOutlined'
import { CabeceraPagina } from '../components/CabeceraPagina.tsx'
import { EmptyState } from '../components/EmptyState.tsx'
import { LeyendaNiveles } from '../components/LeyendaNiveles.tsx'

// Vista de red del subdirector (diseño «Vista de red»; RF-7 con todos los centros). Etapa 1: estructura sin
// datos. En la etapa 2: resumen por nivel, alertas sin confirmar (RF-15), filtros y calendario de calor.
export function RedCentrosScreen() {
  return (
    <div className="pagina">
      <CabeceraPagina
        antetitulo="Vista de red"
        titulo="Red de centros"
        subtitulo="Gran Concepción · 33 centros de urgencia"
      />
      <section className="tarjeta">
        <EmptyState
          icon={<ApartmentOutlinedIcon />}
          title="Todavía no hay pronósticos de la red"
          description="Aquí aparecerá el nivel de cada centro, las alertas sin confirmar y el calendario de las últimas semanas."
        />
      </section>
      <LeyendaNiveles conAbreviaturas />
    </div>
  )
}
