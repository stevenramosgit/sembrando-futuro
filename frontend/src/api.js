// Cliente de la API (documento 18). Devuelve {estado, datos, cabeceras}; lanza ErrorRed si no hay conexión con el servidor.
import { API_BASE } from "./config.js";

export class ErrorRed extends Error {}

export async function llamar(metodo, ruta, { cuerpo, token, consulta } = {}) {
  const cabeceras = { Accept: "application/json" };
  if (cuerpo !== undefined) cabeceras["Content-Type"] = "application/json";
  if (token) cabeceras.Authorization = "Bearer " + token;
  let url = API_BASE + ruta;
  if (consulta) { const q = new URLSearchParams(Object.entries(consulta).filter(([, v]) => v !== undefined && v !== null)); if ([...q].length) url += "?" + q; }
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
export const error = (r) => r.datos?.error || null;
