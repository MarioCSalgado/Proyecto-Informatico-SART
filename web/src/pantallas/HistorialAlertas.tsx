import { useEffect, useState, type FormEvent } from 'react'
import { BloqueCarga } from '../componentes/BloqueCarga.tsx'
import { CabeceraPagina } from '../componentes/CabeceraPagina.tsx'
import { NivelAlerta } from '../componentes/NivelAlerta.tsx'
import { TablaVacia } from '../componentes/TablaVacia.tsx'
import { useEstadoCentros } from '../hooks/useEstadoCentros.ts'
import {
  obtenerHistorialAlertas, type AlertaHistorica, type EstadoNotificacion, type FiltrosHistorial,
} from '../servicios/alertas.ts'
import { entero, rangoSemana } from '../utilidades/formato.ts'

const COLUMNAS = [
  'Centro', 'Emisión', 'Semana objetivo', 'Nivel', 'Pronóstico', 'Consultas observadas', 'Comparación', 'Dotación sugerida',
  'Notificación y acuse',
]
const FECHA_LOCAL = new Intl.DateTimeFormat('es-CL', {
  dateStyle: 'short', timeStyle: 'short', timeZone: 'America/Santiago',
})
const ETIQUETAS: Record<EstadoNotificacion, [singular: string, plural: string]> = {
  enviada: ['enviada sin confirmar', 'enviadas sin confirmar'],
  fallida: ['fallida', 'fallidas'],
  confirmada: ['confirmada', 'confirmadas'],
  reenviada: ['reenviada', 'reenviadas'],
  escalada: ['escalada', 'escaladas'],
}

function resultadoObservado({ consultas, semana_alta }: AlertaHistorica['observacion']): string {
  if (consultas === null) return 'Sin observación válida'
  if (semana_alta === null) return 'Sin umbral registrado'
  return semana_alta ? 'Superó el umbral' : 'No superó el umbral'
}

function Notificaciones({ datos }: { datos: AlertaHistorica['notificaciones'] }) {
  if (datos.tipo === 'no_aplica') {
    return <span className="tabla__sin-dato">No aplica: Atención no genera correo.</span>
  }
  if (datos.tipo === 'resumen') {
    if (datos.estados.length === 0) return <span className="tabla__sin-dato">Sin notificaciones registradas</span>
    return datos.estados.map(({ estado, total }) => (
      <div key={estado}>{entero(total)} {ETIQUETAS[estado][total === 1 ? 0 : 1]}</div>
    ))
  }
  if (datos.estado === null) return <span className="tabla__sin-dato">Sin notificación registrada</span>

  const etiqueta = ETIQUETAS[datos.estado][0]
  return (
    <>
      {etiqueta.charAt(0).toUpperCase() + etiqueta.slice(1)}
      {datos.fecha_confirmacion && (
        <time className="tabla__rango" dateTime={datos.fecha_confirmacion}>
          {FECHA_LOCAL.format(new Date(datos.fecha_confirmacion))}
        </time>
      )}
    </>
  )
}

function FilaAlerta({ alerta }: { alerta: AlertaHistorica }) {
  const { centro, fecha_emision, nivel, pronostico, observacion, dotacion } = alerta
  return (
    <tr>
      <th scope="row" className="tabla__centro">
        {centro.nombre}<span className="tabla__codigo">{centro.codigo_deis}</span>
      </th>
      <td><time dateTime={fecha_emision}>{FECHA_LOCAL.format(new Date(fecha_emision))}</time></td>
      <td>
        SE {pronostico.semana} · {pronostico.anio}
        <span className="tabla__rango">{rangoSemana(pronostico.inicio_semana)}</span>
      </td>
      <td><NivelAlerta nivel={nivel} /></td>
      <td className="tabla__numero">
        {entero(pronostico.valor)}
        <span className="tabla__rango">{entero(pronostico.limite_inferior)}–{entero(pronostico.limite_superior)}</span>
      </td>
      <td className="tabla__numero">
        {observacion.consultas === null ? <span className="tabla__sin-dato">Sin dato</span> : entero(observacion.consultas)}
      </td>
      <td>{resultadoObservado(observacion)}</td>
      <td>
        {dotacion ? (
          <>
            {entero(dotacion.profesionales)} {dotacion.profesionales === 1 ? 'profesional' : 'profesionales'}
            {dotacion.por_validar && <span className="tabla__rango">Supuestos por validar</span>}
          </>
        ) : <span className="tabla__sin-dato">Sin dotación registrada</span>}
      </td>
      <td><Notificaciones datos={alerta.notificaciones} /></td>
    </tr>
  )
}

export function PantallaHistorialAlertas() {
  const { centros, cargando: cargandoCentros, error: errorCentros } = useEstadoCentros()
  const [filtros, setFiltros] = useState<FiltrosHistorial>({})
  const [aplicados, setAplicados] = useState<FiltrosHistorial>({})
  const [resultado, setResultado] = useState<{
    filtros: FiltrosHistorial
    filas: AlertaHistorica[] | null
  } | null>(null)
  const [errorRango, setErrorRango] = useState(false)

  // Cada respuesta pertenece a una consulta. Un filtro nuevo cancela la anterior.
  useEffect(() => {
    const peticion = new AbortController()
    obtenerHistorialAlertas(aplicados, peticion.signal)
      .then((filas) => {
        if (!peticion.signal.aborted) setResultado({ filtros: aplicados, filas })
      })
      .catch(() => {
        if (!peticion.signal.aborted) setResultado({ filtros: aplicados, filas: null })
      })
    return () => peticion.abort()
  }, [aplicados])

  const actual = resultado?.filtros === aplicados ? resultado : null
  const filas = actual?.filas
  const hayFiltros = Object.values(aplicados).some(Boolean)

  function aplicar(evento: FormEvent<HTMLFormElement>) {
    evento.preventDefault()
    if (filtros.desde && filtros.hasta && filtros.desde > filtros.hasta) {
      setErrorRango(true)
      return
    }
    setErrorRango(false)
    setAplicados({ ...filtros })
  }

  function limpiar() {
    setFiltros({})
    setAplicados({})
    setErrorRango(false)
  }

  return (
    <div className="pagina">
      <CabeceraPagina antetitulo="Alertas de demanda" titulo="Historial de alertas" />

      <form className="filtros filtros--historial" aria-label="Filtros del historial" onSubmit={aplicar}>
        <div className="campo">
          <label htmlFor="historial-centro">Centro</label>
          <div className="campo__caja">
            <select id="historial-centro" value={filtros.codigo_deis ?? ''}
              disabled={cargandoCentros || Boolean(errorCentros)}
              onChange={(e) => setFiltros({ ...filtros, codigo_deis: Number(e.target.value) || undefined })}>
              <option value="">{cargandoCentros ? 'Cargando centros…' : 'Todos los centros visibles'}</option>
              {centros?.map(({ centro }) =>
                <option key={centro.codigo_deis} value={centro.codigo_deis}>{centro.nombre}</option>,
              )}
            </select>
          </div>
        </div>
        <div className="campo">
          <label htmlFor="historial-desde">Desde</label>
          <div className="campo__caja">
            <input id="historial-desde" type="date" value={filtros.desde ?? ''} aria-invalid={errorRango}
              aria-describedby={errorRango ? 'historial-error-rango' : undefined}
              onChange={(e) => { setFiltros({ ...filtros, desde: e.target.value || undefined }); setErrorRango(false) }} />
          </div>
        </div>
        <div className="campo">
          <label htmlFor="historial-hasta">Hasta</label>
          <div className="campo__caja">
            <input id="historial-hasta" type="date" value={filtros.hasta ?? ''} aria-invalid={errorRango}
              aria-describedby={errorRango ? 'historial-error-rango' : undefined}
              onChange={(e) => { setFiltros({ ...filtros, hasta: e.target.value || undefined }); setErrorRango(false) }} />
          </div>
        </div>
        <div className="campo">
          <label htmlFor="historial-nivel">Nivel</label>
          <div className="campo__caja">
            <select id="historial-nivel" value={filtros.nivel ?? ''} onChange={(e) =>
              setFiltros({ ...filtros, nivel: (e.target.value || undefined) as FiltrosHistorial['nivel'] })}>
              <option value="">Todos los niveles</option>
              <option value="atencion">Atención</option>
              <option value="alerta">Alerta</option>
            </select>
          </div>
        </div>
        <div className="historial__pie-filtros">
          <p className="nota">El rango incluye las semanas epidemiológicas de ambas fechas.</p>
          {errorCentros && <p className="nota" role="status">No se pudo cargar la lista de centros.</p>}
          {errorRango && (
            <p id="historial-error-rango" className="nota" role="alert">
              La fecha desde debe ser anterior o igual a hasta.
            </p>
          )}
          <div className="historial__acciones">
            <button type="submit" className="boton-primario">Aplicar filtros</button>
            <button type="button" className="boton-secundario" onClick={limpiar}>Limpiar filtros</button>
          </div>
        </div>
      </form>

      <section className="tarjeta" aria-labelledby="historial-resultados">
        <div className="tarjeta__encabezado">
          <div>
            <h2 id="historial-resultados" className="tarjeta__titulo">Alertas emitidas</h2>
            <p className="tarjeta__bajada">La comparación usa las consultas observadas y el umbral de alerta original.</p>
          </div>
        </div>
        {actual === null && (
          <div className="tabla-carga" role="status">
            <span className="oculto-visual">Cargando historial de alertas</span>
            <BloqueCarga alto="14rem" radio="12px" />
          </div>
        )}
        {filas === null && (
          <div className="pendiente">
            <span role="alert">No se pudo cargar el historial de alertas.</span>
            <button type="button" className="boton-secundario" onClick={() => setAplicados({ ...aplicados })}>
              Reintentar
            </button>
          </div>
        )}
        {filas?.length === 0 && (
          <TablaVacia titulo="Historial de alertas emitidas" columnas={COLUMNAS}
            mensaje={hayFiltros ? 'Ninguna alerta coincide con los filtros' : 'Todavía no hay alertas emitidas'} />
        )}
        {filas && filas.length > 0 && (
          <div className="tabla-contenedor" tabIndex={0} role="region" aria-label="Alertas emitidas (desplazable)">
            <table className="tabla">
              <caption className="oculto-visual">Historial de alertas emitidas</caption>
              <thead><tr>{COLUMNAS.map((columna) => <th key={columna} scope="col">{columna}</th>)}</tr></thead>
              <tbody>{filas.map((alerta) => <FilaAlerta key={alerta.id} alerta={alerta} />)}</tbody>
            </table>
          </div>
        )}
      </section>
    </div>
  )
}
