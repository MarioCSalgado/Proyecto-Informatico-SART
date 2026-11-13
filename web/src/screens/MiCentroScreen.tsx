import ShowChartOutlinedIcon from '@mui/icons-material/ShowChartOutlined'
import { CabeceraPagina } from '../components/CabeceraPagina.tsx'
import { EmptyState } from '../components/EmptyState.tsx'
import { LeyendaNiveles } from '../components/LeyendaNiveles.tsx'

// Inicio de la jefatura (diseño «Inicio de jefatura»; RF-7). Etapa 1: estructura sin datos. En la etapa 2
// muestra pronóstico con intervalo, nivel, gráfico de 12 semanas, dotación (RF-6), MP2,5 (RF-4) y el botón
// de acuse de RF-15, cuando la API los entregue.
export function MiCentroScreen() {
  return (
    <div className="pagina">
      <CabeceraPagina
        antetitulo="Mi centro"
        titulo="Mi centro"
        subtitulo="Pronóstico semanal de consultas respiratorias, dotación sugerida y calidad del aire."
      />
      <section className="tarjeta">
        <EmptyState
          icon={<ShowChartOutlinedIcon />}
          title="Todavía no hay pronóstico para tu centro"
          description="Aparecerá aquí cuando estén listos el pronóstico semanal y la asignación de tu centro."
        />
      </section>
      <LeyendaNiveles />
    </div>
  )
}
