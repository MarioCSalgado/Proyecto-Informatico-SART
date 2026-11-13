import { NivelAlerta, NivelCorto } from './NivelAlerta.tsx'

// Cómo se lee el nivel de cada centro (RF-3, RB-3). Los umbrales son percentiles de cada centro, no cifras
// fijas: el diseño de Figma muestra 400/500, pero eso contradice RB-3 (docs/pendientes_informe.md #21).
export function LeyendaNiveles({ conAbreviaturas = false }: { conAbreviaturas?: boolean }) {
  return (
    <section className="tarjeta" aria-labelledby="titulo-leyenda">
      <h2 id="titulo-leyenda" className="tarjeta__titulo">Cómo leer los niveles</h2>
      <p className="tarjeta__bajada">Cada centro se compara con su propia historia de los últimos tres años.</p>
      <ul className="leyenda">
        <li>
          <NivelAlerta nivel="normal" />
          {conAbreviaturas && <NivelCorto nivel="normal" />}
          <span>Pronóstico bajo el percentil 75 del centro.</span>
        </li>
        <li>
          <NivelAlerta nivel="atencion" />
          {conAbreviaturas && <NivelCorto nivel="atencion" />}
          <span>Pronóstico sobre el percentil 75.</span>
        </li>
        <li>
          <NivelAlerta nivel="alerta" />
          {conAbreviaturas && <NivelCorto nivel="alerta" />}
          <span>Pronóstico, con su margen de incertidumbre, sobre el percentil 90.</span>
        </li>
      </ul>
    </section>
  )
}
