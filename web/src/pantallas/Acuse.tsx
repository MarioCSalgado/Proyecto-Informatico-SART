import CheckCircleOutlineIcon from '@mui/icons-material/CheckCircleOutlineOutlined'
import NotificationsActiveOutlinedIcon from '@mui/icons-material/NotificationsActiveOutlined'
import { useEffect, useState } from 'react'
import { useParams } from 'react-router'
import { BloqueCarga } from '../componentes/BloqueCarga.tsx'
import { CabeceraPagina } from '../componentes/CabeceraPagina.tsx'
import { mensajeDeError } from '../servicios/administracion.ts'
import { confirmarLectura, obtenerAcuse } from '../servicios/acuse.ts'
import type { Acuse } from '../tipos/index.ts'

const NIVEL: Record<string, string> = { atencion: 'Atención', alerta: 'ALERTA', sobre_la_norma: 'Sobre la norma' }
const fecha = (iso: string) => new Date(iso).toLocaleString('es-CL', { dateStyle: 'medium', timeStyle: 'short', hourCycle: 'h23' })

// Página de acuse (RF-15): abrirla no registra nada; la lectura se confirma solo con el botón (RF-15 paso 2).
export function PantallaAcuse() {
  const { token = '' } = useParams()
  const [acuse, setAcuse] = useState<Acuse | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [enviando, setEnviando] = useState(false)

  useEffect(() => {
    obtenerAcuse(token).then(setAcuse).catch((e) => setError(mensajeDeError(e)))
  }, [token])

  const confirmar = async () => {
    setEnviando(true)
    try {
      setAcuse(await confirmarLectura(token))
    } catch (e) {
      setError(mensajeDeError(e))
    } finally {
      setEnviando(false)
    }
  }

  const nivel = acuse ? NIVEL[acuse.alerta.nivel] ?? acuse.alerta.nivel : ''
  return (
    <div className="pagina">
      <CabeceraPagina antetitulo="Notificación" titulo="Confirmar lectura"
        subtitulo="Confirme que leyó la alerta para que no se reenvíe ni se avise al Subdirector (RB-2)." />
      {error && <p className="error-formulario" role="alert">{error}</p>}
      {!acuse && !error && <BloqueCarga alto="10rem" radio="16px" />}
      {acuse && (
        <section className="tarjeta" aria-labelledby="titulo-alerta">
          <h2 id="titulo-alerta" className="tarjeta__titulo">
            <NotificationsActiveOutlinedIcon aria-hidden="true" /> {acuse.alerta.lugar} · nivel {nivel}
          </h2>
          <p>{acuse.alerta.mensaje}</p>
          <p className="nota">Enviada el {fecha(acuse.fecha_envio)}</p>
          {acuse.fecha_confirmacion ? (
            <p className="aviso" role="status">
              <CheckCircleOutlineIcon className="aviso__icono" aria-hidden="true" />
              Lectura confirmada el {fecha(acuse.fecha_confirmacion)}.
            </p>
          ) : (
            <button type="button" className="boton-primario" onClick={confirmar} disabled={enviando}>
              <CheckCircleOutlineIcon aria-hidden="true" /> {enviando ? 'Confirmando…' : 'Confirmar lectura'}
            </button>
          )}
        </section>
      )}
    </div>
  )
}
