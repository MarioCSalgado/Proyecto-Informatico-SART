import ApartmentOutlinedIcon from '@mui/icons-material/ApartmentOutlined'
import DownloadOutlinedIcon from '@mui/icons-material/DownloadOutlined'
import SearchOutlinedIcon from '@mui/icons-material/SearchOutlined'
import { lazy, Suspense, useMemo, useState } from 'react'
import { Link } from 'react-router'
import { AvisoPendiente } from '../componentes/AvisoPendiente.tsx'
import { BloqueCarga } from '../componentes/BloqueCarga.tsx'
import { CabeceraPagina } from '../componentes/CabeceraPagina.tsx'
import { EstadoVacio } from '../componentes/EstadoVacio.tsx'
import { IconoNivel, NivelAlerta, NivelCorto } from '../componentes/NivelAlerta.tsx'
import { TablaVacia } from '../componentes/TablaVacia.tsx'
import { useEstadoCentros } from '../hooks/useEstadoCentros.ts'
import { useReferencias } from '../hooks/useReferencias.ts'
import type { EstadoCentro, NivelAlerta as Nivel } from '../tipos/index.ts'
import { entero, rangoSemana } from '../utilidades/formato.ts'

const NIVELES: Nivel[] = ['alerta', 'atencion', 'normal']
const ETIQUETAS: Record<Nivel, string> = { alerta: 'Alerta', atencion: 'Atención', normal: 'Normal' }
const COLUMNAS = ['Centro', 'Comuna', 'Pronóstico', 'Nivel', 'Confirmación', 'Últimas 12 semanas']
const MapaCentros = lazy(() =>
  import('../componentes/MapaCentros.tsx').then(({ MapaCentros: Mapa }) => ({ default: Mapa })),
)

function normalizar(texto: string): string {
  return texto.normalize('NFD').replace(/[̀-ͯ]/g, '').toLowerCase()
}

function FilaCentro({ estado }: { estado: EstadoCentro }) {
  const { centro, pronostico, ultimas_semanas: semanas } = estado
  return (
    <tr>
      <th scope="row" className="tabla__centro">
        <Link to={`/red/${centro.codigo_deis}`}>{centro.nombre}</Link>
        <span className="tabla__codigo">{centro.tipo} · {centro.codigo_deis}</span>
      </th>
      <td>{centro.comuna}</td>
      <td className="tabla__numero">
        {pronostico ? (
          <>
            {entero(pronostico.valor)}
            <span className="tabla__rango">{entero(pronostico.limite_inferior)}–{entero(pronostico.limite_superior)}</span>
          </>
        ) : '—'}
      </td>
      <td>{pronostico?.nivel ? <NivelAlerta nivel={pronostico.nivel} /> : <span className="tabla__sin-dato">Sin nivel</span>}</td>
      <td><span className="tabla__sin-dato" title="Llega con el acuse de lectura (RF-15)">—</span></td>
      <td>
        <ol className="calendario" aria-label={`Nivel observado de ${centro.nombre} en las últimas semanas`}>
          {semanas.map((s) => (
            <li key={s.inicio} title={`SE ${s.semana} · ${rangoSemana(s.inicio)}: ${entero(s.consultas)} consultas`}>
              {s.nivel_observado ? <NivelCorto nivel={s.nivel_observado} /> : <span className="nivel-corto">—</span>}
            </li>
          ))}
        </ol>
      </td>
    </tr>
  )
}

// Vista de red del subdirector (diseño «Vista de red»; RF-7 con todos los centros). La API entrega los centros ya
// ordenados Alerta → Atención → Normal y, dentro de cada nivel, por pronóstico (RF-7 paso 2); los filtros se
// aplican aquí. Cada centro abre su detalle (paso 3). La confirmación llega con RF-15 y la exportación con RF-11.
export function PantallaRedCentros() {
  const { referencias } = useReferencias()
  const { centros, cargando, error } = useEstadoCentros()
  const comunas = referencias?.comunas ?? []
  const [comuna, setComuna] = useState('')
  const [busqueda, setBusqueda] = useState('')

  const filtrados = useMemo(() => {
    const texto = normalizar(busqueda.trim())
    return (centros ?? []).filter((c) =>
      (!comuna || c.centro.comuna === comuna) &&
      (!texto || normalizar(c.centro.nombre).includes(texto) || String(c.centro.codigo_deis).includes(texto)))
  }, [centros, comuna, busqueda])

  const conteo = (nivel: Nivel) => (centros ? centros.filter((c) => c.pronostico?.nivel === nivel).length : null)
  const corte = centros?.find((c) => c.pronostico)?.pronostico
  const valor = (n: number | null) => (n === null ? '—' : entero(n))

  return (
    <div className="pagina">
      <CabeceraPagina
        antetitulo="Vista de red"
        titulo="Red de centros"
        subtitulo={corte
          ? `Gran Concepción · pronóstico de la SE ${corte.semana} (${rangoSemana(corte.inicio_semana)})`
          : 'Gran Concepción · centros de urgencia'}
        acciones={
          <button type="button" className="boton-secundario" disabled title="Llega con RF-11">
            <DownloadOutlinedIcon aria-hidden="true" /> Exportar red CSV
          </button>
        }
      />

      <ul className="kpis" aria-label="Resumen de la red">
        <li className="kpi kpi--total">
          <span className="kpi__icono" aria-hidden="true"><ApartmentOutlinedIcon /></span>
          <span className="kpi__valor">{valor(centros ? centros.length : null)}</span>
          <span className="kpi__etiqueta">Centros en la red</span>
        </li>
        {NIVELES.map((nivel) => (
          <li key={nivel} className={`kpi kpi--${nivel}`}>
            <span className="kpi__icono" aria-hidden="true"><IconoNivel nivel={nivel} /></span>
            <span className="kpi__valor">{valor(conteo(nivel))}</span>
            <span className="kpi__etiqueta">{ETIQUETAS[nivel]}</span>
          </li>
        ))}
      </ul>

      <div className="filtros">
        <div className="campo">
          <label htmlFor="filtro-comuna">Comuna</label>
          <div className="campo__caja">
            <select id="filtro-comuna" value={comuna} onChange={(e) => setComuna(e.target.value)}>
              <option value="">Todas las comunas ({comunas.length})</option>
              {comunas.map((c) => <option key={c} value={c}>{c}</option>)}
            </select>
          </div>
        </div>
        <div className="campo">
          <label htmlFor="filtro-centro">Buscar centro</label>
          <div className="campo__caja">
            <input id="filtro-centro" type="search" placeholder="Nombre o código del centro" value={busqueda}
              onChange={(e) => setBusqueda(e.target.value)} />
            <SearchOutlinedIcon className="campo__icono" aria-hidden="true" />
          </div>
        </div>
        <p className="filtros__orden">
          <strong>Orden: Alerta → Atención → Normal</strong>
          <span>Dentro de cada nivel, el mayor pronóstico primero.</span>
        </p>
      </div>

      {centros && (
        <section className="tarjeta" aria-labelledby="titulo-mapa-centros">
          <div className="tarjeta__encabezado">
            <div>
              <h2 id="titulo-mapa-centros" className="tarjeta__titulo">Mapa de centros</h2>
              <p className="tarjeta__bajada">Ubicación, nivel de pronóstico y estación asignada</p>
            </div>
          </div>
          <Suspense fallback={<p className="mapa-centros__vacio" role="status">Cargando mapa…</p>}>
            <MapaCentros centros={filtrados} />
          </Suspense>
        </section>
      )}

      <section className="tarjeta" aria-labelledby="titulo-seguimiento">
        <div className="tarjeta__encabezado">
          <div>
            <h2 id="titulo-seguimiento" className="tarjeta__titulo">Seguimiento de centros</h2>
            <p className="tarjeta__bajada">
              Calendario de calor por centro, últimas 12 semanas · N = Normal · At = Atención · Al = Alerta
            </p>
          </div>
        </div>
        <ul className="leyenda-chips" aria-label="Niveles del calendario">
          {NIVELES.slice().reverse().map((nivel) => (
            <li key={nivel}><NivelCorto nivel={nivel} /><NivelAlerta nivel={nivel} /></li>
          ))}
        </ul>
        <p className="nota">
          Umbrales de cada centro: percentiles 75 y 90 de sus últimos 3 años (RB-3). El calendario compara las
          consultas ya ocurridas con esos umbrales.
        </p>

        {cargando && <div className="tabla-carga"><BloqueCarga alto="14rem" radio="12px" /></div>}
        {error && <p className="pendiente" role="alert">No se pudo cargar la red. Intente recargar la página.</p>}
        {centros && centros.length === 0 && (
          <TablaVacia
            titulo="Seguimiento de centros"
            columnas={COLUMNAS}
            icono={<ApartmentOutlinedIcon />}
            mensaje="Todavía no hay pronósticos de la red"
            detalle="Aparecerá cada centro con su nivel, el estado de su confirmación y sus últimas semanas."
          />
        )}
        {centros && centros.length > 0 && (
          <>
            <div className="tabla-contenedor" tabIndex={0} role="region" aria-label="Seguimiento de centros (desplazable)">
              <table className="tabla">
                <caption className="oculto-visual">
                  Seguimiento de centros: {filtrados.length} de {centros.length} centros
                </caption>
                <thead>
                  <tr>{COLUMNAS.map((c) => <th key={c} scope="col">{c}</th>)}</tr>
                </thead>
                <tbody>
                  {filtrados.map((c) => <FilaCentro key={c.centro.codigo_deis} estado={c} />)}
                </tbody>
              </table>
            </div>
            {filtrados.length === 0 && (
              <EstadoVacio icono={<SearchOutlinedIcon />} titulo="Ningún centro coincide con los filtros"
                descripcion="Pruebe con otra comuna o con otro nombre o código." />
            )}
          </>
        )}
        <AvisoPendiente>La confirmación de lectura llega con RF-15 y la exportación CSV con RF-11.</AvisoPendiente>
      </section>
    </div>
  )
}
