// Reglas de validación V-xx (Apéndice J). Las mismas del servidor (backend/app/domain/validaciones.py).
// Cada función devuelve null si el dato es válido o un objeto {c, m} con el código y el mensaje.
import { MENSAJES } from "../datos/mensajes.js";
import { decimales, parseDec, parseEnt, parseFechaEs, hoyISO, unAnioDespues } from "./formato.js";

export const msg = (c, x = {}) => MENSAJES[c].replace("N", x.n ?? "N").replace("HH:MM", x.t ?? "HH:MM").replace("(mín.–máx. m)", x.r ?? "(mín.–máx. m)");
export const E = (c, x = {}) => ({ c, m: msg(c, x) });

const BASURA = ["0", "00", "000", "123", "1234", "12345", "test", "prueba", "asdf", "xxx", "null", "undefined", "nada", "ninguno"];
const TECLADO = ["qwert", "werty", "asdfg", "sdfgh", "zxcvb", "xcvbn", "12345", "23456", "34567", "abcde", "bcdef"];
const LET = "A-Za-zÁÉÍÓÚÜÑáéíóúüñ";
const SIMB = "!@#$%^&*()_+\\-=\\[\\]{}|;:,.<>?";
export const CATEGORIAS = ["semillas", "abonos", "agroquimicos", "herramientas", "transporte", "otros"];
export const NOMBRE_CATEGORIA = { semillas: "Semillas", abonos: "Abonos", agroquimicos: "Agroquímicos", herramientas: "Herramientas", transporte: "Transporte", otros: "Otros" };

const repetido = (s) => /(.)\1{3,}/i.test(s);
const basura = (s) => { const l = s.toLowerCase(); return BASURA.includes(l) || TECLADO.some((k) => l.includes(k)); };
function nombreOK(s, min, max, coma) {
  s = (s || "").trim();
  if (s.length < min || s.length > max) return false;
  const re = new RegExp("^[" + LET + "][" + LET + " .\\-" + (coma ? "," : "") + "]*$");
  return re.test(s) && !repetido(s) && !basura(s);
}
export const vNombre = (s) => (nombreOK(s, 2, 60, false) ? null : E("V-01"));
export const vUbicacion = (s) => (nombreOK(s, 3, 60, true) ? null : E("V-02"));
export const vLugar = (s) => (nombreOK(s, 2, 60, false) ? null : E("V-22"));
export function vCorreo(s) {
  s = (s || "").trim();
  const ok = s.length <= 254 && /^[A-Za-z0-9!#$%&'*+/=?^_`{|}~-]+(\.[A-Za-z0-9!#$%&'*+/=?^_`{|}~-]+)*@[A-Za-z0-9]([A-Za-z0-9-]{0,61}[A-Za-z0-9])?(\.[A-Za-z0-9]([A-Za-z0-9-]{0,61}[A-Za-z0-9])?)+$/.test(s) && !basura(s.split("@")[0]);
  return ok ? null : E("V-03");
}
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
const formaInvalida = (p) => p.length < 10 || p.length > 64 || !new RegExp("^[A-Za-z0-9" + SIMB + "]+$").test(p);
const faltaTipoDeCaracter = (p) => !/[A-Z]/.test(p) || !/[a-z]/.test(p) || !/\d/.test(p) || !new RegExp("[" + SIMB + "]").test(p);
function contieneDatosPersonales(p, correo, nombre) {
  const minus = p.toLowerCase();
  const loc = (correo || "").split("@")[0].toLowerCase();
  if (loc.length >= 4 && minus.includes(loc)) return true;
  return (nombre || "").toLowerCase().split(/\s+/).some((t) => t.length >= 4 && minus.includes(t));
}
export function vClave(p, correo = "", nombre = "") {
  p = p || "";
  if (formaInvalida(p) || faltaTipoDeCaracter(p)) return E("V-07");
  if (repetido(p) || secuencia(p) || contieneDatosPersonales(p, correo, nombre)) return E("V-07");
  return null;
}
export const vObservaciones = (s) => {
  s = (s || "").trim();
  return s.length > 150 || (s && !new RegExp("^[" + LET + "0-9 .,\\-]+$").test(s)) ? E("V-38") : null;
};
export const vCodigoOtp = (s) => (/^\d{6}$/.test((s || "").trim()) ? null : E("V-09"));

// ---- números escritos por la persona (texto)
export function vAreaBruta(s) { const v = parseDec(s); return v === null || decimales(s) > 4 || v < 0.0001 || v > 10000 ? E("V-24") : null; }
export function vPendiente(s) { const v = parseDec(s); return v === null || decimales(s) > 2 || v > 100 ? E("V-25") : null; }
export function vDistancia(s) { const v = parseDec(s); return v === null || decimales(s) > 2 || v < 0.01 || v > 10 ? E("V-33") : null; }
export function vValorGasto(s) { const v = parseEnt(s); if (v === null) return E("V-36"); return v < 1 || v > 50000000 ? E("V-35") : null; }
export function vValorJornal(s) { const v = parseEnt(s); return v === null || v < 1 || v > 50000000 ? E("V-40") : null; }
export function vJornales(s) { const v = parseDec(s); return v === null || decimales(s) > 1 || v < 0.5 || v > 999 || Math.abs(v * 2 - Math.round(v * 2)) > 1e-9 ? E("V-39") : null; }
export function vCantidad(s) { const v = parseDec(s); return v === null || decimales(s) > 4 || v < 0.1 || v > 10000 ? E("V-41") : null; }
export function vPrecio(s) { const v = parseEnt(s); return v === null || v < 1 || v > 50000000 ? E("V-42") : null; }

/** V-49: vigencia en años, entero de 1 a 50; el campo es opcional (vacío es válido). */
export function vVigencia(s) {
  const t = (s ?? "").toString().trim();
  if (t === "") return null;
  return /^\d{1,2}$/.test(t) && Number(t) >= 1 && Number(t) <= 50 ? null : E("V-49");
}

// ---- fechas escritas en día/mes/año
export function vSiembra(s) {
  const f = parseFechaEs(s);
  if (!f) return { error: E("V-28") };
  const hoy = hoyISO();
  return f < "2020-01-01" || f > unAnioDespues(hoy) ? { error: E("V-48") } : { iso: f };
}
export function vCierre(s, siembra) {
  const f = parseFechaEs(s);
  if (!f) return { error: E("V-28") };
  return f < siembra || f > hoyISO() ? { error: E("V-29") } : { iso: f };
}
export function vFechaRegistro(s, siembra) {
  const f = parseFechaEs(s);
  if (!f) return { error: E("V-28") };
  return f < siembra || f > hoyISO() ? { error: E("V-47") } : { iso: f };
}
