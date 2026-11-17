import { useId, useState, type FormEvent } from 'react'
import { EstadoConsultaConfiguracion } from '../componentes/EstadoConsultaConfiguracion.tsx'
import { EstadoVacio } from '../componentes/EstadoVacio.tsx'
import { IconoNivel } from '../componentes/NivelAlerta.tsx'
import { useConsultaConfiguracion } from '../hooks/useConsultaConfiguracion.ts'
import {
  guardarUmbral, listarUmbrales, mensajeErrorConfiguracion, type UmbralPorCentro,
} from '../servicios/configuracionAdministracion.ts'
import { leerNumeroNoNegativo } from '../utilidades/configuracion.ts'

export function UmbralesAdministracion() {
  const id = useId()
  const { estado, recargar, actualizar } = useConsultaConfiguracion(listarUmbrales, 'No se pudieron cargar los umbrales.')
  const [codigo, setCodigo] = useState('')
  const [atencion, setAtencion] = useState('')
  const [alerta, setAlerta] = useState('')
  const [motivo, setMotivo] = useState('')
  const [guardando, setGuardando] = useState(false)
  const [error, setError] = useState('')
  const [guardado, setGuardado] = useState(false)
  const centros = estado.tipo === 'lista' ? estado.datos : []
  const seleccionado = centros.find((fila) => String(fila.centro.codigo_deis) === codigo)
  const umbral = seleccionado?.umbral

  function cargarValores(vigente: UmbralPorCentro['umbral']) {
    setAtencion(vigente ? String(vigente.umbral_atencion) : '')
    setAlerta(vigente ? String(vigente.umbral_alerta) : '')
    setMotivo('')
  }

  function elegirCentro(nuevo: string) {
    setCodigo(nuevo)
    cargarValores(centros.find((fila) => String(fila.centro.codigo_deis) === nuevo)?.umbral ?? null)
    setError('')
    setGuardado(false)
  }

  async function guardar(evento: FormEvent<HTMLFormElement>) {
    evento.preventDefault()
    if (!seleccionado || guardando) return
    setGuardado(false)
    setError('')
    const justificacion = motivo.trim()
    const desdeAtencion = leerNumeroNoNegativo(atencion)
    const desdeAlerta = leerNumeroNoNegativo(alerta)
    if (!justificacion) {
      setError('El motivo del cambio es obligatorio.')
      return
    }
    if (desdeAtencion === null || desdeAlerta === null) {
      setError('Ingrese dos umbrales numéricos no negativos.')
      return
    }
    if (desdeAtencion > desdeAlerta) {
      setError('Atención debe ser menor o igual que Alerta.')
      return
    }

    setGuardando(true)
    try {
      const nuevo = await guardarUmbral(seleccionado.centro.codigo_deis, {
        umbral_atencion: desdeAtencion, umbral_alerta: desdeAlerta, motivo: justificacion,
      })
      actualizar((datos) => datos.map((fila) => fila.centro.codigo_deis === nuevo.centro.codigo_deis ? nuevo : fila))
      cargarValores(nuevo.umbral)
      setGuardado(true)
    } catch (fallo) {
      setError(mensajeErrorConfiguracion(fallo, 'No se pudieron guardar los umbrales.'))
    } finally {
      setGuardando(false)
    }
  }

  return (
    <section className="tarjeta" aria-labelledby={`${id}-titulo`}>
      <h2 id={`${id}-titulo`} className="tarjeta__titulo">Umbrales por centro</h2>
      <p className="tarjeta__bajada">
        Los cambios manuales se registran en el historial y se aplican en la siguiente corrida semanal.
      </p>
      {estado.tipo !== 'lista' ? (
        <EstadoConsultaConfiguracion estado={estado} textoCarga="Cargando umbrales" reintentar={recargar} />
      ) : centros.length === 0 ? (
        <EstadoVacio titulo="Todavía no hay centros configurables" />
      ) : (
        <>
          <form className="formulario-grilla" noValidate onSubmit={guardar}>
            <div className="campo">
              <label htmlFor={`${id}-centro`}>Centro a configurar</label>
              <div className="campo__caja">
                <select id={`${id}-centro`} value={codigo} disabled={guardando}
                  onChange={(evento) => elegirCentro(evento.target.value)}>
                  <option value="">Seleccione un centro</option>
                  {centros.map(({ centro }) => (
                    <option key={centro.codigo_deis} value={centro.codigo_deis}>{centro.nombre}</option>
                  ))}
                </select>
              </div>
              {seleccionado && (
                <span className="nota">
                  {umbral
                    ? `Umbral vigente: ${umbral.origen === 'manual' ? 'manual' : 'calculado'}${umbral.anios_usados ? ` (${umbral.anios_usados})` : ''}.`
                    : 'Este centro aún no tiene umbrales vigentes.'}
                </span>
              )}
            </div>
            <div className="campo">
              <label htmlFor={`${id}-atencion`}>
                <IconoNivel nivel="atencion" className="campo__icono-nivel campo__icono-nivel--atencion" />
                Atención desde
              </label>
              <div className="campo__caja">
                <input id={`${id}-atencion`} type="number" step="any" min="0" required
                  disabled={!seleccionado || guardando} value={atencion}
                  onChange={(evento) => { setAtencion(evento.target.value); setGuardado(false) }} />
              </div>
            </div>
            <div className="campo">
              <label htmlFor={`${id}-alerta`}>
                <IconoNivel nivel="alerta" className="campo__icono-nivel campo__icono-nivel--alerta" />
                Alerta desde
              </label>
              <div className="campo__caja">
                <input id={`${id}-alerta`} type="number" step="any" min="0" required
                  disabled={!seleccionado || guardando} value={alerta}
                  onChange={(evento) => { setAlerta(evento.target.value); setGuardado(false) }} />
              </div>
            </div>
            <div className="campo campo--ancho">
              <label htmlFor={`${id}-motivo`}>Motivo del cambio</label>
              <textarea id={`${id}-motivo`} rows={3} required disabled={!seleccionado || guardando} value={motivo}
                onChange={(evento) => { setMotivo(evento.target.value); setGuardado(false) }} />
            </div>
            <div className="formulario-grilla__pie">
              <p className="nota">Consultas por semana. Atención debe ser menor o igual que Alerta. El motivo es obligatorio.</p>
              <button type="submit" className="boton-primario" disabled={!seleccionado || guardando}>
                {guardando ? 'Guardando umbrales…' : 'Guardar umbrales'}
              </button>
            </div>
          </form>
          {error && <p className="pendiente" role="alert">{error}</p>}
          {guardado && <p className="nota" role="status">Umbrales guardados.</p>}
        </>
      )}
    </section>
  )
}
