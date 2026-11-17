import './App.scss'
import { Navigate, Route, Routes } from 'react-router'
import { rutaInicio } from './acceso/rutas.ts'
import { DisenoApp } from './componentes/DisenoApp.tsx'
import { RequiereSesion } from './componentes/RequiereSesion.tsx'
import { RequierePermiso } from './componentes/RequierePermiso.tsx'
import { useSesion } from './contexto/sesion.tsx'
import { PantallaAdministracion } from './pantallas/Administracion.tsx'
import { PantallaCentro } from './pantallas/Centro.tsx'
import { PantallaHistorialAlertas } from './pantallas/HistorialAlertas.tsx'
import { PantallaInicioSesion } from './pantallas/InicioSesion.tsx'
import { PantallaMiCentro } from './pantallas/MiCentro.tsx'
import { PantallaRedCentros } from './pantallas/RedCentros.tsx'

// La raíz lleva a la pantalla de inicio del rol (jefatura → Mi centro, subdirector → Red, admin → Administración).
function InicioSegunRol() {
  const { usuario } = useSesion()
  return usuario ? <Navigate to={rutaInicio(usuario.rol)} replace /> : <Navigate to="/login" replace />
}

// Navegación con URL (react-router): el correo de RF-5/RF-15 necesita enlazar a una página concreta.
// Ruta por agregar: /acuse/:id (actividad 10).
function App() {
  return (
    <Routes>
      <Route path="/login" element={<PantallaInicioSesion />} />
      <Route element={<RequiereSesion><DisenoApp /></RequiereSesion>}>
        <Route index element={<InicioSegunRol />} />
        <Route
          path="mi-centro"
          element={<RequierePermiso permiso="ver_mi_centro"><PantallaMiCentro /></RequierePermiso>}
        />
        <Route
          path="red"
          element={<RequierePermiso permiso="ver_todos_los_centros"><PantallaRedCentros /></RequierePermiso>}
        />
        <Route
          path="red/:codigo"
          element={<RequierePermiso permiso="ver_todos_los_centros"><PantallaCentro /></RequierePermiso>}
        />
        <Route
          path="historial-alertas"
          element={<RequierePermiso permiso="ver_historial_alertas"><PantallaHistorialAlertas /></RequierePermiso>}
        />
        <Route
          path="administracion"
          element={<RequierePermiso permiso="administrar_cuentas"><PantallaAdministracion /></RequierePermiso>}
        />
      </Route>
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  )
}

export default App
