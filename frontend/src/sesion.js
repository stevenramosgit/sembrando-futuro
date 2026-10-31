// Control de la sesión en el dispositivo (RF-03 y RNF-04): se cierra sola tras 30 minutos sin uso y, aunque se use sin parar,
// a las 12 horas de haber escrito la clave (OWASP ASVS 4.0.3, requisito 3.3.2, nivel 2). El servidor aplica las mismas
// reglas a su token; aquí se aplican también para que la sesión se cierre aunque el teléfono esté sin conexión.
//
// Para que el agricultor pueda volver a entrar sin internet, al ingresar se guarda en el teléfono un «verificador» de la
// clave: una huella PBKDF2-SHA256 con sal aleatoria y 600.000 repeticiones (recomendación de OWASP). La clave nunca se guarda.
import { guardarSesion, leerSesion } from "./estado.js";

export const MINUTOS_SIN_USO = 30;
export const HORAS_MAXIMAS = 12;
export const INTENTOS_SIN_CONEXION = 5;
const REPETICIONES = 600000;
const MIN = 60000;
let ultimaEscritura = 0;

/** Pasa bytes a texto base64 para guardarlos en IndexedDB. */
const aBase64 = (bytes) => btoa(String.fromCharCode(...new Uint8Array(bytes)));
/** Pasa texto base64 a bytes. */
const deBase64 = (texto) => Uint8Array.from(atob(texto), (c) => c.charCodeAt(0));

/** Huella PBKDF2-SHA256 de la clave con la sal y las repeticiones dadas (usa la criptografía del navegador). */
async function huella(clave, sal, repeticiones) {
  const llave = await crypto.subtle.importKey("raw", new TextEncoder().encode(clave), "PBKDF2", false, ["deriveBits"]);
  return crypto.subtle.deriveBits({ name: "PBKDF2", hash: "SHA-256", salt: sal, iterations: repeticiones }, llave, 256);
}

/** Crea el verificador de la clave (sal aleatoria de 16 bytes). Si el navegador no tiene criptografía, devuelve null
 *  y en ese caso, sin conexión, la persona tendrá que esperar a tener internet para volver a entrar. */
export async function crearVerificador(clave) {
  try {
    const sal = crypto.getRandomValues(new Uint8Array(16));
    return { sal: aBase64(sal), repeticiones: REPETICIONES, huella: aBase64(await huella(clave, sal, REPETICIONES)) };
  } catch { return null; }
}

/** true si la clave escrita produce la misma huella que el verificador guardado (comparación de tiempo constante). */
export async function claveCoincide(clave, v) {
  if (!v) return false;
  try {
    const a = new Uint8Array(await huella(clave, deBase64(v.sal), v.repeticiones)), b = deBase64(v.huella);
    let diferencia = a.length ^ b.length;
    for (let i = 0; i < a.length && i < b.length; i++) diferencia |= a[i] ^ b[i];
    return diferencia === 0;
  } catch { return false; }
}

/** Motivo por el que la sesión guardada ya no sirve sin volver a escribir la clave, o null si sigue vigente:
 *  V-51 (30 minutos sin uso) o V-52 (12 horas desde que escribió la clave). */
export function motivoDeCierre(s, ahora = Date.now()) {
  if (!s) return null;
  const minutos = s.inactividad_min || MINUTOS_SIN_USO;
  const ingreso = s.autenticado_en || 0;
  if (ahora - ingreso >= HORAS_MAXIMAS * 60 * MIN) return "V-52";
  if (ahora - (s.ultima_actividad || ingreso) >= minutos * MIN) return "V-51";
  return null;
}

/** Anota que la persona tocó o escribió algo. Se guarda en el teléfono como mucho cada 15 segundos. */
export async function anotarActividad(usuario, ahora = Date.now()) {
  if (!usuario) return;
  usuario.ultima_actividad = ahora;
  if (ahora - ultimaEscritura < 15000) return;
  ultimaEscritura = ahora;
  const s = await leerSesion();
  if (s && s.id === usuario.id && !s.bloqueada) await guardarSesion({ ...s, ultima_actividad: ahora });
}

/** Deja la sesión guardada como bloqueada: los datos y los pendientes siguen en el teléfono, pero hay que escribir la clave. */
export async function bloquearGuardada(motivo) {
  const s = await leerSesion();
  if (s) await guardarSesion({ ...s, bloqueada: true, motivo });
}
