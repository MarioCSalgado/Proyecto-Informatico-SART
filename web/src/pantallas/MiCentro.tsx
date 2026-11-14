import DownloadOutlinedIcon from '@mui/icons-material/DownloadOutlined'
import ShowChartOutlinedIcon from '@mui/icons-material/ShowChartOutlined'
import TableChartOutlinedIcon from '@mui/icons-material/TableChartOutlined'
import { AvisoPendiente } from '../componentes/AvisoPendiente.tsx'
import { CabeceraPagina } from '../componentes/CabeceraPagina.tsx'
import { EstadoVacio } from '../componentes/EstadoVacio.tsx'
import { EscalaMp25 } from '../componentes/EscalaMp25.tsx'
import { LeyendaGrafico } from '../componentes/LeyendaGrafico.tsx'
import { LeyendaNiveles } from '../componentes/LeyendaNiveles.tsx'
import { useReferencias } from '../hooks/useReferencias.ts'

// Inicio de la jefatura (diseño «Inicio de jefatura»; RF-7). Partes fijas del diseño: estructura, títulos,
// leyenda del gráfico, escala de MP2,5 y botones. Lo que depende de datos (aviso de alerta, pronóstico, gráfico,
// dotación de RF-6, valores de MP2,5 de RF-4 y el acuse de RF-15) llega cuando la API los entregue.
// La tarjeta de virus del ISP no se incluye: no está en la especificación (pendientes #22).
export function PantallaMiCentro() {
  const { referencias, cargando, error } = useReferencias()

  return (
    <div className="pagina">
      <CabeceraPagina
        antetitulo="Mi centro"
        titulo="Mi centro"
        subtitulo="Pronóstico semanal de consultas respiratorias, dotación sugerida y calidad del aire."
      />

      <section className="tarjeta" aria-labelledby="titulo-pronostico">
        <div className="grilla-pronostico">
          <div>
            <p className="antetitulo">Próxima semana</p>
            <h2 id="titulo-pronostico" className="tarjeta__titulo">Pronóstico de consultas</h2>
            <p className="pronostico__vacio">Sin pronóstico todavía</p>
            <p className="tarjeta__bajada">
              Aquí aparecerán las consultas esperadas, su rango con 90 % de confianza y el nivel del centro.
            </p>
          </div>
          <div>
            <h3 className="subtitulo-tarjeta">Consultas respiratorias semanales</h3>
            <p className="tarjeta__bajada">Últimas 12 semanas y pronóstico de la próxima</p>
            <div className="grafico-vacio">
              <EstadoVacio icono={<ShowChartOutlinedIcon />} titulo="Gráfico sin datos todavía" />
            </div>
            <LeyendaGrafico />
            <p className="nota">La banda representa incertidumbre, no un máximo esperado.</p>
          </div>
        </div>
        <div className="tarjeta__pie">
          <AvisoPendiente>Disponible cuando la API entregue el pronóstico del centro (RF-2, RF-7).</AvisoPendiente>
          <div className="acciones">
            <button type="button" className="boton-secundario" disabled>
              <TableChartOutlinedIcon aria-hidden="true" /> Ver como tabla
            </button>
            <button type="button" className="boton-secundario" disabled>
              <DownloadOutlinedIcon aria-hidden="true" /> Descargar CSV
            </button>
          </div>
        </div>
      </section>

      <div className="grilla-dos">
        <section className="tarjeta" aria-labelledby="titulo-dotacion">
          <h2 id="titulo-dotacion" className="tarjeta__titulo">Dotación sugerida</h2>
          <p className="tarjeta__bajada">Escenario orientativo para el centro en hora punta</p>
          <p className="pronostico__vacio">Sin estimación todavía</p>
          <p className="nota">
            Estimación según demanda prevista y capacidad del centro. Validar turnos y disponibilidad local antes
            de actuar.
          </p>
        </section>
        <EscalaMp25 niveles={referencias?.mp25_niveles ?? null} cargando={cargando} error={error} />
      </div>

      <LeyendaNiveles />
    </div>
  )
}
