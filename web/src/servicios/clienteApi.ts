import axios from "axios";
import entorno from "../constantes/entorno.ts";

// El JWT viaja en una cookie httpOnly que pone la API (RNF-S-1): el navegador la envía sola y el código
// de la página no puede leerla. Por eso no hay token en localStorage ni cabecera Authorization.
const clienteApi = axios.create({
  baseURL: entorno.URL_API,
  withCredentials: true,
});

export default clienteApi;
