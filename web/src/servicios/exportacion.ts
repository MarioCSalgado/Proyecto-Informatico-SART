import clienteApi from "./clienteApi.ts";

// Servicio de RF-11: el CSV lo arma la API con los centros que el usuario puede ver (la jefatura, solo los suyos).
export const RUTA_EXPORTAR_CENTROS = "exportar/centros.csv";

function nombreDelArchivo(disposicion: string | undefined, porDefecto: string): string {
    const coincidencia = disposicion?.match(/filename="?([^"]+)"?/);
    return coincidencia?.[1] ?? porDefecto;
}

/** GET /exportar/centros.csv[?codigo_deis=]: descarga el CSV (UTF-8, «;») en el navegador. */
export async function descargarCsvCentros(codigo?: number): Promise<void> {
    const respuesta = await clienteApi.get(RUTA_EXPORTAR_CENTROS, {
        params: codigo === undefined ? undefined : { codigo_deis: codigo },
        responseType: "blob",
    });
    const nombre = nombreDelArchivo(respuesta.headers["content-disposition"], "sart_centros.csv");
    const url = URL.createObjectURL(respuesta.data as Blob);
    const enlace = document.createElement("a");
    enlace.href = url;
    enlace.download = nombre;
    document.body.appendChild(enlace);
    enlace.click();
    enlace.remove();
    URL.revokeObjectURL(url);
}
