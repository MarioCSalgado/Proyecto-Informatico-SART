import GroupsOutlinedIcon from '@mui/icons-material/GroupsOutlined'
import HistoryToggleOffOutlinedIcon from '@mui/icons-material/HistoryToggleOffOutlined'
import HourglassEmptyOutlinedIcon from '@mui/icons-material/HourglassEmptyOutlined'
import ShowChartOutlinedIcon from '@mui/icons-material/ShowChartOutlined'
import TableChartOutlinedIcon from '@mui/icons-material/TableChartOutlined'
import { useState } from 'react'
import type { Dotacion, EstadoCentro, NivelMp25, Pronostico } from '../tipos/index.ts'
import { decimal, entero, rangoSemana } from '../utilidades/formato.ts'
import { AvisoPendiente } from './AvisoPendiente.tsx'
import { BotonExportarCsv } from './BotonExportarCsv.tsx'
import { EscalaMp25 } from './EscalaMp25.tsx'
import { EstadoVacio } from './EstadoVacio.tsx'
import { GraficoConsultas, TablaConsultas } from './GraficoConsultas.tsx'
import { LeyendaGrafico } from './LeyendaGrafico.tsx'
import { NivelAlerta } from './NivelAlerta.tsx'

// Detalle del estado de un centro (RF-7, paso 3): pronóstico con su intervalo y nivel, gráfico de las últimas
// semanas, dotación sugerida (RF-6) y MP2,5 de su zona (RB-5). Lo usan «Mi centro» (jefatura) y el detalle de
// un centro de la red (subdirector y administrador). Solo cifras agregadas (RNF-S-5).

function AvisosDatos({ pronostico }: { pronostico: Pronostico }) {
  return (
    <>
      {pronostico.desactualizado && (
        <p className="aviso aviso--importante" role="status">
          <HistoryToggleOffOutlinedIcon className="aviso__icono" aria-hidden="true" />
          <span>
            <strong>Pronóstico desactualizado.</strong> Es de la SE {pronostico.semana} y esa ya no es la semana en
            curso: falta la última semana completa del DEIS. No se emitieron alertas nuevas (RF-3 E2).
          </span>
        </p>
      )}
      {pronostico.datos_antiguos && (
        <p className="aviso aviso--importante" role="status">
          <HistoryToggleOffOutlinedIcon className="aviso__icono" aria-hidden="true" />
          <span>
            <strong>Datos antiguos.</strong> Las consultas del DEIS llegan solo hasta la semana del{' '}
            {rangoSemana(pronostico.fecha_corte)}.
          </span>
        </p>
      )}
    </>
  )
}

function ResumenPronostico({ pronostico }: { pronostico: Pronostico | null }) {
  if (!pronostico) {
    return (
      <div className="pronostico__resumen">
        <p className="antetitulo">Próxima semana</p>
        <h2 id="titulo-pronostico" className="tarjeta__titulo">Pronóstico de consultas</h2>
        <p className="pronostico__cifra" aria-hidden="true">—</p>
        <p className="pronostico__unidad">consultas respiratorias esperadas</p>
        <p className="pronostico__estado">
          <HourglassEmptyOutlinedIcon aria-hidden="true" />
          Sin pronóstico todavía
        </p>
        <p className="pronostico__bajada">
          Aquí aparecerán las consultas esperadas, su rango con 90 % de confianza y el nivel del centro.
        </p>
      </div>
    )
  }
  const { umbrales } = pronostico
  return (
    <div className="pronostico__resumen">
      <p className="antetitulo">SE {pronostico.semana} · {rangoSemana(pronostico.inicio_semana)}</p>
      <h2 id="titulo-pronostico" className="tarjeta__titulo">Pronóstico de consultas</h2>
      <p className="pronostico__cifra">{entero(pronostico.valor)}</p>
      <p className="pronostico__unidad">consultas respiratorias esperadas</p>
      <p className="pronostico__rango">
        Rango con 90 % de confianza: <strong>{entero(pronostico.limite_inferior)} a {entero(pronostico.limite_superior)}</strong>
      </p>
      <div className="pronostico__nivel">
        {pronostico.nivel ? <NivelAlerta nivel={pronostico.nivel} /> : <span className="pronostico__estado">Sin nivel: el centro no tenía umbral</span>}
      </div>
      {umbrales && (
        <p className="pronostico__umbrales">
          Atención sobre {entero(umbrales.atencion)} · Alerta sobre {entero(umbrales.alerta)}
          {pronostico.valor_con_margen !== null && <> · con margen: {entero(pronostico.valor_con_margen)}</>}
        </p>
      )}
      <p className="pronostico__bajada">
        Datos del DEIS hasta la semana del {rangoSemana(pronostico.fecha_corte)}.
      </p>
    </div>
  )
}

function TarjetaDotacion({ dotacion }: { dotacion: Dotacion | null }) {
  const s = dotacion?.supuestos
  return (
    <section className="tarjeta tarjeta--suave" aria-labelledby="titulo-dotacion">
      <span className="tarjeta__icono" aria-hidden="true"><GroupsOutlinedIcon /></span>
      <h2 id="titulo-dotacion" className="tarjeta__titulo">Dotación sugerida</h2>
      <p className="tarjeta__bajada">Escenario orientativo para el centro en hora punta</p>
      {dotacion ? (
        <>
          <p className="dotacion__cifra">
            <span className="dotacion__numero">{dotacion.profesionales}</span>
            {dotacion.profesionales === 1 ? ' profesional' : ' profesionales'}
          </p>
          <p className="dotacion__detalle">
            Espera media de {decimal(dotacion.espera_media_min)} min con {decimal(dotacion.llegadas_hora_punta)} llegadas
            por hora en hora punta.
            {dotacion.espera_con_uno_menos_min !== null && dotacion.profesionales > 1 && (
              <> Con {dotacion.profesionales - 1}, la espera sería de {entero(dotacion.espera_con_uno_menos_min)} min.</>
            )}
          </p>
          {s && (
            <ul className="dotacion__supuestos" aria-label="Supuestos usados">
              {s.minutos_por_atencion !== undefined && <li>{s.minutos_por_atencion} min por atención</li>}
              {s.factor_hora_punta !== undefined && <li>Factor de hora punta {decimal(s.factor_hora_punta)}</li>}
              {s.horas_funcionamiento_semana !== undefined && <li>{s.horas_funcionamiento_semana} h de atención a la semana</li>}
              {s.espera_objetivo_min !== undefined && <li>Espera objetivo {s.espera_objetivo_min} min</li>}
            </ul>
          )}
          {dotacion.por_validar && <p className="etiqueta-por-validar">Supuestos por validar (RF-6)</p>}
        </>
      ) : (
        <p className="dotacion__vacio">Sin estimación todavía</p>
      )}
      <p className="nota">
        Estimación según demanda prevista y capacidad del centro. Validar turnos y disponibilidad local antes
        de actuar.
      </p>
    </section>
  )
}

type Props = {
  estado: EstadoCentro | null
  mp25Niveles: NivelMp25[] | null
  cargandoReferencias: boolean
  errorReferencias: boolean
}

export function DetalleCentro({ estado, mp25Niveles, cargandoReferencias, errorReferencias }: Props) {
  const [comoTabla, setComoTabla] = useState(false)
  const pronostico = estado?.pronostico ?? null
  const semanas = estado?.ultimas_semanas ?? []
  const hayGrafico = semanas.length + (pronostico ? 1 : 0) >= 2

  return (
    <>
      {pronostico && <AvisosDatos pronostico={pronostico} />}

      <section className="tarjeta pronostico" aria-labelledby="titulo-pronostico">
        <div className="pronostico__cuerpo">
          <ResumenPronostico pronostico={pronostico} />
          <div className="pronostico__grafico">
            <h3 className="subtitulo-tarjeta">Consultas respiratorias semanales</h3>
            <p className="tarjeta__bajada">
              Últimas {semanas.length || 12} semanas y pronóstico de la próxima
            </p>
            {hayGrafico ? (
              comoTabla ? <TablaConsultas semanas={semanas} pronostico={pronostico} /> : (
                <div className="grafico-contenedor"><GraficoConsultas semanas={semanas} pronostico={pronostico} /></div>
              )
            ) : (
              <div className="grafico-vacio">
                <EstadoVacio icono={<ShowChartOutlinedIcon />} titulo="Gráfico sin datos todavía" />
              </div>
            )}
            {!comoTabla && <LeyendaGrafico />}
            <p className="nota">La banda representa incertidumbre, no un máximo esperado.</p>
          </div>
        </div>
        <div className="tarjeta__pie">
          {hayGrafico ? (
            <p className="tarjeta__pie-dato">
              {estado && <>{estado.centro.nombre} · {estado.centro.comuna}</>}
              {pronostico && <> · modelo {pronostico.version_modelo}</>}
            </p>
          ) : (
            <AvisoPendiente>Disponible cuando la corrida semanal entregue el pronóstico del centro (RF-2, RF-7).</AvisoPendiente>
          )}
          <div className="acciones">
            <button type="button" className="boton-secundario" disabled={!hayGrafico} aria-pressed={comoTabla}
              onClick={() => setComoTabla((v) => !v)}>
              {comoTabla
                ? <><ShowChartOutlinedIcon aria-hidden="true" /> Ver como gráfico</>
                : <><TableChartOutlinedIcon aria-hidden="true" /> Ver como tabla</>}
            </button>
            <BotonExportarCsv codigo={estado?.centro.codigo_deis} desactivado={!estado} etiqueta="Descargar CSV" />
          </div>
        </div>
      </section>

      <div className="grilla-dos">
        <TarjetaDotacion dotacion={estado?.dotacion ?? null} />
        <EscalaMp25 niveles={mp25Niveles} cargando={cargandoReferencias} error={errorReferencias}
          actual={estado?.mp25 ?? null} />
      </div>
    </>
  )
}
