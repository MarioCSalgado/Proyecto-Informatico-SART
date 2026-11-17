import DownloadOutlinedIcon from '@mui/icons-material/DownloadOutlined'
import { useState } from 'react'
import { usePermisos } from '../hooks/usePermisos.ts'
import { descargarCsvCentros } from '../servicios/exportacion.ts'

// Botón de RF-11 (TC-15): descarga el CSV de un centro (Mi centro) o de todos los que el usuario ve (Red de
// centros). La API decide qué centros entran; aquí solo se muestra si el rol puede exportar (RNF-S-2).
export function BotonExportarCsv({ codigo, etiqueta, desactivado = false }: {
  codigo?: number
  etiqueta: string
  desactivado?: boolean
}) {
  const { puede } = usePermisos()
  const [estado, setEstado] = useState<'listo' | 'descargando' | 'error'>('listo')

  if (!puede('exportar_csv')) return null

  const descargar = async () => {
    setEstado('descargando')
    try {
      await descargarCsvCentros(codigo)
      setEstado('listo')
    } catch {
      setEstado('error')
    }
  }

  return (
    <>
      <button type="button" className="boton-secundario" onClick={descargar} disabled={desactivado || estado === 'descargando'}
        title="CSV UTF-8 con separador «;» para Excel o Power BI (RF-11)">
        <DownloadOutlinedIcon aria-hidden="true" /> {estado === 'descargando' ? 'Descargando…' : etiqueta}
      </button>
      {estado === 'error' && (
        <span className="nota" role="alert">No se pudo descargar el CSV. Intente de nuevo.</span>
      )}
    </>
  )
}
