// Arranque de la PWA: dibuja la pantalla actual, atiende los toques y mantiene la conexión, la sesión y la sincronización.
import { esc, fmt, money, parseDec, parseEnt, ahoraMs } from "./calculos/formato.js";
import { msg } from "./calculos/validaciones.js";
import { costoJornal, totalIngreso } from "./calculos/formulas.js";
import { db, listo, meta } from "./db/db.js";
import { A, AUTH, P, alDibujar, go, raiz, render, val, volver, warnB } from "./ui.js";
import { S, alCambiarDatos, borrarSesion, cargarCatalogo, cargarDatos, leerSesion, ciclo, misFincas, pendCount, vaciarDatos } from "./estado.js";
import { configurarSync, pedirSync, sincronizar } from "./sync.js";
import "./pantallas/acceso.js";
import "./pantallas/panel.js";
import "./pantallas/fincas.js";
import "./pantallas/calculadora.js";
import "./pantallas/finanzas.js";
import { textoEspera } from "./pantallas/acceso.js";

const $ = (s) => document.querySelector(s);
const NAVS = [["p10", "Inicio"], ["p11", "Fincas"], ["p18", "Calcular"], ["p20", "Finanzas"], ["p16", "Catálogo"]];
const SUB = new Set(["reg", "otpv", "otpr", "chm", "login", "savefinca", "savecy", "savecult", "savearea", "closego", "closeyes", "calc", "savegas", "savejor", "saveinc", "saveedit", "del", "syncnow"]);

// ---------------------------------------------------------------- dibujo
const hectareasDe = (v, unidad) => (unidad === "m2" ? v / 1e4 : unidad === "plaza" ? v * 0.64 : v);

function previaArea() {
  const l = ciclo(S.ctx.cy), el = $("#prev13");
  if (!el || !l) return;
  const t = val("nosemb").trim();
  const v = t === "" ? 0 : parseDec(t);
  const ha = v === null ? null : hectareasDe(v, val("unit") || "m2");
  el.innerHTML = ha === null ? "<h3>Convertido</h3>Escriba solo números." : `<h3>Resultado</h3><div class="kv"><span>Convertido a hectáreas</span><b>${fmt(ha, 4)} ha</b></div><div class="kv"><span>Área efectiva</span><b>${ha < l.area_bruta_ha ? fmt(Math.round((l.area_bruta_ha - ha) * 1e4) / 1e4, 4) + " ha" : "—"}</b></div>`;
}

function previaJornal() {
  const n = parseDec(val("jn")), v = parseEnt(val("jv")), el = $("#prevj");
  if (el) el.innerHTML = `<h3>Cálculo automático</h3><div class="kv"><span>Costo total</span><b>${n !== null && v !== null ? money(costoJornal(n, v)) : "—"}</b></div>`;
}

function previaIngreso() {
  const q = parseDec(val("iq")), p = parseEnt(val("ip")), el = $("#previ");
  if (el) el.innerHTML = `<h3>Total del ingreso</h3><div class="kv"><span>Total</span><b>${q !== null && p !== null ? money(totalIngreso(q, p)) : "—"}</b></div>`;
}

const PREVIAS = { p13: previaArea, p22: previaJornal, p23: previaIngreso };
function vistaPrevia() {
  const dibujarPrevia = PREVIAS[S.pantalla];
  if (dibujarPrevia) dibujarPrevia();
}

function pantallaActual() {
  try { return P[S.pantalla](); } catch (x) {
    console.error(x);
    return { t: "Sembrando Futuro", h: '<div class="banner bad">Ocurrió un error inesperado. Intente de nuevo.</div>' };
  }
}

function barraSuperior(sc, hayVolver, nav) {
  const n = pendCount();
  const pastilla = `<button class="pill" data-act="go:${S.usuario ? "p25" : "p01"}" ${S.usuario ? "" : "tabindex=-1"} aria-label="Estado de conexión">${S.enLinea ? "● En línea" : "○ Sin conexión"}${n ? " · " + n : ""}</button>`;
  const cuenta = S.usuario && nav ? `<button class="pill" data-act="go:p26">Cuenta</button>` : "";
  return `<header class="appbar">${hayVolver ? `<button class="back" data-act="back" aria-label="Volver">‹</button>` : ""}<h1>${esc(sc.t)}</h1>${cuenta}${pastilla}</header>`;
}

const barraInferior = (sc, nav) => (nav
  ? `<nav class="nav" aria-label="Principal">${NAVS.map((x, i) => `<button data-act="tab:${x[0]}" ${i === sc.nav ? 'aria-current="page"' : ""}>${x[1]}</button>`).join("")}</nav>`
  : "");

const avisoHtml = () => (S.aviso
  ? `<div class="toast" id="toast" role="status"><span id="toastm">${esc(S.aviso.m)}</span>${S.aviso.muerto ? "" : `<button data-act="undo">Deshacer</button>`}</div>`
  : "");

function restaurarFoco(foco) {
  const el = foco && document.getElementById(foco);
  if (!el || !el.matches("input,select,textarea")) return;
  el.focus();
  try { el.setSelectionRange(el.value.length, el.value.length); } catch { /* selects y correos no admiten selección */ }
}

function dibujar() {
  if (!S.usuario && AUTH.has(S.pantalla)) { S.pantalla = "p01"; S.pila = []; }  // sin sesión no se dibuja ninguna pantalla interna
  const sc = pantallaActual();
  const previo = $(".content");
  const arriba = previo && previo.dataset.s === S.pantalla ? previo.scrollTop : 0;
  const hayVolver = sc.back !== 0 && S.pila.length;
  const nav = sc.nav !== undefined && S.usuario;
  const foco = document.activeElement && document.activeElement.id;
  $("#screen").innerHTML = `${barraSuperior(sc, hayVolver, nav)}<div class="content" data-s="${S.pantalla}" id="content">${sc.h}</div>${barraInferior(sc, nav)}${avisoHtml()}`;
  $("#content").scrollTop = arriba;
  restaurarFoco(foco);
  vistaPrevia();
}
alDibujar(dibujar);

// ---------------------------------------------------------------- acciones de navegación
A.back = () => volver();
A.go = (s) => go(s);
A.goroot = (s) => raiz(s);
A.tab = (s) => raiz(s === "p10" && !misFincas().length ? "p09" : s);
A.seg = (el) => { S.f[el.dataset.id] = el.dataset.v; render(); };

document.addEventListener("click", (ev) => {
  const a = ev.target.closest("[data-act]");
  if (!a) return;
  ev.preventDefault();
  if (a.disabled) return;
  const [nombre, ...args] = a.dataset.act.split(":");
  if (nombre === "go") { if (args[0] === "p15") S.ctx = { ...S.ctx, cy: S.sel.ciclo, done: false, ask: false }; return go(args[0]); }
  if (A[nombre]) A[nombre](SUB.has(nombre) || nombre === "seg" ? a : args[0], args[1]);
});
const alEscribir = (ev) => {
  const el = ev.target;
  if (!el.dataset || !el.dataset.f) return;
  S.f[el.dataset.f] = el.type === "checkbox" ? el.checked : el.value;
  if (el.dataset.f === "selFarm") { S.sel.finca = el.value; S.sel.ciclo = null; return render(); }
  if (el.dataset.f === "selCycle") { S.sel.ciclo = el.value; return render(); }
  if (el.hasAttribute("data-rr")) return render();
  vistaPrevia();
};
document.addEventListener("input", alEscribir);
document.addEventListener("change", (ev) => { if (ev.target.tagName === "SELECT" || ev.target.type === "checkbox") alEscribir(ev); });
document.addEventListener("keydown", (ev) => {
  if (ev.key === "Enter" && ev.target.tagName === "INPUT" && ev.target.type !== "checkbox") {
    const b = document.querySelector(".content .btn:not(.sec):not(.danger):not([disabled])");
    if (b) { ev.preventDefault(); b.click(); }
  }
});

// ---------------------------------------------------------------- conexión, sesión y sincronización
function sesionVencida() {
  // V-46: el token venció o fue revocado. Los datos siguen guardados en el dispositivo.
  const correo = S.usuario?.correo || "";
  S.usuario = null;
  borrarSesion();
  vaciarDatos();
  S.pantalla = "p07"; S.pila = []; S.f = { lmail: correo };
  warnB("V-46");
  render();
}
configurarSync({ terminar: () => render(), sesionVencida });
alCambiarDatos(() => pedirSync(1500));

window.addEventListener("online", () => { S.enLinea = true; render(); sincronizar().catch(() => {}); });
window.addEventListener("offline", () => { S.enLinea = false; render(); });
document.addEventListener("visibilitychange", () => { if (document.visibilityState === "visible" && S.usuario && S.enLinea) pedirSync(300); });

setInterval(() => {
  if (S.pantalla === "p04") { const el = $("#wait"); if (el) { const t = textoEspera(); if (el.textContent !== t) el.textContent = t; } }
  const t = S.aviso;
  if (t && !t.muerto && ahoraMs() > t.hasta) { t.m = msg("V-43"); t.muerto = true; render(); }
  else if (t && t.muerto && ahoraMs() > t.hasta + 3500) { S.aviso = null; render(); }
}, 1000);
setInterval(() => { if (S.usuario && S.enLinea && document.visibilityState === "visible") sincronizar().catch(() => {}); }, 60000);

// ---------------------------------------------------------------- arranque
async function iniciar() {
  try { await listo(); } catch (e) {
    $("#screen").innerHTML = `<div class="content"><div class="banner bad">Este navegador no permite guardar datos en el dispositivo (modo privado o sin espacio). Abra la aplicación en una ventana normal.</div></div>`;
    return;
  }
  await cargarCatalogo();
  S.ultimaSync = (await meta("ultima_sync")) || null;
  const s = await leerSesion();
  if (s && Date.parse(s.expira_en) > Date.now()) {
    const { k, ...usuario } = s;
    S.usuario = usuario;
    await cargarDatos(usuario.id);
    S.pantalla = misFincas().length ? "p10" : "p09";
    render();
    pedirSync(300);
  } else {
    if (s) { await borrarSesion(); S.f = { lmail: s.correo || "" }; S.pantalla = "p07"; warnB("V-46"); } 
    render();
  }
  if ("serviceWorker" in navigator) navigator.serviceWorker.register("sw.js").catch((e) => console.warn("Service worker:", e));
}
iniciar();
