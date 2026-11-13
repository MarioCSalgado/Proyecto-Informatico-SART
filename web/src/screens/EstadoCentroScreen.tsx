import { EmptyState } from '../components/EmptyState.tsx';
import { NivelAlerta } from '../components/NivelAlerta.tsx';
import { usePermissions } from '../hooks/usePermissions.ts';

// RF-7: estado de alerta de los centros del usuario. Pantalla vacía del esqueleto: los datos llegan en la
// actividad 8 (API y consulta). Debe mostrar nivel, pronóstico con intervalo, dotación, fecha de corte y
// advertencias de calidad, en 4 clics o menos (RNF-U-2).
export function EstadoCentroScreen() {
  const { can } = usePermissions();
  const titulo = can('ver_todos_los_centros') ? 'Estado de los centros' : 'Estado de mis centros';

  return (
    <main className="contenedor-principal">
      <div className="cabecera-vista">
        <div className="titulos-cabecera">
          <h1 className="titulo-principal">{titulo}</h1>
          <p className="subtitulo">Pronóstico de consultas respiratorias de la semana</p>
        </div>
      </div>

      <section className="seccion-card">
        <EmptyState
          icon="🛠️"
          title="Todavía no hay datos para mostrar"
          description="Pendiente: actividad 8 (RF-7). Aquí aparecerá el nivel de cada centro con su pronóstico."
        />
      </section>

      <section className="seccion-card mt-3" aria-labelledby="leyenda-niveles">
        <h2 id="leyenda-niveles" className="titulo-seccion">Niveles de alerta</h2>
        <ul className="leyenda-niveles">
          <li><NivelAlerta nivel="normal" /> bajo el percentil 75 del centro</li>
          <li><NivelAlerta nivel="atencion" /> sobre el percentil 75</li>
          <li><NivelAlerta nivel="alerta" /> pronóstico con margen sobre el percentil 90</li>
        </ul>
      </section>
    </main>
  );
}
