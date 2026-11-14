import type { Role } from '../auth/permissions.ts';

/** Usuario autenticado tal como lo entrega la API (actividad 8). Solo datos de la cuenta (§5.3). */
export type Usuario = {
  id: number;
  nombre: string;
  rol: Role;
};

/** Niveles de la alerta de demanda (RF-3, RB-3). */
export type NivelAlerta = 'normal' | 'atencion' | 'alerta';

/** Un nivel de la escala de MP2,5 de RB-1, tal como lo entrega GET /referencias (límites en µg/m³). */
export type NivelMp25 = {
  clave: string;
  nombre: string;
  desde: number;
  hasta: number | null;
};

/** Valores fijos que la API lee de config/parametros.yaml (RNF-M-4): la web no los escribe en su código. */
export type Referencias = {
  mp25_niveles: NivelMp25[];
  comunas: string[];
};
