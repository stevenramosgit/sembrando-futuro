// Formato colombiano (miles con punto, decimales con coma) y fechas. "Hoy" es la fecha de Colombia (UTC−5, sin horario de verano).
export const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
/** Completa con cero a la izquierda: 5 → "05". */
export const pad = (n) => String(n).padStart(2, "0");
/** Pone el punto de miles: 1234567 → "1.234.567". */
const grp = (s) => s.replace(/\B(?=(\d{3})+(?!\d))/g, ".");

/** Número en formato colombiano con d decimales: miles con punto y decimales con coma (4444.45 → "4.444,45"). */
export function fmt(n, d = 0) {
  const neg = n < 0 && Number(Math.abs(n).toFixed(d)) !== 0;
  const [i, f] = Math.abs(n).toFixed(d).split(".");
  return (neg ? "-" : "") + grp(i) + (f ? "," + f : "");
}
/** Valor en pesos colombianos sin decimales: 2220000 → "$ 2.220.000". */
export const money = (n) => "$ " + fmt(n, 0);
/** Redondeo de la mitad hacia arriba (RF-18): 0,5 sube. */
export const rhu = (x) => (x < 0 ? -rhu(-x) : Math.floor(Math.round(x * 1e6) / 1e6 + 0.5));
/** Muestra un decimal con coma sin cambiar sus cifras: 2.5 → "2,5". */
export const dn = (x) => String(x).replace(".", ",");
/** Redondeo hacia arriba (techo) con a lo sumo d decimales: 4.444,441 pasa a 4.444,45. El toFixed(6) absorbe el ruido de los decimales binarios. */
export const techo = (x, d = 2) => { const f = 10 ** d; return Math.ceil(Number((x * f).toFixed(6))) / f; };
/** Área en hectáreas para mostrar: hacia arriba y con dos decimales. */
export const ha2 = (x) => fmt(techo(x, 2), 2) + " ha";

const COLOMBIA_MS = -5 * 3600e3;
/** Momento actual en milisegundos (las pruebas lo reemplazan para simular otra hora). */
export const ahoraMs = () => Date.now();
/** Fecha de hoy en Colombia como AAAA-MM-DD. */
export function hoyISO(ms = ahoraMs()) {
  const d = new Date(ms + COLOMBIA_MS);
  return `${d.getUTCFullYear()}-${pad(d.getUTCMonth() + 1)}-${pad(d.getUTCDate())}`;
}
/** Suma años a una fecha AAAA-MM-DD; el 29 de febrero pasa al 28 si el año final no es bisiesto. */
export const sumarAnios = (iso, n) => {
  const [y, m, d] = iso.split("-").map(Number);
  const f = new Date(Date.UTC(y + n, m - 1, d));
  if (f.getUTCMonth() !== m - 1) return `${y + n}-${pad(m)}-28`; // 29 de febrero
  return `${y + n}-${pad(m)}-${pad(d)}`;
};
/** La misma fecha un año después (límite de la fecha de siembra, V-48). */
export const unAnioDespues = (iso) => sumarAnios(iso, 1);
/** Suma meses de calendario; si el día no existe en el mes final (31 de abril) usa el último día de ese mes. */
export const sumarMeses = (iso, n) => {
  const [y, m, d] = iso.split("-").map(Number);
  const i = y * 12 + (m - 1) + n, ny = Math.floor(i / 12), nm = (i % 12) + 1;
  const ultimo = new Date(Date.UTC(ny, nm, 0)).getUTCDate();
  return `${ny}-${pad(nm)}-${pad(Math.min(d, ultimo))}`;
};
const MESES = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre"];
/** Nombre del mes en español a partir de su número (1 = enero). */
export const nombreMes = (n) => MESES[n - 1];
/** «noviembre de 2027» a partir de AAAA-MM-DD. */
export const mesAnio = (iso) => { const [y, m] = iso.split("-").map(Number); return `${MESES[m - 1]} de ${y}`; };
/** [4,5,6,10,11,12] → «abril a junio y octubre a diciembre». */
export function temporadas(meses) {
  const orden = [...meses].sort((a, b) => a - b), tramos = [];
  for (const m of orden) { const t = tramos[tramos.length - 1]; if (t && m === t[1] + 1) t[1] = m; else tramos.push([m, m]); }
  return tramos.map(([a, b]) => (a === b ? MESES[a - 1] : b === a + 1 ? `${MESES[a - 1]} y ${MESES[b - 1]}` : `${MESES[a - 1]} a ${MESES[b - 1]}`)).join(" y ");
};
/** Fecha AAAA-MM-DD en el formato colombiano día/mes/año. */
export const isoAEs = (iso) => (iso ? iso.split("-").reverse().join("/") : "");
/** Hora de Colombia (HH:MM) de un momento en milisegundos. */
export const horaCO = (ms) => { const d = new Date(ms + COLOMBIA_MS); return `${pad(d.getUTCHours())}:${pad(d.getUTCMinutes())}`; };
/** AAAA-MM-DDTHH:MM:SS.mmmZ en UTC. */
export const ahoraISOms = () => new Date().toISOString();

/** Fecha del calendario del navegador (AAAA-MM-DD) o, si el navegador no ofrece calendario, día/mes/año: devuelve AAAA-MM-DD si existe; si no, null (V-28). */
export function parseFecha(s) {
  const t = (s || "").trim(), m = /^(\d{4})-(\d{2})-(\d{2})$/.exec(t);
  if (!m) return parseFechaEs(t);
  const y = +m[1], mo = +m[2], d = +m[3], f = new Date(Date.UTC(y, mo - 1, d));
  return f.getUTCFullYear() === y && f.getUTCMonth() === mo - 1 && f.getUTCDate() === d && y >= 1900 && y <= 2200 ? t : null;
}
/** Lee día/mes/año y devuelve AAAA-MM-DD si la fecha existe en el calendario; si no, null (V-28). */
export function parseFechaEs(s) {
  const m = /^(\d{1,2})\/(\d{1,2})\/(\d{4})$/.exec((s || "").trim());
  if (!m) return null;
  const d = +m[1], mo = +m[2], y = +m[3];
  const f = new Date(Date.UTC(y, mo - 1, d));
  if (f.getUTCFullYear() !== y || f.getUTCMonth() !== mo - 1 || f.getUTCDate() !== d || y < 1900 || y > 2200) return null;
  return `${y}-${pad(mo)}-${pad(d)}`;
}
/** Lee un número escrito por la persona, con punto o coma decimal; devuelve null si no es un número válido. */
export function parseDec(s) {
  s = (s || "").trim();
  if (!/^\d+([.,]\d+)?$/.test(s)) return null;
  return parseFloat(s.replace(",", "."));
}
/** Lee un número entero escrito por la persona (solo dígitos); devuelve null si no lo es. */
export function parseEnt(s) {
  s = (s || "").trim();
  return /^\d+$/.test(s) ? parseInt(s, 10) : null;
}
/** Número de decimales escritos (para las reglas de máximo de decimales). */
export const decimales = (s) => { const m = /[.,](\d+)$/.exec((s || "").trim()); return m ? m[1].length : 0; };
