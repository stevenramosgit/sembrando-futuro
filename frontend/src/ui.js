// Piezas comunes de la interfaz: campos, botones, avisos, navegación y ejecución de acciones.
import { esc } from "./calculos/formato.js";
import { E, msg } from "./calculos/validaciones.js";
import { S } from "./estado.js";

let dibujar = () => {};
/** Registra la función que dibuja la pantalla (la define app.js). */
export const alDibujar = (fn) => { dibujar = fn; };
/** Vuelve a dibujar la pantalla actual con el estado actual. */
export const render = () => dibujar();

export const A = {};   // acciones: se invocan con data-act="nombre:argumento"
export const P = {};   // pantallas: cada una devuelve {t, h, nav?, back?}

/** Valor actual de un campo del formulario. */
export const val = (id) => S.f[id] ?? "";
export const MSG_SIN_RED = "Sin conexión. Esta acción necesita internet; inténtelo de nuevo cuando vuelva la conexión.";

/** Lista desplegable de un campo, marcada como inválida si tiene error. */
const selectHtml = (id, o, v, e) => `<select class="form-select${e ? " is-invalid" : ""}" id="${id}" data-f="${id}"${o.rerender ? " data-rr" : ""}${e ? ' aria-invalid="true"' : ""}>${o.opts.map((x) => `<option value="${esc(x[0])}"${String(v) === String(x[0]) ? " selected" : ""}>${esc(x[1])}</option>`).join("")}</select>`;

/** Caja de texto de un campo, con su tipo de teclado y marcada como inválida si tiene error. */
const inputHtml = (id, o, v, e) => `<input class="form-control${e ? " is-invalid" : ""}" id="${id}" data-f="${id}" type="${o.type || "text"}" value="${esc(v)}" placeholder="${esc(o.ph || "")}" autocomplete="${o.ac || "off"}"${o.im ? ` inputmode="${o.im}"` : ""}${o.max ? ` maxlength="${o.max}"` : ""}${o.min_f ? ` min="${o.min_f}"` : ""}${o.max_f ? ` max="${o.max_f}"` : ""}${e ? ` aria-invalid="true" aria-describedby="e-${id}"` : ""}>`;

/** Debajo del campo: el error con su código (por ejemplo V-24) o, si no hay error, la ayuda. */
function mensajeDeCampo(id, o, e) {
  if (e) return `<div class="err" id="e-${id}" role="alert"><span>${esc(e.m)} <span class="muted">(${e.c})</span></span></div>`;
  return o.hint ? `<div class="hint">${o.hint}</div>` : "";
}

/** Campo completo: etiqueta, control y mensaje. Es la pieza con la que se arman todos los formularios. */
export function fld(id, label, o = {}) {
  const e = S.e[id];
  const v = o.value ?? val(id);
  const ctl = o.opts ? selectHtml(id, o, v, e) : inputHtml(id, o, v, e);
  return `<div class="field${e ? " bad" : ""}"><label class="form-label" for="${id}">${label}</label>${ctl}${mensajeDeCampo(id, o, e)}</div>`;
}
/** Campo de fecha con el calendario del teléfono (type=date): el usuario elige el día en vez de escribirlo. Se guarda como AAAA-MM-DD. */
export const fldFecha = (id, label, o = {}) => fld(id, label, { type: "date", ...o });
const ESTILO_BTN = { "": "btn-primario", sec: "btn-contorno", danger: "btn-peligro" };
/** Botón que ejecuta una acción (data-act); estilos: principal, de contorno o de peligro. */
export const btn = (act, txt, cls = "", d = "") => `<button class="btn ${ESTILO_BTN[cls] || ESTILO_BTN[""]} w-100 mb-2" data-act="${act}" ${d}>${txt}</button>`;
const ESTILO_ALERTA = { ok: "alert-success", warn: "alert-warning", bad: "alert-danger" };
/** Aviso de color (éxito, advertencia o error) con su código si lo tiene. */
export const banner = (k, m, c) => `<div class="alert ${ESTILO_ALERTA[k] || "alert-secondary"}" role="alert">${esc(m)}${c ? ` <span class="muted">(${c})</span>` : ""}</div>`;
/** Aviso neutro con HTML ya armado (sin código de error). */
export const aviso = (html) => `<div class="alert alert-secondary" role="status">${html}</div>`;
/** Fila de dos columnas «etiqueta: valor» de las tarjetas de resultados. */
export const kv = (a, b) => `<div class="kv"><span>${a}</span><b>${b}</b></div>`;
/** Utilidad neta; si es negativa se llama «Pérdida» y va en rojo (RF-28): el color no es lo único que la distingue. */
export const kvUtilidad = (u, texto) => (u < 0 ? `<div class="kv perdida"><span>Pérdida</span><b>${texto}</b></div>` : kv("Utilidad neta", texto));
/** Aviso general de la pantalla, si hay uno. */
export const topBanner = () => (S.banner ? banner(S.banner.k, S.banner.m, S.banner.c) : "");
/** Casilla de verificación (por ejemplo, la autorización de datos de la Ley 1581). */
export const chk = (id, label) => `<div class="form-check"><input class="form-check-input" type="checkbox" id="${id}" data-f="${id}"${S.f[id] ? " checked" : ""}><label class="form-check-label" for="${id}">${label}</label></div>`;
/** Error suelto de un campo que no es caja de texto (por ejemplo, la casilla de autorización). */
export const err1 = (id) => (S.e[id] ? `<div class="err" role="alert"><span>${esc(S.e[id].m)} <span class="muted">(${S.e[id].c})</span></span></div>` : "");
/** Botones de selección única (por ejemplo, el marco de siembra). */
export const seg = (id, opts) => `<div class="seg" role="group">${opts.map((o) => `<button type="button" data-act="seg" data-id="${id}" data-v="${o[0]}" aria-pressed="${val(id) === o[0]}">${o[1]}</button>`).join("")}</div>`;

// ---------------------------------------------------------------- avisos
export const okB = (m) => { S.banner = { k: "ok", m }; };
/** Muestra un aviso de error con su código. */
export const badB = (c, x) => { S.banner = { k: "bad", m: msg(c, x), c }; };
/** Muestra una advertencia con su código. */
export const warnB = (c, x) => { S.banner = { k: "warn", m: msg(c, x), c }; };
/** Marca el error de un campo. */
export const fail = (id, c, x) => { S.e[id] = E(c, x); };

// ---------------------------------------------------------------- navegación
export const AUTH = new Set(["p09", "p10", "p11", "p12", "p13", "p14", "p15", "p18", "p19", "p20", "p21", "p22", "p23", "p24", "p25", "p26", "p28"]);
/** Prepara una pantalla nueva: campos con sus valores iniciales y sin errores ni avisos de la pantalla anterior. */
export function entrar(pantalla, pre, defecto) {
  S.f = Object.assign({}, defecto ? defecto() : {}, pre || {});
  S.e = {};
  S.banner = null;
  S.ctx.out = false;  // las preguntas de confirmación (cerrar sesión, cerrar ciclo) no sobreviven a un cambio de pantalla
  S.ctx.ask = false;
}
export const DEFECTOS = {};
/** Abre una pantalla y guarda la anterior para el botón Volver. Las pantallas internas sin sesión llevan a Ingresar. */
export function go(p, pre) {
  if (AUTH.has(p) && !S.usuario) p = "p07";
  S.pila.push(S.pantalla);
  S.pantalla = p;
  entrar(p, pre, DEFECTOS[p]);
  render();
}
/** Abre una pantalla principal (pestañas inferiores) y olvida el historial de Volver. */
export function raiz(p, pre) {
  S.pila = [];
  S.pantalla = p;
  entrar(p, pre, DEFECTOS[p]);
  render();
}
/** Regresa a la pantalla anterior. */
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
