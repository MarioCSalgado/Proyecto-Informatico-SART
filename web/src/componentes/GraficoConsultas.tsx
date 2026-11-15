import type { Pronostico, SemanaObservada } from '../tipos/index.ts'
import { entero, rangoSemana } from '../utilidades/formato.ts'
import { NivelAlerta } from './NivelAlerta.tsx'

// Gráfico de consultas semanales de un centro (DESIGN.md · Gráfico de consultas). SVG propio, sin librería:
// observado en línea continua azul noche, pronóstico en línea discontinua verde azulado, intervalo de 90 % como
// banda y umbral de alerta como línea fina con su rótulo. Las series se distinguen por la forma, no solo por el
// color (RNF-U-1), y hay una tabla con las mismas cifras («Ver como tabla»).

const ANCHO = 640
const ALTO = 260
const M = { arriba: 18, derecha: 92, abajo: 30, izquierda: 48 }

function pasoRedondo(maximo: number): number {
  const bruto = maximo / 4
  const potencia = 10 ** Math.floor(Math.log10(bruto || 1))
  return [1, 2, 2.5, 5, 10].map((f) => f * potencia).find((p) => p >= bruto) ?? bruto
}

type Props = {
  semanas: SemanaObservada[]
  pronostico: Pronostico | null
}

export function GraficoConsultas({ semanas, pronostico }: Props) {
  const puntos = semanas.length + (pronostico ? 1 : 0)
  if (puntos < 2) return null
  const umbral = pronostico?.umbrales?.alerta ?? null
  const valores = [
    ...semanas.map((s) => s.consultas),
    ...(pronostico ? [pronostico.limite_superior] : []),
    ...(umbral !== null ? [umbral] : []),
  ]
  const paso = pasoRedondo(Math.max(...valores) * 1.08)
  const tope = Math.ceil((Math.max(...valores) * 1.08) / paso) * paso
  const anchoUtil = ANCHO - M.izquierda - M.derecha
  const altoUtil = ALTO - M.arriba - M.abajo
  const x = (i: number) => M.izquierda + (anchoUtil * i) / (puntos - 1)
  const y = (v: number) => M.arriba + altoUtil * (1 - v / tope)
  const marcas = Array.from({ length: Math.round(tope / paso) + 1 }, (_, i) => i * paso)

  const observado = semanas.map((s, i) => `${x(i)},${y(s.consultas)}`).join(' ')
  const ultimo = semanas.length - 1
  const ultimaSemana = semanas[ultimo]
  const resumen = pronostico
    ? `Consultas de las últimas ${semanas.length} semanas, de ${entero(Math.min(...semanas.map((s) => s.consultas)))} a ` +
      `${entero(Math.max(...semanas.map((s) => s.consultas)))}; pronóstico de la SE ${pronostico.semana}: ` +
      `${entero(pronostico.valor)} (rango de ${entero(pronostico.limite_inferior)} a ${entero(pronostico.limite_superior)})`
    : `Consultas de las últimas ${semanas.length} semanas`

  return (
    <svg className="grafico" viewBox={`0 0 ${ANCHO} ${ALTO}`} role="img" aria-label={resumen}>
      {marcas.map((v) => (
        <g key={v} className="grafico__marca">
          <line x1={M.izquierda} x2={ANCHO - M.derecha} y1={y(v)} y2={y(v)} />
          <text x={M.izquierda - 10} y={y(v)} dy="0.32em" textAnchor="end">{entero(v)}</text>
        </g>
      ))}
      {umbral !== null && (
        <g className="grafico__umbral">
          <line x1={M.izquierda} x2={ANCHO - M.derecha} y1={y(umbral)} y2={y(umbral)} />
          <text x={ANCHO - M.derecha + 8} y={y(umbral)} dy="0.32em">Alerta {entero(umbral)}</text>
        </g>
      )}
      {pronostico && ultimaSemana && (
        <>
          <polygon
            className="grafico__banda"
            points={`${x(ultimo)},${y(ultimaSemana.consultas)} ${x(puntos - 1)},${y(pronostico.limite_superior)} ` +
              `${x(puntos - 1)},${y(pronostico.limite_inferior)}`}
          />
          <line className="grafico__pronostico" x1={x(ultimo)} y1={y(ultimaSemana.consultas)}
            x2={x(puntos - 1)} y2={y(pronostico.valor)} />
        </>
      )}
      <polyline className="grafico__observado" points={observado} />
      {semanas.map((s, i) => <circle key={s.inicio} className="grafico__punto" cx={x(i)} cy={y(s.consultas)} r="3.5" />)}
      {pronostico && (
        <circle className="grafico__punto grafico__punto--pronostico" cx={x(puntos - 1)} cy={y(pronostico.valor)} r="6" />
      )}
      {semanas.map((s, i) => (puntos - 1 - i) % 3 === 0 && (
        <text key={s.inicio} className="grafico__eje" x={x(i)} y={ALTO - 8} textAnchor="middle">SE {s.semana}</text>
      ))}
      {pronostico && (
        <text className="grafico__eje grafico__eje--pronostico" x={x(puntos - 1)} y={ALTO - 8} textAnchor="middle">
          SE {pronostico.semana}
        </text>
      )}
    </svg>
  )
}

/** Las mismas cifras del gráfico, en tabla (alternativa accesible). */
export function TablaConsultas({ semanas, pronostico }: Props) {
  return (
    <div className="tabla-contenedor tabla-contenedor--interna" tabIndex={0} role="region"
      aria-label="Consultas semanales (desplazable)">
      <table className="tabla">
        <caption className="oculto-visual">Consultas respiratorias semanales y pronóstico</caption>
        <thead>
          <tr>
            <th scope="col">Semana</th>
            <th scope="col">Fechas</th>
            <th scope="col" className="tabla__numero">Consultas</th>
            <th scope="col">Nivel</th>
          </tr>
        </thead>
        <tbody>
          {semanas.map((s) => (
            <tr key={s.inicio}>
              <td>SE {s.semana} de {s.anio}</td>
              <td>{rangoSemana(s.inicio)}</td>
              <td className="tabla__numero">{entero(s.consultas)}</td>
              <td>{s.nivel_observado ? <NivelAlerta nivel={s.nivel_observado} /> : '—'}</td>
            </tr>
          ))}
          {pronostico && (
            <tr className="tabla__fila-pronostico">
              <td>SE {pronostico.semana} de {pronostico.anio} (pronóstico)</td>
              <td>{rangoSemana(pronostico.inicio_semana)}</td>
              <td className="tabla__numero">
                {entero(pronostico.valor)}{' '}
                <span className="tabla__rango">({entero(pronostico.limite_inferior)}–{entero(pronostico.limite_superior)})</span>
              </td>
              <td>{pronostico.nivel ? <NivelAlerta nivel={pronostico.nivel} /> : '—'}</td>
            </tr>
          )}
        </tbody>
      </table>
    </div>
  )
}
