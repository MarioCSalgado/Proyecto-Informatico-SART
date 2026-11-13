import './App.scss'
import { Navigate, Route, Routes } from 'react-router'
import { LoginScreen } from './screens/LoginScreen.tsx'
import { EstadoCentroScreen } from './screens/EstadoCentroScreen.tsx'
import { TopBar } from './components/TopBar.tsx'
import { RequireAuth } from './components/RequireAuth.tsx'
import { RequirePermission } from './components/RequirePermission.tsx'

// Navegación con URL (react-router): el correo de RF-5/RF-15 necesita enlazar a una página concreta.
// Rutas por agregar: /acuse/:id (actividad 10), /administracion (actividad 8).
function App() {
  return (
    <div className="main">
      <Routes>
        <Route
          path="/login"
          element={<div className="login-wrapper"><LoginScreen /></div>}
        />
        <Route
          path="/centros"
          element={
            <RequireAuth>
              <TopBar />
              <RequirePermission permission="ver_estado_centros">
                <EstadoCentroScreen />
              </RequirePermission>
            </RequireAuth>
          }
        />
        <Route path="*" element={<Navigate to="/centros" replace />} />
      </Routes>
    </div>
  )
}

export default App
