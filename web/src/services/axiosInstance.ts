import axios from "axios";
import environment from "../constants/envs.ts";

// El JWT viaja en una cookie httpOnly que pone la API (RNF-S-1): el navegador la envía sola y el código
// de la página no puede leerla. Por eso no hay token en localStorage ni cabecera Authorization.
const axiosInstance = axios.create({
  baseURL: environment.API_URL,
  withCredentials: true,
});

export default axiosInstance;
