// Leyenda fija del gráfico de consultas semanales (diseño «Inicio de jefatura»). Cada serie se distingue por
// la forma de su muestra (línea continua, punteada, banda) y por su nombre, no solo por el color (RNF-U-1).
const SERIES = [
  { nombre: 'Observado', muestra: <line x1="2" y1="6" x2="26" y2="6" className="muestra--observado" /> },
  { nombre: 'Pronóstico', muestra: <line x1="2" y1="6" x2="26" y2="6" className="muestra--pronostico" /> },
  { nombre: 'Intervalo 90 %', muestra: <rect x="2" y="1" width="24" height="10" className="muestra--intervalo" /> },
  { nombre: 'Umbral de alerta', muestra: <line x1="2" y1="6" x2="26" y2="6" className="muestra--umbral" /> },
]

export function LeyendaGrafico() {
  return (
    <ul className="leyenda-grafico" aria-label="Leyenda del gráfico">
      {SERIES.map(({ nombre, muestra }) => (
        <li key={nombre}>
          <svg viewBox="0 0 28 12" aria-hidden="true">{muestra}</svg>
          {nombre}
        </li>
      ))}
    </ul>
  )
}
