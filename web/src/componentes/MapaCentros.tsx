import { useEffect, useMemo } from 'react'
import { CircleMarker, MapContainer, Popup, TileLayer, Tooltip, useMap } from 'react-leaflet'
import type { EstadoCentro, NivelAlerta } from '../tipos/index.ts'
import 'leaflet/dist/leaflet.css'

type Posicion = [number, number]

const NIVELES: Record<NivelAlerta, { etiqueta: string; color: string }> = {
  normal: { etiqueta: 'Normal', color: '#1d6b45' },
  atencion: { etiqueta: 'Atención', color: '#7c5a00' },
  alerta: { etiqueta: 'Alerta', color: '#ad430c' },
}

const SIN_NIVEL = { etiqueta: 'Sin nivel', color: '#687584' }

function ajustarVista(posiciones: Posicion[]) {
  const latitudes = posiciones.map(([latitud]) => latitud)
  const longitudes = posiciones.map(([, longitud]) => longitud)
  const suroeste: Posicion = [Math.min(...latitudes), Math.min(...longitudes)]
  const noreste: Posicion = [Math.max(...latitudes), Math.max(...longitudes)]
  return [suroeste, noreste] as const
}

function AjustarVista({ posiciones }: { posiciones: Posicion[] }) {
  const mapa = useMap()

  useEffect(() => {
    const [suroeste, noreste] = ajustarVista(posiciones)
    if (
      posiciones.length === 1 ||
      (suroeste[0] === noreste[0] && suroeste[1] === noreste[1])
    ) {
      mapa.setView(posiciones[0]!, 13)
    } else {
      mapa.fitBounds([suroeste, noreste], { padding: [28, 28], maxZoom: 12 })
    }
  }, [mapa, posiciones])

  return null
}

function esPosicionValida(estado: EstadoCentro): estado is EstadoCentro & {
  centro: EstadoCentro['centro'] & { latitud: number; longitud: number }
} {
  const { latitud, longitud } = estado.centro
  return latitud !== null && longitud !== null &&
    Number.isFinite(latitud) && Number.isFinite(longitud) &&
    Math.abs(latitud) <= 90 && Math.abs(longitud) <= 180
}

export function MapaCentros({ centros }: { centros: EstadoCentro[] }) {
  const centrosConPosicion = useMemo(() => centros.filter(esPosicionValida), [centros])
  const posiciones = useMemo(
    () => centrosConPosicion.map(({ centro }) => [centro.latitud, centro.longitud] as Posicion),
    [centrosConPosicion],
  )

  if (centros.length === 0) {
    return <p className="mapa-centros__vacio">No hay centros para mostrar en el mapa con esos filtros.</p>
  }

  if (centrosConPosicion.length === 0) {
    return <p className="mapa-centros__vacio" role="status">No hay centros con coordenadas válidas para mostrar.</p>
  }

  const centroInicial: Posicion = [
    posiciones.reduce((suma, [latitud]) => suma + latitud, 0) / posiciones.length,
    posiciones.reduce((suma, [, longitud]) => suma + longitud, 0) / posiciones.length,
  ]

  return (
    <div className="mapa-centros">
      <div className="mapa-centros__marco">
        <MapContainer
          center={centroInicial}
          zoom={11}
          scrollWheelZoom={false}
          className="mapa-centros__lienzo"
        >
          <TileLayer
            attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'
            url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
          />
          <AjustarVista posiciones={posiciones} />
          {centrosConPosicion.map((estado) => {
            const nivel = estado.pronostico?.nivel
            const estilo = nivel ? NIVELES[nivel] : SIN_NIVEL
            const posicion: Posicion = [estado.centro.latitud, estado.centro.longitud]

            return (
              <CircleMarker
                key={estado.centro.codigo_deis}
                center={posicion}
                radius={8}
                pathOptions={{ color: '#fff', weight: 2, fillColor: estilo.color, fillOpacity: 1 }}
              >
                <Tooltip
                  permanent
                  direction="top"
                  offset={[0, -8]}
                  className={`mapa-centros__rotulo mapa-centros__rotulo--${nivel ?? 'sin-nivel'}`}
                >
                  {estilo.etiqueta}
                </Tooltip>
                <Popup>
                  <strong>{estado.centro.nombre}</strong>
                  <p>{estado.centro.comuna} · {estado.centro.tipo}</p>
                  <p>Nivel: {estilo.etiqueta}</p>
                  <p>Estación asignada: {estado.centro.estacion_asignada}</p>
                </Popup>
              </CircleMarker>
            )
          })}
        </MapContainer>
      </div>
      {centrosConPosicion.length < centros.length && (
        <p className="mapa-centros__aviso" role="status">
          No se muestran {centros.length - centrosConPosicion.length} centros porque no tienen coordenadas válidas.
        </p>
      )}
      <ul className="mapa-centros__leyenda" aria-label="Leyenda del mapa">
        {(Object.entries(NIVELES) as [NivelAlerta, (typeof NIVELES)[NivelAlerta]][]).map(([nivel, estilo]) => (
          <li key={nivel}>
            <span className={`mapa-centros__muestra mapa-centros__muestra--${nivel}`} aria-hidden="true" />
            {estilo.etiqueta}
          </li>
        ))}
        <li><span className="mapa-centros__muestra mapa-centros__muestra--sin-nivel" aria-hidden="true" />Sin nivel</li>
      </ul>
      <p className="nota">Selecciona un punto para ver el centro y su estación asignada. Mapa base: OpenStreetMap.</p>
    </div>
  )
}
