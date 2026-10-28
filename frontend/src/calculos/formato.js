// Formato colombiano (miles con punto, decimales con coma) y fechas. "Hoy" es la fecha de Colombia (UTC−5, sin horario de verano).
export const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
export const pad = (n) => String(n).padStart(2, "0");
const grp = (s) => s.replace(/\B(?=(\d{3})+(?!\d))/g, ".");

export function fmt(n, d = 0) {
  const neg = n < 0 && Number(Math.abs(n).toFixed(d)) !== 0;
  const [i, f] = Math.abs(n).toFixed(d).split(".");
  return (neg ? "-" : "") + grp(i) + (f ? "," + f : "");
}
export const money = (n) => "$ " + fmt(n, 0);
/** Redondeo de la mitad hacia arriba (RF-18): 0,5 sube. */
export const rhu = (x) => (x < 0 ? -rhu(-x) : Math.floor(Math.round(x * 1e6) / 1e6 + 0.5));
export const dn = (x) => String(x).replace(".", ",");

const COLOMBIA_MS = -5 * 3600e3;
export const ahoraMs = () => Date.now();
/** Fecha de hoy en Colombia como AAAA-MM-DD. */
export function hoyISO(ms = ahoraMs()) {
  const d = new Date(ms + COLOMBIA_MS);
  return `${d.getUTCFullYear()}-${pad(d.getUTCMonth() + 1)}-${pad(d.getUTCDate())}`;
}
export const sumarAnios = (iso, n) => {
  const [y, m, d] = iso.split("-").map(Number);
  const f = new Date(Date.UTC(y + n, m - 1, d));
  if (f.getUTCMonth() !== m - 1) return `${y + n}-${pad(m)}-28`; // 29 de febrero
  return `${y + n}-${pad(m)}-${pad(d)}`;
};
export const unAnioDespues = (iso) => sumarAnios(iso, 1);
export const isoAEs = (iso) => (iso ? iso.split("-").reverse().join("/") : "");
export const horaCO = (ms) => { const d = new Date(ms + COLOMBIA_MS); return `${pad(d.getUTCHours())}:${pad(d.getUTCMinutes())}`; };
/** AAAA-MM-DDTHH:MM:SS.mmmZ en UTC. */
export const ahoraISOms = () => new Date().toISOString();

/** Lee día/mes/año y devuelve AAAA-MM-DD si la fecha existe en el calendario; si no, null (V-28). */
export function parseFechaEs(s) {
  const m = /^(\d{1,2})\/(\d{1,2})\/(\d{4})$/.exec((s || "").trim());
  if (!m) return null;
  const d = +m[1], mo = +m[2], y = +m[3];
  const f = new Date(Date.UTC(y, mo - 1, d));
  if (f.getUTCFullYear() !== y || f.getUTCMonth() !== mo - 1 || f.getUTCDate() !== d || y < 1900 || y > 2200) return null;
  return `${y}-${pad(mo)}-${pad(d)}`;
}
export function parseDec(s) {
  s = (s || "").trim();
  if (!/^\d+([.,]\d+)?$/.test(s)) return null;
  return parseFloat(s.replace(",", "."));
}
export function parseEnt(s) {
  s = (s || "").trim();
  return /^\d+$/.test(s) ? parseInt(s, 10) : null;
}
/** Número de decimales escritos (para las reglas de máximo de decimales). */
export const decimales = (s) => { const m = /[.,](\d+)$/.exec((s || "").trim()); return m ? m[1].length : 0; };
