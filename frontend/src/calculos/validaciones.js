// Reglas de validación V-xx (Apéndice J). Las mismas del servidor (backend/app/domain/validaciones.py).
// Cada función devuelve null si el dato es válido o un objeto {c, m} con el código y el mensaje.
import { MENSAJES } from "../datos/mensajes.js";
import { decimales, parseDec, parseEnt, parseFecha, hoyISO, unAnioDespues } from "./formato.js";

/** Mensaje de una regla con sus datos: N (número), HH:MM (hora) y el rango de distancias del cultivo. */
export const msg = (c, x = {}) => MENSAJES[c].replace("N", x.n ?? "N").replace("HH:MM", x.t ?? "HH:MM").replace("(mín.–máx. m)", x.r ?? "(mín.–máx. m)");
/** Error de una regla: {c: código, m: mensaje}. */
export const E = (c, x = {}) => ({ c, m: msg(c, x) });

const BASURA = ["0", "00", "000", "123", "1234", "12345", "test", "prueba", "asdf", "xxx", "null", "undefined", "nada", "ninguno"];
const TECLADO = ["qwert", "werty", "asdfg", "sdfgh", "zxcvb", "xcvbn", "12345", "23456", "34567", "abcde", "bcdef"];
const LET = "A-Za-zÁÉÍÓÚÜÑáéíóúüñ";
const SIMB = "!@#$%^&*()_+\\-=\\[\\]{}|;:,.<>?";
export const CATEGORIAS = ["semillas", "abonos", "agroquimicos", "herramientas", "transporte", "otros"];
export const NOMBRE_CATEGORIA = { semillas: "Semillas", abonos: "Abonos", agroquimicos: "Agroquímicos", herramientas: "Herramientas", transporte: "Transporte", otros: "Otros" };

/** Detecta un mismo carácter 4 o más veces seguidas (aaaa, 1111). */
const repetido = (s) => /(.)\1{3,}/i.test(s);
/** Detecta textos sin sentido: palabras de relleno o secuencias del teclado (qwert, 12345). */
const basura = (s) => { const l = s.toLowerCase(); return BASURA.includes(l) || TECLADO.some((k) => l.includes(k)); };
/** Comprueba un nombre de persona o de lugar: largo permitido, empieza con letra, solo letras, espacios, punto y guion
 *  (y coma si se permite), sin caracteres repetidos ni texto basura. */
function nombreOK(s, min, max, coma) {
  s = (s || "").trim();
  if (s.length < min || s.length > max) return false;
  const re = new RegExp("^[" + LET + "][" + LET + " .\\-" + (coma ? "," : "") + "]*$");
  return re.test(s) && !repetido(s) && !basura(s);
}
/** Nombre completo de 2 a 60 caracteres (V-01). */
export const vNombre = (s) => (nombreOK(s, 2, 60, false) ? null : E("V-01"));
/** Municipio o vereda de 3 a 60 caracteres; admite coma (V-02). */
export const vUbicacion = (s) => (nombreOK(s, 3, 60, true) ? null : E("V-02"));
/** Nombre de una finca de 2 a 60 caracteres (V-22). */
export const vLugar = (s) => (nombreOK(s, 2, 60, false) ? null : E("V-22"));
/** Correo con formato válido y de hasta 254 caracteres (V-03). */
export function vCorreo(s) {
  s = (s || "").trim();
  const ok = s.length <= 254 && /^[A-Za-z0-9!#$%&'*+/=?^_`{|}~-]+(\.[A-Za-z0-9!#$%&'*+/=?^_`{|}~-]+)*@[A-Za-z0-9]([A-Za-z0-9-]{0,61}[A-Za-z0-9])?(\.[A-Za-z0-9]([A-Za-z0-9-]{0,61}[A-Za-z0-9])?)+$/.test(s) && !basura(s.split("@")[0]);
  return ok ? null : E("V-03");
}
/** Detecta 5 caracteres seguidos en orden (abcde, 12345) o al revés; hacen débil una clave. */
function secuencia(s) {
  const l = s.toLowerCase();
  let up = 1, dn = 1;
  for (let i = 1; i < l.length; i++) {
    const d = l.charCodeAt(i) - l.charCodeAt(i - 1);
    up = d === 1 ? up + 1 : 1;
    dn = d === -1 ? dn + 1 : 1;
    if (up >= 5 || dn >= 5) return true;
  }
  return false;
}
/** La clave debe tener de 10 a 64 caracteres y solo letras sin tilde, números y los símbolos permitidos. */
const formaInvalida = (p) => p.length < 10 || p.length > 64 || !new RegExp("^[A-Za-z0-9" + SIMB + "]+$").test(p);
/** La clave debe tener al menos una mayúscula, una minúscula, un número y un símbolo. */
const faltaTipoDeCaracter = (p) => !/[A-Z]/.test(p) || !/[a-z]/.test(p) || !/\d/.test(p) || !new RegExp("[" + SIMB + "]").test(p);
/** La clave no puede contener la parte del correo antes de la arroba ni palabras del nombre (de 4 letras o más). */
function contieneDatosPersonales(p, correo, nombre) {
  const minus = p.toLowerCase();
  const loc = (correo || "").split("@")[0].toLowerCase();
  if (loc.length >= 4 && minus.includes(loc)) return true;
  return (nombre || "").toLowerCase().split(/\s+/).some((t) => t.length >= 4 && minus.includes(t));
}
/** Clave segura (V-07): forma, tipos de carácter, sin repeticiones, sin secuencias y sin datos personales. */
export function vClave(p, correo = "", nombre = "") {
  p = p || "";
  if (formaInvalida(p) || faltaTipoDeCaracter(p)) return E("V-07");
  if (repetido(p) || secuencia(p) || contieneDatosPersonales(p, correo, nombre)) return E("V-07");
  return null;
}
/** Observaciones opcionales de hasta 150 caracteres con letras, números y puntuación básica (V-38). */
export const vObservaciones = (s) => {
  s = (s || "").trim();
  return s.length > 150 || (s && !new RegExp("^[" + LET + "0-9 .,\\-]+$").test(s)) ? E("V-38") : null;
};
/** Código de verificación de exactamente 6 dígitos (V-09). */
export const vCodigoOtp = (s) => (/^\d{6}$/.test((s || "").trim()) ? null : E("V-09"));

// ---- números escritos por la persona (texto)
export function vAreaBruta(s) { const v = parseDec(s); return v === null || decimales(s) > 4 || v < 0.0001 || v > 10000 ? E("V-24") : null; }
/** Pendiente de 0 a 100 % con hasta 2 decimales (V-25). */
export function vPendiente(s) { const v = parseDec(s); return v === null || decimales(s) > 2 || v > 100 ? E("V-25") : null; }
/** Distancia de siembra de 0,01 a 10 m con hasta 2 decimales (V-33). */
export function vDistancia(s) { const v = parseDec(s); return v === null || decimales(s) > 2 || v < 0.01 || v > 10 ? E("V-33") : null; }
/** Valor del gasto: solo números enteros (V-36), de $1 a $50.000.000 (V-35). */
export function vValorGasto(s) { const v = parseEnt(s); if (v === null) return E("V-36"); return v < 1 || v > 50000000 ? E("V-35") : null; }
/** Valor del jornal: entero de $1 a $50.000.000 (V-40). */
export function vValorJornal(s) { const v = parseEnt(s); return v === null || v < 1 || v > 50000000 ? E("V-40") : null; }
/** Número de jornales: de 0,5 a 999 en pasos de medio jornal (V-39). */
export function vJornales(s) { const v = parseDec(s); return v === null || decimales(s) > 1 || v < 0.5 || v > 999 || Math.abs(v * 2 - Math.round(v * 2)) > 1e-9 ? E("V-39") : null; }
/** Cantidad vendida: de 0,1 a 10.000 con hasta 4 decimales (V-41). */
export function vCantidad(s) { const v = parseDec(s); return v === null || decimales(s) > 4 || v < 0.1 || v > 10000 ? E("V-41") : null; }
/** Precio unitario: entero de $1 a $50.000.000 (V-42). */
export function vPrecio(s) { const v = parseEnt(s); return v === null || v < 1 || v > 50000000 ? E("V-42") : null; }

/** V-49: vigencia en años, entero de 1 a 50; el campo es opcional (vacío es válido). */
export function vVigencia(s) {
  const t = (s ?? "").toString().trim();
  if (t === "") return null;
  return /^\d{1,2}$/.test(t) && Number(t) >= 1 && Number(t) <= 50 ? null : E("V-49");
}

// ---- fechas elegidas en el calendario (AAAA-MM-DD)
export function vSiembra(s) {
  const f = parseFecha(s);
  if (!f) return { error: E("V-28") };
  const hoy = hoyISO();
  return f < "2020-01-01" || f > unAnioDespues(hoy) ? { error: E("V-48") } : { iso: f };
}
/** Fecha de cierre del ciclo: válida (V-28) y entre la siembra y hoy (V-29). */
export function vCierre(s, siembra) {
  const f = parseFecha(s);
  if (!f) return { error: E("V-28") };
  return f < siembra || f > hoyISO() ? { error: E("V-29") } : { iso: f };
}
/** Fecha de un gasto, jornal o ingreso: válida (V-28) y entre la siembra del ciclo y hoy (V-47). */
export function vFechaRegistro(s, siembra) {
  const f = parseFecha(s);
  if (!f) return { error: E("V-28") };
  return f < siembra || f > hoyISO() ? { error: E("V-47") } : { iso: f };
}
