import { useId } from 'react'
import { EstadoConsultaConfiguracion } from '../componentes/EstadoConsultaConfiguracion.tsx'
import { EstadoVacio } from '../componentes/EstadoVacio.tsx'
import { useConsultaConfiguracion } from '../hooks/useConsultaConfiguracion.ts'
import { listarHistorialConfiguracion, type CambioConfiguracion } from '../servicios/configuracionAdministracion.ts'
import { etiquetaParametro } from '../utilidades/configuracion.ts'

const FECHA = new Intl.DateTimeFormat('es-CL', { dateStyle: 'short', timeStyle: 'short', timeZone: 'America/Santiago' })
const TITULO_TABLA = 'Historial de cambios de configuración'
const ACCIONES = {
  cambio_umbral: 'Umbral manual',
  recalculo_umbral: 'Recálculo de umbral',
  cambio_parametro: 'Ajuste de parámetro',
} as const

function numero(valor: number): string {
  return String(valor).replace('.', ',')
}

function valorMostrado(valor: CambioConfiguracion['valor_anterior']): string {
  if (valor === null) return 'Sin valor'
  if (typeof valor === 'number') return numero(valor)
  if (typeof valor === 'string') return valor
  if (typeof valor === 'object' && !Array.isArray(valor)) {
    const { umbral_atencion, umbral_alerta, origen } = valor
    if (typeof umbral_atencion === 'number' && typeof umbral_alerta === 'number') {
      const umbrales = `Atención ${numero(umbral_atencion)} · Alerta ${numero(umbral_alerta)}`
      return typeof origen === 'string' ? `${umbrales} (${origen})` : umbrales
    }
  }
  return JSON.stringify(valor)
}

function autor({ autor_id, autor_rol }: CambioConfiguracion): string {
  if (autor_rol === 'sistema') return 'Sistema'
  const rol = autor_rol ? autor_rol.charAt(0).toUpperCase() + autor_rol.slice(1) : 'Autor sin registrar'
  return autor_id === null ? rol : `${rol} (#${autor_id})`
}

function referencia(cambio: CambioConfiguracion): string {
  if (cambio.accion === 'cambio_parametro' && cambio.entidad_id) return etiquetaParametro(cambio.entidad_id)
  if (cambio.centro) return cambio.centro.nombre
  return cambio.entidad_id ? `Centro #${cambio.entidad_id}` : 'Referencia sin registrar'
}

export function HistorialConfiguracion() {
  const id = useId()
  const { estado, recargar } = useConsultaConfiguracion(listarHistorialConfiguracion, 'No se pudo cargar el historial.')

  return (
    <section className="tarjeta" aria-labelledby={`${id}-titulo`}>
      <div className="tarjeta__encabezado">
        <div>
          <h2 id={`${id}-titulo`} className="tarjeta__titulo">Historial de cambios</h2>
          <p className="tarjeta__bajada">Cambios de configuración del más reciente al más antiguo.</p>
        </div>
        {estado.tipo === 'lista' && (
          <button type="button" className="boton-secundario" onClick={recargar}>Actualizar historial</button>
        )}
      </div>

      {estado.tipo !== 'lista' ? (
        <EstadoConsultaConfiguracion estado={estado} textoCarga="Cargando historial de configuración" reintentar={recargar} />
      ) : estado.datos.length === 0 ? (
        <EstadoVacio titulo="Todavía no hay cambios registrados" />
      ) : (
        <div className="tabla-contenedor" tabIndex={0} role="region" aria-label="Historial de cambios (desplazable)">
          <table className="tabla">
            <caption className="oculto-visual">{TITULO_TABLA}</caption>
            <thead>
              <tr>
                <th scope="col">Fecha</th>
                <th scope="col">Autor</th>
                <th scope="col">Centro o parámetro</th>
                <th scope="col">Valor anterior</th>
                <th scope="col">Valor nuevo</th>
                <th scope="col">Motivo</th>
              </tr>
            </thead>
            <tbody>
              {estado.datos.map((cambio, indice) => (
                <tr key={`${cambio.fecha}-${indice}`}>
                  <td><time dateTime={cambio.fecha}>{FECHA.format(new Date(cambio.fecha))}</time></td>
                  <td>{autor(cambio)}</td>
                  <th scope="row" className="tabla__centro">
                    {referencia(cambio)}<span className="tabla__codigo">{ACCIONES[cambio.accion]}</span>
                  </th>
                  <td>{valorMostrado(cambio.valor_anterior)}</td>
                  <td>{valorMostrado(cambio.valor_nuevo)}</td>
                  <td>{cambio.motivo ?? 'Sin motivo registrado'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  )
}
