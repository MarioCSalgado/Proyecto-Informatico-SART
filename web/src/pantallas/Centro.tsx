import ArrowBackOutlinedIcon from '@mui/icons-material/ArrowBackOutlined'
import { Link, useParams } from 'react-router'
import { BloqueCarga } from '../componentes/BloqueCarga.tsx'
import { CabeceraPagina } from '../componentes/CabeceraPagina.tsx'
import { DetalleCentro } from '../componentes/DetalleCentro.tsx'
import { LeyendaNiveles } from '../componentes/LeyendaNiveles.tsx'
import { useEstadoCentro } from '../hooks/useEstadoCentros.ts'
import { useReferencias } from '../hooks/useReferencias.ts'

const MENSAJES = {
  sin_acceso: 'Su cuenta no tiene acceso a este centro.',
  no_existe: 'No existe un centro con ese código.',
  red: 'No se pudo cargar el estado del centro. Intente recargar la página.',
}

// Detalle de un centro desde la vista de red (RF-7 paso 3; subdirector y administrador): el mismo bloque que
// «Mi centro», con la fecha de corte y las advertencias de calidad de los datos.
export function PantallaCentro() {
  const { codigo } = useParams()
  const { centro, cargando, error } = useEstadoCentro(Number(codigo))
  const { referencias, cargando: cargandoRef, error: errorRef } = useReferencias()

  return (
    <div className="pagina">
      <Link to="/red" className="boton-enlace enlace-volver">
        <ArrowBackOutlinedIcon aria-hidden="true" /> Volver a la red de centros
      </Link>
      <CabeceraPagina
        antetitulo={centro ? `${centro.centro.tipo} · código ${centro.centro.codigo_deis}` : 'Centro'}
        titulo={centro?.centro.nombre ?? 'Centro'}
        subtitulo={centro?.centro.comuna}
      />
      {cargando && <BloqueCarga alto="22rem" radio="16px" />}
      {error && <p className="aviso" role="alert">{MENSAJES[error]}</p>}
      {centro && (
        <DetalleCentro estado={centro} mp25Niveles={referencias?.mp25_niveles ?? null}
          cargandoReferencias={cargandoRef} errorReferencias={errorRef} />
      )}
      <LeyendaNiveles />
    </div>
  )
}
