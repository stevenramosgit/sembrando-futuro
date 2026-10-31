// Cliente de la API (documento 18). Devuelve {estado, datos, cabeceras}; lanza ErrorRed si no hay conexión con el servidor.
import { API_BASE } from "./config.js";

export class ErrorRed extends Error {}

/** Une la dirección del servidor, la ruta y los parámetros de consulta que tengan valor (los vacíos no se envían). */
function armarUrl(ruta, consulta) {
  if (!consulta) return API_BASE + ruta;
  const q = new URLSearchParams(Object.entries(consulta).filter(([, v]) => v !== undefined && v !== null));
  return API_BASE + ruta + ([...q].length ? "?" + q : "");
}

/** Hace una petición a la API y devuelve {estado, datos, cabeceras}. Si el teléfono no logra hablar con el servidor
 *  (sin señal, servidor dormido), lanza ErrorRed para que la pantalla guarde el dato en el dispositivo y lo sincronice después. */
export async function llamar(metodo, ruta, { cuerpo, token, consulta } = {}) {
  const cabeceras = { Accept: "application/json" };
  if (cuerpo !== undefined) cabeceras["Content-Type"] = "application/json";
  if (token) cabeceras.Authorization = "Bearer " + token;
  const url = armarUrl(ruta, consulta);
  let r;
  try {
    r = await fetch(url, { method: metodo, headers: cabeceras, body: cuerpo !== undefined ? JSON.stringify(cuerpo) : undefined, cache: "no-store" });
  } catch (e) {
    throw new ErrorRed(e.message);
  }
  let datos = null;
  if (r.status !== 204 && r.status !== 304) { try { datos = await r.json(); } catch { datos = null; } }
  return { estado: r.status, datos, cabeceras: r.headers };
}
/** Error que devolvió la API ({codigo, mensaje, campos}) o null si la respuesta no trae error. */
export const error = (r) => r.datos?.error || null;
