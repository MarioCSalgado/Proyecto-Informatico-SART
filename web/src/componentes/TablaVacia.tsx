import type { ReactNode } from 'react'
import { EstadoVacio } from './EstadoVacio.tsx'

type Props = {
  titulo: string  // nombre accesible de la tabla (caption oculta a la vista)
  columnas: string[]
  icono?: ReactNode
  mensaje: string
  detalle?: ReactNode
}

// Tabla del diseño con sus encabezados fijos y un estado vacío mientras no hay filas. La tabla va en un
// contenedor con desplazamiento horizontal propio (en celular no rompe el ancho de la página); el mensaje de
// vacío va fuera de ese contenedor, para que se lea completo sin tener que desplazarse.
export function TablaVacia({ titulo, columnas, icono, mensaje, detalle }: Props) {
  return (
    <div className="tabla-vacia">
      <div className="tabla-contenedor" tabIndex={0} role="region" aria-label={`${titulo} (desplazable)`}>
        <table className="tabla">
          <caption className="oculto-visual">{`${titulo}: ${mensaje}`}</caption>
          <thead>
            <tr>
              {columnas.map((columna) => <th key={columna} scope="col">{columna}</th>)}
            </tr>
          </thead>
        </table>
      </div>
      <EstadoVacio icono={icono} titulo={mensaje} descripcion={detalle} />
    </div>
  )
}
