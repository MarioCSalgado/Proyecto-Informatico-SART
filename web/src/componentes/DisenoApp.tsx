import { Outlet } from 'react-router'
import { Encabezado } from './Encabezado.tsx'
import { PiePagina } from './PiePagina.tsx'

// Marco común de las pantallas con sesión: encabezado, contenido y pie.
export function DisenoApp() {
  return (
    <div className="app">
      <Encabezado />
      <main className="app__contenido">
        <Outlet />
      </main>
      <PiePagina />
    </div>
  )
}
