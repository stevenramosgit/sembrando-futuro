// Piezas comunes de la interfaz: campos, botones, avisos, navegación y ejecución de acciones.
import { esc } from "./calculos/formato.js";
import { E, msg } from "./calculos/validaciones.js";
import { S } from "./estado.js";

let dibujar = () => {};
export const alDibujar = (fn) => { dibujar = fn; };
export const render = () => dibujar();

export const A = {};   // acciones: se invocan con data-act="nombre:argumento"
export const P = {};   // pantallas: cada una devuelve {t, h, nav?, back?}

export const val = (id) => S.f[id] ?? "";
export const MSG_SIN_RED = "Sin conexión. Esta acción necesita internet; inténtelo de nuevo cuando vuelva la conexión.";

const selectHtml = (id, o, v) => `<select id="${id}" data-f="${id}"${o.rerender ? " data-rr" : ""}>${o.opts.map((x) => `<option value="${esc(x[0])}"${String(v) === String(x[0]) ? " selected" : ""}>${esc(x[1])}</option>`).join("")}</select>`;

const inputHtml = (id, o, v, e) => `<input id="${id}" data-f="${id}" type="${o.type || "text"}" value="${esc(v)}" placeholder="${esc(o.ph || "")}" autocomplete="${o.ac || "off"}"${o.im ? ` inputmode="${o.im}"` : ""}${o.max ? ` maxlength="${o.max}"` : ""}${e ? ` aria-invalid="true" aria-describedby="e-${id}"` : ""}>`;

function mensajeDeCampo(id, o, e) {
  if (e) return `<div class="err" id="e-${id}" role="alert"><span>${esc(e.m)} <span class="muted">(${e.c})</span></span></div>`;
  return o.hint ? `<div class="hint">${o.hint}</div>` : "";
}

export function fld(id, label, o = {}) {
  const e = S.e[id];
  const v = o.value ?? val(id);
  const ctl = o.opts ? selectHtml(id, o, v) : inputHtml(id, o, v, e);
  return `<div class="field${e ? " bad" : ""}"><label for="${id}">${label}</label>${ctl}${mensajeDeCampo(id, o, e)}</div>`;
}
export const btn = (act, txt, cls = "", d = "") => `<button class="btn ${cls}" data-act="${act}" ${d}>${txt}</button>`;
export const banner = (k, m, c) => `<div class="banner ${k}" role="alert">${esc(m)}${c ? ` <span class="muted">(${c})</span>` : ""}</div>`;
export const kv = (a, b) => `<div class="kv"><span>${a}</span><b>${b}</b></div>`;
/** Utilidad neta; si es negativa se llama «Pérdida» y va en rojo (RF-28): el color no es lo único que la distingue. */
export const kvUtilidad = (u, texto) => (u < 0 ? `<div class="kv perdida"><span>Pérdida</span><b>${texto}</b></div>` : kv("Utilidad neta", texto));
export const topBanner = () => (S.banner ? banner(S.banner.k, S.banner.m, S.banner.c) : "");
export const chk = (id, label) => `<div class="chk"><input type="checkbox" id="${id}" data-f="${id}"${S.f[id] ? " checked" : ""}><label for="${id}">${label}</label></div>`;
export const err1 = (id) => (S.e[id] ? `<div class="err" role="alert"><span>${esc(S.e[id].m)} <span class="muted">(${S.e[id].c})</span></span></div>` : "");
export const seg = (id, opts) => `<div class="seg" role="group">${opts.map((o) => `<button type="button" data-act="seg" data-id="${id}" data-v="${o[0]}" aria-pressed="${val(id) === o[0]}">${o[1]}</button>`).join("")}</div>`;

// ---------------------------------------------------------------- avisos
export const okB = (m) => { S.banner = { k: "ok", m }; };
export const badB = (c, x) => { S.banner = { k: "bad", m: msg(c, x), c }; };
export const warnB = (c, x) => { S.banner = { k: "warn", m: msg(c, x), c }; };
export const fail = (id, c, x) => { S.e[id] = E(c, x); };

// ---------------------------------------------------------------- navegación
export const AUTH = new Set(["p09", "p10", "p11", "p12", "p13", "p14", "p15", "p18", "p19", "p20", "p21", "p22", "p23", "p24", "p25", "p26", "p28"]);
export function entrar(pantalla, pre, defecto) {
  S.f = Object.assign({}, defecto ? defecto() : {}, pre || {});
  S.e = {};
  S.banner = null;
  S.ctx.out = false;  // las preguntas de confirmación (cerrar sesión, cerrar ciclo) no sobreviven a un cambio de pantalla
  S.ctx.ask = false;
}
export const DEFECTOS = {};
export function go(p, pre) {
  if (AUTH.has(p) && !S.usuario) p = "p07";
  S.pila.push(S.pantalla);
  S.pantalla = p;
  entrar(p, pre, DEFECTOS[p]);
  render();
}
export function raiz(p, pre) {
  S.pila = [];
  S.pantalla = p;
  entrar(p, pre, DEFECTOS[p]);
  render();
}
export function volver() {
  S.pantalla = S.pila.pop() || (S.usuario ? "p10" : "p01");
  S.e = {};
  S.banner = null;
  render();
}

/** Ejecuta una acción mostrando «Procesando…» y evitando doble pulsación. */
export async function ejecutar(el, fn) {
  if (S.ocupado) return;
  S.ocupado = true;
  if (el) { el.disabled = true; el.textContent = "Procesando…"; }
  S.e = {};
  S.banner = null;
  try { await fn(); } catch (x) { console.error(x); S.banner = { k: "bad", m: "Ocurrió un error inesperado. Intente de nuevo." }; }
  S.ocupado = false;
  render();
}
