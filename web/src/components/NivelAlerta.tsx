import CheckCircleOutlineIcon from '@mui/icons-material/CheckCircleOutlineOutlined';
import ErrorOutlineIcon from '@mui/icons-material/ErrorOutlineOutlined';
import ReportProblemOutlinedIcon from '@mui/icons-material/ReportProblemOutlined';
import type { NivelAlerta as Nivel } from '../types/index.ts';

// RNF-U-1: el nivel nunca se indica solo con color. Siempre va con texto y con un ícono de forma distinta.
const NIVELES: Record<Nivel, { texto: string; Icono: typeof CheckCircleOutlineIcon }> = {
  normal:   { texto: 'Normal',   Icono: CheckCircleOutlineIcon },
  atencion: { texto: 'Atención', Icono: ErrorOutlineIcon },
  alerta:   { texto: 'ALERTA',   Icono: ReportProblemOutlinedIcon },
};

export function NivelAlerta({ nivel }: { nivel: Nivel }) {
  const { texto, Icono } = NIVELES[nivel];
  return (
    <span className={`badge nivel nivel--${nivel}`}>
      <Icono fontSize="small" aria-hidden="true" />
      {texto}
    </span>
  );
}
