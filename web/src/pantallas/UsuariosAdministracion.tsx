import GroupOutlinedIcon from '@mui/icons-material/GroupOutlined'
import PersonAddAltOutlinedIcon from '@mui/icons-material/PersonAddAltOutlined'
import { Dialog, DialogActions, DialogContent, DialogTitle } from '@mui/material'
import { useCallback, useEffect, useState, type FormEvent } from 'react'
import { BloqueCarga } from '../componentes/BloqueCarga.tsx'
import { TablaVacia } from '../componentes/TablaVacia.tsx'
import { useSesion } from '../contexto/sesion.tsx'
import { useReferencias } from '../hooks/useReferencias.ts'
import { asignarCentros, crearCuenta, darDeBaja, listarCuentas, mensajeDeError } from '../servicios/administracion.ts'
import { obtenerEstadoCentros } from '../servicios/centros.ts'
import type { Cuenta, RolCuenta } from '../tipos/index.ts'

const ETIQUETA_ROL: Record<RolCuenta, string> = {
  jefatura: 'Jefatura',
  subdirector: 'Subdirector',
  administrador: 'Administrador',
}
const COLUMNAS = ['Usuario / correo', 'Rol', 'Centro o alcance', 'Acción']

type Centro = { codigo_deis: number; nombre: string }

function ErrorFormulario({ mensaje }: { mensaje: string | null }) {
  return mensaje ? <p className="error-formulario" role="alert">{mensaje}</p> : null
}

// Lista de casillas de centros (RF-9). Solo las jefaturas tienen centros: el subdirector y el administrador
// ven toda la red (RNF-S-2).
function ElegirCentros({ centros, elegidos, cambiar }: {
  centros: Centro[]; elegidos: number[]; cambiar: (codigos: number[]) => void
}) {
  return (
    <fieldset className="casillas">
      <legend>Centros asignados</legend>
      {centros.map((c) => (
        <label key={c.codigo_deis} className="casillas__opcion">
          <input type="checkbox" checked={elegidos.includes(c.codigo_deis)}
            onChange={(e) => cambiar(e.target.checked
              ? [...elegidos, c.codigo_deis]
              : elegidos.filter((x) => x !== c.codigo_deis))} />
          {c.nombre} <span className="tabla__codigo">{c.codigo_deis}</span>
        </label>
      ))}
    </fieldset>
  )
}

// Alta de cuenta (RF-16): el administrador muestra el texto de §5.3 al funcionario y marca su aceptación.
// Sin la casilla no se envía nada; si igual llega a la API, esta responde 422 sin guardar datos (TC-16).
function DialogoCrear({ centros, cerrar, creada }: { centros: Centro[]; cerrar: () => void; creada: () => void }) {
  const { referencias } = useReferencias()
  const [datos, setDatos] = useState({ nombre: '', correo: '', rol: 'jefatura' as RolCuenta, contrasena: '' })
  const [elegidos, setElegidos] = useState<number[]>([])
  const [acepta, setAcepta] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [enviando, setEnviando] = useState(false)

  const cambiar = (campo: keyof typeof datos) => (e: { target: { value: string } }) =>
    setDatos({ ...datos, [campo]: e.target.value })

  const enviar = async (evento: FormEvent) => {
    evento.preventDefault()
    setEnviando(true)
    setError(null)
    try {
      await crearCuenta({
        ...datos,
        acepta_finalidad: acepta,
        version_texto: referencias?.finalidad_version ?? '',
        centros: datos.rol === 'jefatura' ? elegidos : [],
      })
      creada()
    } catch (e) {
      setError(mensajeDeError(e))
    } finally {
      setEnviando(false)
    }
  }

  return (
    <Dialog open onClose={cerrar} aria-labelledby="titulo-crear" fullWidth maxWidth="sm">
      <form onSubmit={enviar}>
        <DialogTitle id="titulo-crear">Crear usuario</DialogTitle>
        <DialogContent>
          <ErrorFormulario mensaje={error} />
          <div className="campo">
            <label htmlFor="alta-nombre">Nombre</label>
            <div className="campo__caja"><input id="alta-nombre" required value={datos.nombre} onChange={cambiar('nombre')} /></div>
          </div>
          <div className="campo">
            <label htmlFor="alta-correo">Correo institucional</label>
            <div className="campo__caja">
              <input id="alta-correo" type="email" required value={datos.correo} onChange={cambiar('correo')} />
            </div>
          </div>
          <div className="campo">
            <label htmlFor="alta-rol">Rol</label>
            <div className="campo__caja">
              <select id="alta-rol" value={datos.rol} onChange={cambiar('rol')}>
                {Object.entries(ETIQUETA_ROL).map(([valor, etiqueta]) => <option key={valor} value={valor}>{etiqueta}</option>)}
              </select>
            </div>
          </div>
          <div className="campo">
            <label htmlFor="alta-clave">Contraseña inicial</label>
            <div className="campo__caja">
              <input id="alta-clave" type="password" autoComplete="new-password" required value={datos.contrasena}
                onChange={cambiar('contrasena')} />
            </div>
          </div>
          {datos.rol === 'jefatura' && <ElegirCentros centros={centros} elegidos={elegidos} cambiar={setElegidos} />}
          <section className="aviso aviso--importante finalidad" aria-labelledby="titulo-finalidad">
            <div>
              <h3 id="titulo-finalidad" className="finalidad__titulo">
                Finalidad del tratamiento de datos (versión {referencias?.finalidad_version ?? '…'})
              </h3>
              <p>{referencias?.finalidad_texto ?? 'Cargando el texto…'}</p>
              <label className="casillas__opcion">
                <input type="checkbox" checked={acepta} onChange={(e) => setAcepta(e.target.checked)} />
                El funcionario leyó y aceptó este texto
              </label>
            </div>
          </section>
        </DialogContent>
        <DialogActions>
          <button type="button" className="boton-secundario" onClick={cerrar}>Cancelar</button>
          <button type="submit" className="boton-primario" disabled={!acepta || enviando || !referencias}>
            {enviando ? 'Creando…' : 'Crear cuenta'}
          </button>
        </DialogActions>
      </form>
    </Dialog>
  )
}

function DialogoCentros({ cuenta, centros, cerrar, guardada }: {
  cuenta: Cuenta; centros: Centro[]; cerrar: () => void; guardada: () => void
}) {
  const [elegidos, setElegidos] = useState(cuenta.centros.map((c) => c.codigo_deis))
  const [error, setError] = useState<string | null>(null)

  const guardar = async (evento: FormEvent) => {
    evento.preventDefault()
    try {
      await asignarCentros(cuenta.id, elegidos)
      guardada()
    } catch (e) {
      setError(mensajeDeError(e))
    }
  }

  return (
    <Dialog open onClose={cerrar} aria-labelledby="titulo-centros" fullWidth maxWidth="sm">
      <form onSubmit={guardar}>
        <DialogTitle id="titulo-centros">Centros de {cuenta.nombre}</DialogTitle>
        <DialogContent>
          <ErrorFormulario mensaje={error} />
          <ElegirCentros centros={centros} elegidos={elegidos} cambiar={setElegidos} />
        </DialogContent>
        <DialogActions>
          <button type="button" className="boton-secundario" onClick={cerrar}>Cancelar</button>
          <button type="submit" className="boton-primario">Guardar centros</button>
        </DialogActions>
      </form>
    </Dialog>
  )
}

// Pestaña «Usuarios» de Administración (RF-9, RF-16). Sin columna «Estado»: la baja borra la cuenta
// (pendientes #18 y #24).
export function UsuariosAdministracion() {
  const { usuario } = useSesion()
  const [cuentas, setCuentas] = useState<Cuenta[] | null>(null)
  const [centros, setCentros] = useState<Centro[]>([])
  const [error, setError] = useState<string | null>(null)
  const [dialogo, setDialogo] = useState<'crear' | Cuenta | null>(null)

  const cargar = useCallback(() => {
    listarCuentas().then(setCuentas).catch((e) => setError(mensajeDeError(e)))
  }, [])

  useEffect(() => {
    cargar()
    obtenerEstadoCentros()
      .then((estado) => setCentros(estado.map((e) => e.centro).sort((a, b) => a.codigo_deis - b.codigo_deis)))
      .catch(() => setCentros([]))
  }, [cargar])

  const terminar = () => {
    setDialogo(null)
    cargar()
  }

  const bajar = async (cuenta: Cuenta) => {
    if (!window.confirm(`¿Dar de baja a ${cuenta.nombre}? Se borran su nombre, correo y centros; queda solo el registro de auditoría sin datos personales.`)) return
    try {
      await darDeBaja(cuenta.id)
      cargar()
    } catch (e) {
      setError(mensajeDeError(e))
    }
  }

  return (
    <section className="tarjeta" aria-labelledby="titulo-usuarios">
      <div className="tarjeta__encabezado">
        <div>
          <h2 id="titulo-usuarios" className="tarjeta__titulo">Usuarios y permisos</h2>
          <p className="tarjeta__bajada">Solo el administrador crea cuentas, con la aceptación de la finalidad (RF-16).</p>
        </div>
        <button type="button" className="boton-primario" onClick={() => setDialogo('crear')}>
          <PersonAddAltOutlinedIcon aria-hidden="true" /> Crear usuario
        </button>
      </div>
      <ErrorFormulario mensaje={error} />
      {cuentas === null && !error && <BloqueCarga />}
      {cuentas?.length === 0 && (
        <TablaVacia titulo="Usuarios y permisos" columnas={COLUMNAS} icono={<GroupOutlinedIcon />}
          mensaje="Todavía no hay cuentas" />
      )}
      {!!cuentas?.length && (
        <div className="tabla-contenedor" tabIndex={0} role="region" aria-label="Usuarios y permisos (desplazable)">
          <table className="tabla">
            <caption className="oculto-visual">Usuarios y permisos</caption>
            <thead><tr>{COLUMNAS.map((c) => <th key={c} scope="col">{c}</th>)}</tr></thead>
            <tbody>
              {cuentas.map((c) => (
                <tr key={c.id}>
                  <th scope="row" className="tabla__centro">
                    {c.nombre}<span className="tabla__codigo">{c.correo}</span>
                  </th>
                  <td>{ETIQUETA_ROL[c.rol]}{c.rol === 'administrador' && !c.mfa_activo && ' (MFA sin activar)'}</td>
                  <td>
                    {c.rol !== 'jefatura' ? 'Toda la red'
                      : c.centros.length ? c.centros.map((x) => x.nombre).join(', ')
                        : <span className="tabla__sin-dato">Sin centros asignados</span>}
                  </td>
                  <td className="acciones">
                    {c.rol === 'jefatura' && (
                      <button type="button" className="boton-enlace" onClick={() => setDialogo(c)}
                        aria-label={`Centros de ${c.nombre}`}>Centros</button>
                    )}
                    {c.id !== usuario?.id && (
                      <button type="button" className="boton-enlace" onClick={() => bajar(c)}
                        aria-label={`Dar de baja a ${c.nombre}`}>Dar de baja</button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      <p className="nota">
        Jefatura: solo su centro · Subdirector: lectura y seguimiento de la red · Administrador: cuentas, umbrales
        e historial, con verificación en dos pasos.
      </p>
      {dialogo === 'crear' && <DialogoCrear centros={centros} cerrar={() => setDialogo(null)} creada={terminar} />}
      {dialogo && dialogo !== 'crear' && (
        <DialogoCentros cuenta={dialogo} centros={centros} cerrar={() => setDialogo(null)} guardada={terminar} />
      )}
    </section>
  )
}
