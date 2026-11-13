import './App.scss'
import { Navigate, Route, Routes } from 'react-router'
import { rutaInicio } from './auth/rutas.ts'
import { DisenoApp } from './components/DisenoApp.tsx'
import { RequireAuth } from './components/RequireAuth.tsx'
import { RequirePermission } from './components/RequirePermission.tsx'
import { useAuth } from './context/authContext.tsx'
import { AdministracionScreen } from './screens/AdministracionScreen.tsx'
import { LoginScreen } from './screens/LoginScreen.tsx'
import { MiCentroScreen } from './screens/MiCentroScreen.tsx'
import { RedCentrosScreen } from './screens/RedCentrosScreen.tsx'

// La raíz lleva a la pantalla de inicio del rol (jefatura → Mi centro, subdirector → Red, admin → Administración).
function InicioSegunRol() {
  const { user } = useAuth()
  return user ? <Navigate to={rutaInicio(user.rol)} replace /> : <Navigate to="/login" replace />
}

// Navegación con URL (react-router): el correo de RF-5/RF-15 necesita enlazar a una página concreta.
// Ruta por agregar: /acuse/:id (actividad 10).
function App() {
  return (
    <Routes>
      <Route path="/login" element={<LoginScreen />} />
      <Route element={<RequireAuth><DisenoApp /></RequireAuth>}>
        <Route index element={<InicioSegunRol />} />
        <Route
          path="mi-centro"
          element={<RequirePermission permission="ver_mi_centro"><MiCentroScreen /></RequirePermission>}
        />
        <Route
          path="red"
          element={<RequirePermission permission="ver_todos_los_centros"><RedCentrosScreen /></RequirePermission>}
        />
        <Route
          path="administracion"
          element={<RequirePermission permission="administrar_cuentas"><AdministracionScreen /></RequirePermission>}
        />
      </Route>
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  )
}

export default App
