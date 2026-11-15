import ApartmentOutlinedIcon from '@mui/icons-material/ApartmentOutlined'
import { useState } from 'react'
import { BloqueCarga } from '../componentes/BloqueCarga.tsx'
import { CabeceraPagina } from '../componentes/CabeceraPagina.tsx'
import { DetalleCentro } from '../componentes/DetalleCentro.tsx'
import { EstadoVacio } from '../componentes/EstadoVacio.tsx'
import { LeyendaNiveles } from '../componentes/LeyendaNiveles.tsx'
import { useEstadoCentros } from '../hooks/useEstadoCentros.ts'
import { useReferencias } from '../hooks/useReferencias.ts'

// Inicio de la jefatura (diseño «Inicio de jefatura»; RF-7). Es su pantalla de inicio: el pronóstico de su centro
// queda a 0 clics después de iniciar sesión (RF-7 pide 4 o menos). La API solo entrega sus centros asignados
// (RNF-S-2); si tiene más de uno, elige cuál ver. La tarjeta de virus del ISP no se incluye (pendientes #22).
export function PantallaMiCentro() {
  const { referencias, cargando: cargandoRef, error: errorRef } = useReferencias()
  const { centros, cargando, error } = useEstadoCentros()
  const [codigo, setCodigo] = useState<number | null>(null)
  const estado = centros?.find((c) => c.centro.codigo_deis === codigo) ?? centros?.[0] ?? null

  return (
    <div className="pagina">
      <CabeceraPagina
        antetitulo="Mi centro"
        titulo={estado ? estado.centro.nombre : 'Mi centro'}
        subtitulo={estado
          ? `${estado.centro.comuna} · pronóstico semanal de consultas respiratorias, dotación sugerida y calidad del aire.`
          : 'Pronóstico semanal de consultas respiratorias, dotación sugerida y calidad del aire.'}
        acciones={centros && centros.length > 1 && (
          <div className="campo campo--compacto">
            <label htmlFor="elegir-centro">Centro</label>
            <div className="campo__caja">
              <select id="elegir-centro" value={estado?.centro.codigo_deis ?? ''}
                onChange={(e) => setCodigo(Number(e.target.value))}>
                {centros.map((c) => <option key={c.centro.codigo_deis} value={c.centro.codigo_deis}>{c.centro.nombre}</option>)}
              </select>
            </div>
          </div>
        )}
      />

      {cargando && <BloqueCarga alto="22rem" radio="16px" />}
      {error && (
        <p className="aviso" role="alert">No se pudo cargar el estado de su centro. Intente recargar la página.</p>
      )}
      {centros && centros.length === 0 && (
        <section className="tarjeta">
          <EstadoVacio icono={<ApartmentOutlinedIcon />} titulo="Su cuenta no tiene centros asignados"
            descripcion="Pida al administrador que le asigne su centro (RF-9)." />
        </section>
      )}
      {!cargando && (
        <DetalleCentro estado={estado} mp25Niveles={referencias?.mp25_niveles ?? null}
          cargandoReferencias={cargandoRef} errorReferencias={errorRef} />
      )}

      <LeyendaNiveles />
    </div>
  )
}
