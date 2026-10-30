// Arranque de la PWA: dibuja la pantalla actual, atiende los toques y mantiene la conexión, la sesión y la sincronización.
import { esc, ha2, money, parseDec, parseEnt, ahoraMs } from "./calculos/formato.js";
import { msg } from "./calculos/validaciones.js";
import { aHectareas, costoJornal, totalIngreso } from "./calculos/formulas.js";
import { listo, meta } from "./db/db.js";
import { ico } from "./iconos.js";
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
const NAVS = [["p10", "Inicio", "inicio"], ["p11", "Fincas", "mapa"], ["p18", "Calcular", "calculadora"], ["p20", "Finanzas", "grafica"], ["p16", "Catálogo", "libro"]];
const SUB = new Set(["reg", "otpv", "otpr", "chm", "login", "savefinca", "savecy", "savecult", "savearea", "closego", "closeyes", "calc", "savegas", "savejor", "saveinc", "saveedit", "del", "syncnow"]);

// ---------------------------------------------------------------- dibujo

/** P-13: muestra mientras se escribe el área no sembrable convertida a hectáreas. */
function previaArea() {
  const l = ciclo(S.ctx.cy), el = $("#prev13");
  if (!el || !l) return;
  const t = val("nosemb").trim();
  const v = t === "" ? 0 : parseDec(t);
  const ha = v === null ? null : aHectareas(v, val("unit") || "m2");
  el.innerHTML = ha === null ? "<h3>Convertido</h3>Escriba solo números." : `<h3>Resultado</h3><div class="kv"><span>Convertido a hectáreas</span><b>${ha2(ha)}</b></div><div class="kv"><span>Área efectiva</span><b>${ha < l.area_bruta_ha ? ha2(Math.round((l.area_bruta_ha - ha) * 1e4) / 1e4) : "—"}</b></div>`;
}

/** P-22: muestra mientras se escribe el costo total de los jornales. */
function previaJornal() {
  const n = parseDec(val("jn")), v = parseEnt(val("jv")), el = $("#prevj");
  if (el) el.innerHTML = `<h3>Cálculo automático</h3><div class="kv"><span>Costo total</span><b>${n !== null && v !== null ? money(costoJornal(n, v)) : "—"}</b></div>`;
}

/** P-23: muestra mientras se escribe el total del ingreso. */
function previaIngreso() {
  const q = parseDec(val("iq")), p = parseEnt(val("ip")), el = $("#previ");
  if (el) el.innerHTML = `<h3>Total del ingreso</h3><div class="kv"><span>Total</span><b>${q !== null && p !== null ? money(totalIngreso(q, p)) : "—"}</b></div>`;
}

const PREVIAS = { p13: previaArea, p22: previaJornal, p23: previaIngreso };
/** Actualiza el cálculo automático de la pantalla actual, si tiene uno. */
function vistaPrevia() {
  const dibujarPrevia = PREVIAS[S.pantalla];
  if (dibujarPrevia) dibujarPrevia();
}

/** Arma la pantalla actual; si algo falla muestra un aviso en lugar de dejar la pantalla en blanco. */
function pantallaActual() {
  try { return P[S.pantalla](); } catch (x) {
    console.error(x);
    return { t: "Sembrando Futuro", h: '<div class="alert alert-danger">Ocurrió un error inesperado. Intente de nuevo.</div>' };
  }
}

/** Iniciales del nombre para el círculo de la cuenta: «María Pérez» → «MP». */
const iniciales = (nombre) => (nombre || "").trim().split(/\s+/).slice(0, 2).map((p) => p[0] || "").join("").toUpperCase();
/** Primer nombre del usuario: «María Pérez» → «María». */
const primerNombre = (nombre) => (nombre || "").trim().split(/\s+/)[0] || "";

/** Lado derecho del encabezado en el computador: con sesión, la cuenta (iniciales y nombre) y Salir;
 *  sin sesión, Ingresar y Crear cuenta. En el teléfono se ocultan: allí se usan la pastilla de la cuenta y la portada. */
function accionesPc(nav) {
  if (S.usuario && nav) {
    return `<button class="usuario-pc" data-act="cuenta" title="${esc(S.usuario.nombre)} · ${esc(S.usuario.correo || "")}"><span class="avatar">${esc(iniciales(S.usuario.nombre))}</span><span>${esc(primerNombre(S.usuario.nombre))}</span></button>`
      + `<button class="btn btn-contorno btn-nav" data-act="salir">${ico("salir", 18)}Salir</button>`;
  }
  if (!S.usuario) return `<button class="btn btn-fantasma btn-nav" data-act="cab:p07">Ingresar</button><button class="btn btn-primario btn-nav" data-act="cab:p02">Crear cuenta</button>`;
  return "";
}

/** Encabezado del sitio. Teléfono: Volver (o el emblema), título de la pantalla, cuenta y conexión.
 *  Computador: logo con el nombre, menú principal (Inicio, Mis fincas, Calcular, Finanzas, Catálogo), conexión y cuenta. */
function barraSuperior(sc, hayVolver, nav) {
  const n = pendCount();
  const pastilla = `<button class="pill${S.enLinea ? "" : " fuera"}" data-act="go:${S.usuario ? "p25" : "p01"}" ${S.usuario ? "" : "tabindex=-1"} aria-label="Estado de conexión"><span class="punto" aria-hidden="true"></span>${S.enLinea ? "En línea" : "Sin conexión"}${n ? " · " + n : ""}</button>`;
  const cuenta = S.usuario && nav ? `<button class="pill cuenta" data-act="go:p26" aria-label="Cuenta">${ico("usuario", 22)}<span class="sr">Cuenta</span></button>` : "";
  const inicio = hayVolver ? `<button class="back" data-act="back" aria-label="Volver">${ico("atras", 26)}</button>` : `<img class="marca" src="img/emblema.png" alt="" width="40" height="40">`;
  const marca = `<button class="marca-pc" data-act="marca" aria-label="Sembrando Futuro, ir al inicio"><img src="img/emblema.png" alt="" width="40" height="40"><span>Sembrando Futuro</span></button>`;
  const menu = nav ? `<nav class="nav-sup" aria-label="Principal">${NAVS.map((x, i) => `<button data-act="nav:${x[0]}" ${i === sc.nav ? 'aria-current="page"' : ""}>${x[1] === "Fincas" ? "Mis fincas" : x[1]}</button>`).join("")}</nav>` : '<span class="nav-sup"></span>';
  return `<header class="appbar"><div class="nav-fila">${inicio}${marca}<h1>${esc(sc.t)}</h1>${menu}<div class="nav-acciones">${pastilla}${cuenta}${accionesPc(nav)}</div></div></header>`;
}

/** Pestañas inferiores: Inicio, Fincas, Calcular, Finanzas y Catálogo. */
const barraInferior = (sc, nav) => (nav
  ? `<nav class="tabs" aria-label="Principal"><div class="nav-marca"><img src="img/emblema.png" alt="" width="56" height="56"><span>Sembrando<br>Futuro</span></div>${NAVS.map((x, i) => `<button data-act="tab:${x[0]}" ${i === sc.nav ? 'aria-current="page"' : ""}>${ico(x[2], 24)}<span>${x[1]}</span></button>`).join("")}</nav>`
  : "");

/** Pie de página (como el sitio del proyecto): marca, herramientas, datos del proyecto y tratamiento de datos.
 *  Se ve en la portada y, en el computador, al final de cada pantalla. */
const pieHtml = () => `<footer class="pie"><div class="pie-rejilla"><div class="pie-marca"><span class="pie-logo"><img src="img/emblema.png" alt="" width="32" height="32">Sembrando Futuro</span><p>Gestión agrícola para pequeñas y medianas fincas del Cauca.</p></div>`
  + `<div class="pie-col"><h2>Herramientas</h2><button data-act="pie:p18">Calculadora de matas</button><button data-act="pie:p16">Catálogo de cultivos</button><button data-act="pie:p11">Mis fincas</button></div>`
  + `<div class="pie-col"><h2>Proyecto</h2><span>Ingeniería de Sistemas · Unicomfacauca</span><span>Calidad de Software · 2026</span></div>`
  + `<div class="pie-col"><h2>Sus datos</h2><span>Tratados conforme a la Ley 1581 de 2012.</span><button data-act="pie:p27">Política de datos y ayuda</button><span>Funciona también sin conexión.</span></div></div></footer>`;

/** Aviso inferior temporal con el botón Deshacer (10 segundos después de eliminar un registro). */
const avisoHtml = () => (S.aviso
  ? `<div class="snack" id="toast" role="status"><span id="toastm">${esc(S.aviso.m)}</span>${S.aviso.muerto ? "" : `<button data-act="undo">Deshacer</button>`}</div>`
  : "");

/** Devuelve el cursor al campo donde estaba la persona después de volver a dibujar. */
function restaurarFoco(foco) {
  const el = foco && document.getElementById(foco);
  if (!el || !el.matches("input,select,textarea")) return;
  el.focus();
  try { el.setSelectionRange(el.value.length, el.value.length); } catch { /* selects y correos no admiten selección */ }
}

/** Dibuja la pantalla completa conservando el desplazamiento y el campo activo. */
function dibujar() {
  if (!S.usuario && AUTH.has(S.pantalla)) { S.pantalla = "p01"; S.pila = []; }  // sin sesión no se dibuja ninguna pantalla interna
  const sc = pantallaActual();
  const previo = $(".content");
  const arriba = previo && previo.dataset.s === S.pantalla ? previo.scrollTop : 0;
  const hayVolver = sc.back !== 0 && S.pila.length;
  const nav = sc.nav !== undefined && S.usuario;
  const foco = document.activeElement && document.activeElement.id;
  const tituloPc = sc.sinTituloPc ? "" : `<h2 class="titulo-pc">${esc(sc.t)}</h2>`;
  $("#screen").innerHTML = `${barraSuperior(sc, hayVolver, nav)}<div class="content" data-s="${S.pantalla}" id="content"><div class="contenedor">${tituloPc}${sc.h}</div>${pieHtml()}</div>${barraInferior(sc, nav)}${avisoHtml()}`;
  $("#content").scrollTop = arriba;
  restaurarFoco(foco);
  vistaPrevia();
}
alDibujar(dibujar);

// ---------------------------------------------------------------- acciones de navegación
// Acciones de navegación: Volver, abrir una pantalla, abrir una pestaña principal y elegir una opción de un grupo de botones.
A.back = () => volver();
A.go = (s) => go(s);
A.goroot = (s) => raiz(s);
A.tab = (s) => raiz(s === "p10" && !misFincas().length ? "p09" : s);
A.seg = (el) => { S.f[el.dataset.id] = el.dataset.v; render(); };
// Encabezado del computador y pie de página: el logo lleva al inicio, el menú abre la pestaña elegida y Salir cierra la sesión.
A.marca = () => raiz(S.usuario ? (misFincas().length ? "p10" : "p09") : "p01");
A.nav = (s) => A.tab(s);
A.cab = (s) => go(s);
A.cuenta = () => raiz("p26");
A.pie = (s) => (S.usuario ? raiz(s) : go(s));
A.rapido = (s) => raiz(s);
// Salir: sin pendientes cierra de una vez; con pendientes abre la cuenta y pide confirmación (RF-04).
A.salir = () => { if (!pendCount()) return A.outyes(); raiz("p26"); S.ctx.out = true; render(); };

document.addEventListener("click", (ev) => {
  const a = ev.target.closest("[data-act]");
  if (!a) return;
  ev.preventDefault();
  if (a.disabled) return;
  const [nombre, ...args] = a.dataset.act.split(":");
  if (nombre === "go") { if (args[0] === "p15") S.ctx = { ...S.ctx, cy: S.sel.ciclo, done: false, ask: false }; return go(args[0]); }
  if (A[nombre]) A[nombre](SUB.has(nombre) || nombre === "seg" ? a : args[0], args[1]);
});
/** Guarda en el estado lo que la persona escribe o elige; algunos campos (finca y ciclo del panel) redibujan la pantalla. */
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
    const b = document.querySelector(".content .btn-primario:not([disabled])");
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
/** RF-35: pide al navegador que no borre los datos del dispositivo cuando le falte espacio (almacenamiento persistente).
 *  Si el navegador no tiene esta función o la niega, la aplicación sigue igual. */
function pedirAlmacenamientoPersistente() {
  try { navigator.storage?.persist?.().catch(() => {}); } catch { /* navegador sin esta función */ }
}

/** Arranque: abre la base local, carga el catálogo y, si hay una sesión vigente, los datos del usuario; luego sincroniza. */
async function iniciar() {
  try { await listo(); } catch {
    $("#screen").innerHTML = `<div class="content"><div class="alert alert-danger">Este navegador no permite guardar datos en el dispositivo (modo privado o sin espacio). Abra la aplicación en una ventana normal.</div></div>`;
    return;
  }
  pedirAlmacenamientoPersistente();
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
