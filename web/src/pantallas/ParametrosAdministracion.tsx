import { useId, useState, type FormEvent } from 'react'
import { EstadoConsultaConfiguracion } from '../componentes/EstadoConsultaConfiguracion.tsx'
import { EstadoVacio } from '../componentes/EstadoVacio.tsx'
import { useConsultaConfiguracion } from '../hooks/useConsultaConfiguracion.ts'
import {
  guardarParametro, listarParametros, mensajeErrorConfiguracion,
} from '../servicios/configuracionAdministracion.ts'
import { etiquetaParametro, leerNumeroNoNegativo } from '../utilidades/configuracion.ts'

export function ParametrosAdministracion() {
  const id = useId()
  const { estado, recargar, actualizar } = useConsultaConfiguracion(listarParametros, 'No se pudieron cargar los parámetros.')
  const [clave, setClave] = useState('')
  const [valor, setValor] = useState('')
  const [motivo, setMotivo] = useState('')
  const [guardando, setGuardando] = useState(false)
  const [error, setError] = useState('')
  const [guardado, setGuardado] = useState(false)
  const parametros = estado.tipo === 'lista' ? estado.datos : []
  const seleccionado = parametros.find((fila) => fila.clave === clave)
  const editable = seleccionado?.valor === null || typeof seleccionado?.valor === 'number'

  function elegirParametro(nueva: string) {
    const vigente = parametros.find((fila) => fila.clave === nueva)?.valor
    setClave(nueva)
    setValor(typeof vigente === 'number' ? String(vigente) : '')
    setMotivo('')
    setError('')
    setGuardado(false)
  }

  async function guardar(evento: FormEvent<HTMLFormElement>) {
    evento.preventDefault()
    if (!editable || guardando) return
    setGuardado(false)
    setError('')
    const justificacion = motivo.trim()
    const numero = leerNumeroNoNegativo(valor)
    if (!justificacion) {
      setError('El motivo del cambio es obligatorio.')
      return
    }
    if (numero === null) {
      setError('Ingrese un valor numérico no negativo.')
      return
    }

    setGuardando(true)
    try {
      const nuevo = await guardarParametro(clave, { valor: numero, motivo: justificacion })
      actualizar((datos) => datos.map((fila) => fila.clave === nuevo.clave ? nuevo : fila))
      setValor(typeof nuevo.valor === 'number' ? String(nuevo.valor) : '')
      setMotivo('')
      setGuardado(true)
    } catch (fallo) {
      setError(mensajeErrorConfiguracion(fallo, 'No se pudo guardar el parámetro.'))
    } finally {
      setGuardando(false)
    }
  }

  return (
    <section className="tarjeta" aria-labelledby={`${id}-titulo`}>
      <h2 id={`${id}-titulo`} className="tarjeta__titulo">Parámetros editables</h2>
      <p className="tarjeta__bajada">
        Los ajustes quedan registrados al guardar. Los cuantiles y la ventana de umbrales se usan en el próximo recálculo.
      </p>
      {estado.tipo !== 'lista' ? (
        <EstadoConsultaConfiguracion estado={estado} textoCarga="Cargando parámetros" reintentar={recargar} />
      ) : parametros.length === 0 ? (
        <EstadoVacio titulo="Todavía no hay parámetros editables" />
      ) : (
        <>
          <form className="formulario-grilla" noValidate onSubmit={guardar}>
            <div className="campo">
              <label htmlFor={`${id}-clave`}>Parámetro a configurar</label>
              <div className="campo__caja">
                <select id={`${id}-clave`} value={clave} disabled={guardando}
                  onChange={(evento) => elegirParametro(evento.target.value)}>
                  <option value="">Seleccione un parámetro</option>
                  {parametros.map(({ clave }) => <option key={clave} value={clave}>{etiquetaParametro(clave)}</option>)}
                </select>
              </div>
              {seleccionado?.valor === null && <span className="nota">Valor vigente sin definir.</span>}
              {seleccionado && !editable && <span className="nota">Este formulario admite ajustes numéricos.</span>}
            </div>
            <div className="campo">
              <label htmlFor={`${id}-valor`}>Valor del parámetro</label>
              <div className="campo__caja">
                <input id={`${id}-valor`} type="number" step="any" min="0" required value={valor}
                  disabled={!editable || guardando}
                  onChange={(evento) => { setValor(evento.target.value); setGuardado(false) }} />
              </div>
            </div>
            <div className="campo">
              <label htmlFor={`${id}-motivo`}>Motivo del ajuste</label>
              <textarea id={`${id}-motivo`} rows={3} required disabled={!editable || guardando} value={motivo}
                onChange={(evento) => { setMotivo(evento.target.value); setGuardado(false) }} />
            </div>
            <div className="formulario-grilla__pie">
              <p className="nota">El motivo es obligatorio.</p>
              <button type="submit" className="boton-primario" disabled={!editable || guardando}>
                {guardando ? 'Guardando parámetro…' : 'Guardar parámetro'}
              </button>
            </div>
          </form>
          {error && <p className="pendiente" role="alert">{error}</p>}
          {guardado && <p className="nota" role="status">Parámetro guardado.</p>}
        </>
      )}
    </section>
  )
}
