// Formato de cifras y fechas en español de Chile, para todas las pantallas.

const ENTERO = new Intl.NumberFormat("es-CL", { maximumFractionDigits: 0 });
const DECIMAL = new Intl.NumberFormat("es-CL", { minimumFractionDigits: 1, maximumFractionDigits: 1 });

/** 1234.6 → «1.235» */
export const entero = (n: number) => ENTERO.format(Math.round(n));

/** 7.13 → «7,1» */
export const decimal = (n: number) => DECIMAL.format(n);

/** Fecha ISO «2026-09-27» como día local (sin corrimiento por zona horaria). */
export function fechaLocal(iso: string): Date {
    const [anio = 1970, mes = 1, dia = 1] = iso.split("-").map(Number);
    return new Date(anio, mes - 1, dia);
}

/** «2026-09-27» → «27 sep» */
export const diaMes = (iso: string) =>
    fechaLocal(iso).toLocaleDateString("es-CL", { day: "numeric", month: "short" }).replace(".", "");

/** «2026-10-04» → «4 al 10 oct» (semana de domingo a sábado) */
export function rangoSemana(inicio: string): string {
    const desde = fechaLocal(inicio);
    const hasta = new Date(desde);
    hasta.setDate(desde.getDate() + 6);
    const mesHasta = hasta.toLocaleDateString("es-CL", { month: "short" }).replace(".", "");
    if (desde.getMonth() === hasta.getMonth()) return `${desde.getDate()} al ${hasta.getDate()} ${mesHasta}`;
    return `${diaMes(inicio)} al ${hasta.getDate()} ${mesHasta}`;
}
