import type { Rol } from '../acceso/permisos.ts';

/** Usuario autenticado tal como lo entrega la API (actividad 8). Solo datos de la cuenta (§5.3). */
export type Usuario = {
  id: number;
  nombre: string;
  rol: Rol;
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
  finalidad_version?: string;  // texto de §5.3 que acepta el funcionario al crear su cuenta (RF-16)
  finalidad_texto?: string;
};

/** Rol tal como lo guarda la API (el de la sesión, `Rol`, es la etiqueta para mostrar). */
export type RolCuenta = 'jefatura' | 'subdirector' | 'administrador';

/** Cuenta tal como la entrega GET /administracion/usuarios (RF-9). */
export type Cuenta = {
  id: number;
  nombre: string;
  correo: string;
  rol: RolCuenta;
  mfa_activo: boolean;
  centros: { codigo_deis: number; nombre: string }[];
};

/** Datos de un alta (RF-16): sin la aceptación de la versión vigente, la API no crea nada. */
export type AltaCuenta = {
  nombre: string;
  correo: string;
  rol: RolCuenta;
  contrasena: string;
  acepta_finalidad: boolean;
  version_texto: string;
  centros: number[];
};

/** Umbrales con que se clasificó el pronóstico (no los vigentes: pendientes #39). */
export type UmbralesUsados = { atencion: number; alerta: number; origen: string };

/** Pronóstico vigente de un centro (RF-2, RF-3), tal como lo entrega GET /centros/estado. Fechas en ISO. */
export type Pronostico = {
  anio: number;
  semana: number;
  inicio_semana: string;
  fecha_corte: string;
  valor: number;
  limite_inferior: number;
  limite_superior: number;
  nivel: NivelAlerta | null;
  valor_con_margen: number | null;
  k_margen: number | null;
  version_modelo: string;
  desactualizado: boolean;  // RF-3 E2
  datos_antiguos: boolean;  // RF-7 E1
  umbrales: UmbralesUsados | null;
};

/** Dotación sugerida guardada con los supuestos usados (RF-6). */
export type Dotacion = {
  profesionales: number;
  llegadas_hora_punta: number;
  espera_media_min: number;
  espera_con_uno_menos_min: number | null;
  supuestos: {
    minutos_por_atencion?: number;
    factor_hora_punta?: number;
    horas_funcionamiento_semana?: number;
    espera_objetivo_min?: number;
    supuestos_validados?: boolean;
  };
  por_validar: boolean;  // RF-6 E1
};

/** MP2,5 de la zona del centro (RB-5, RF-7 E3). */
export type Mp25Zona = {
  estado: 'ok' | 'datos_insuficientes';
  estacion: string | null;
  de_respaldo: boolean;
  fecha: string | null;
  valor: number | null;
  nivel: { clave: string; nombre: string } | null;
};

export type SemanaObservada = {
  anio: number;
  semana: number;
  inicio: string;
  consultas: number;
  nivel_observado: NivelAlerta | null;
};

/** Estado de un centro (RF-7): solo cifras agregadas, sin datos de pacientes (RNF-S-5). */
export type EstadoCentro = {
  centro: {
    codigo_deis: number;
    nombre: string;
    tipo: string;
    comuna: string;
    latitud: number | null;
    longitud: number | null;
    estacion_asignada: string;
  };
  pronostico: Pronostico | null;
  dotacion: Dotacion | null;
  mp25: Mp25Zona;
  ultimas_semanas: SemanaObservada[];
};

/** Notificación vista desde la página de acuse (RF-15), tal como la entrega GET /acuse/{token}. */
export type Acuse = {
  estado: 'enviada' | 'fallida' | 'confirmada' | 'reenviada' | 'escalada';
  fecha_envio: string;
  fecha_confirmacion: string | null;
  alerta: { tipo: string; nivel: string; mensaje: string; fecha_emision: string; lugar: string; dia_pronosticado: string | null };
};
