import type { Role } from '../auth/permissions.ts';

/** Usuario autenticado tal como lo entrega la API (actividad 8). Solo datos de la cuenta (§5.3). */
export type Usuario = {
  id: number;
  nombre: string;
  rol: Role;
};

/** Niveles de la alerta de demanda (RF-3, RB-3). */
export type NivelAlerta = 'normal' | 'atencion' | 'alerta';
