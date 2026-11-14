// Pie del diseño de Figma. «SART informa, no decide»: el aviso del criterio clínico va en todas las pantallas.
// La marca de entorno de demostración solo aparece en desarrollo, para no presentar como oficiales datos de prueba.
export function AvisoEntorno() {
  if (!import.meta.env.DEV) return null
  return <span>Entorno de demostración · Datos no oficiales</span>
}

export function PiePagina() {
  return (
    <footer className="pie">
      <p className="pie__aviso">Herramienta de apoyo a la decisión; no reemplaza el criterio clínico</p>
      <p className="pie__datos">
        SART · Gran Concepción{import.meta.env.DEV && ' · '}<AvisoEntorno />
      </p>
    </footer>
  )
}
