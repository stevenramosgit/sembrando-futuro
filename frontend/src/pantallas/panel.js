// Panel (P-09, P-10), sincronización (P-25) y cuenta (P-26).
import { llamar, ErrorRed } from "../api.js";
import { dn, fmt, ha2, horaCO, money, esc, hoyISO } from "../calculos/formato.js";
import { estimarCostos, semaforoVigencia } from "../calculos/formulas.js";
import { proyeccionHtml } from "./cosecha.js";
import { msg } from "../calculos/validaciones.js";
import { meta } from "../db/db.js";
import { S, borrarSesion, ciclo, cultivo, cultivosDe, descartar, finanzas, finca, matasDe, misCiclos, misFincas, nombresCultivos, pendCount, rechazados, totalMatas, vaciarDatos } from "../estado.js";
import { sincronizar } from "../sync.js";
import { ico } from "../iconos.js";
import { A, P, banner, btn, ejecutar, fld, kv, okB, raiz, render, topBanner } from "../ui.js";

/** Nombre corto de un ciclo: «finca · nombre de referencia · cultivos», con «(cerrado)» si ya se cerró. */
export const cyLabel = (c) => {
  const f = finca(c.finca_id);
  return `${f.nombre} · ${c.nombre_lote || "Ciclo"} · ${nombresCultivos(c.id) || "sin cultivos"}${c.estado === "CERRADO" ? " (cerrado)" : ""}`;
};
const COLOR = { VERDE: "Verde", AMARILLO: "Amarillo", ROJO: "Rojo" };
/** Fila del semáforo de vigencia del ciclo (verde, amarillo o rojo), si el ciclo tiene vigencia. */
const vigenciaHtml = (c) => {
  const v = semaforoVigencia(c.fecha_siembra, c.vigencia_anios, hoyISO());
  if (v.fin === null) return kv("Vigencia", "No definida");
  return kv("Vigencia", `<span class="badge sem-${v.semaforo.toLowerCase()}">${COLOR[v.semaforo]}</span> ${dn(v.restantes)} años restantes`) + kv("Fin estimado", isoCorta(v.fin));
};
/** Costos aproximados con la ficha técnica de cada cultivo del ciclo. Los valores de la ficha pueden estar por validar. */
const fichasHtml = (c) => {
  const filas = cultivosDe(c.id).map((cc) => {
    const cu = cultivo(cc.cultivo_codigo), mt = matasDe(cc);
    if (!cu?.ficha_tecnica || mt === null) return "";
    const e = estimarCostos(cu.ficha_tecnica, mt);
    const dudoso = (cu.ficha_tecnica.datos_extra?.estado || "").startsWith("POR_");
    return `<h3>${esc(cu.nombre)} · ${fmt(mt)} matas</h3>${kv("Siembra inicial", money(e.siembra))}${kv("Insumos por año", money(e.insumos))}${kv("Jornales por año", dn(e.jornales))}${dudoso ? '<div class="muted">Valores de la ficha por validar.</div>' : ""}`;
  }).join("");
  return filas ? `<div class="card"><h3>Costos aproximados (ficha técnica)</h3>${filas}<div class="muted">Son valores orientativos de la ficha técnica, no un presupuesto.</div></div>` : "";
};
/** Proyección de cosecha de cada cultivo del ciclo con matas calculadas. */
const cosechasHtml = (c) => cultivosDe(c.id).map((cc) => {
  const cu = cultivo(cc.cultivo_codigo), mt = matasDe(cc);
  return cu && mt !== null ? proyeccionHtml(cu, mt, c.fecha_siembra, `Proyección de cosecha · ${cu.nombre}`) : "";
}).join("");
/** Fecha AAAA-MM-DD como día/mes/año. */
export const isoCorta = (iso) => iso.split("-").reverse().join("/");

/** P-09 Inicio sin fincas: invita a crear la primera finca. Si ya hay fincas, muestra P-10. */
P.p09 = () => misFincas().length ? P.p10() : ({ t: "Inicio", nav: 0, h: `${topBanner()}<div class="portada"><img src="img/brote.svg" alt="" width="84" height="84"><h2>Bienvenido a Sembrando Futuro</h2><p>Aún no tiene fincas. Registre la primera para empezar a calcular y a llevar sus cuentas.</p></div>${btn("go:p12", "Registrar mi primera finca")}${btn("go:p16", "Ver catálogo de cultivos", "sec")}` });

/** Indicador del panel con ícono, etiqueta y valor. */
const kpi = (icono, etiqueta, valor, extra = "") => `<div class="kpi${extra}"><span>${ico(icono, 18)}${etiqueta}</span><b>${valor}</b></div>`;
/** Barra horizontal proporcional para comparar ingresos y gastos. */
const barra = (clase, etiqueta, v, tope) => `<div class="barra-fila"><span>${etiqueta}</span><div class="barra-pista"><div class="barra ${clase}" style="--v:${(v / tope).toFixed(4)}"></div></div></div>`;

/** Resumen del ciclo: matas, gastos, ingresos, utilidad o pérdida, rentabilidad, vigencia, costos de la ficha y cosecha. */
function resumenCicloHtml(c) {
  const m = finanzas(c.id), mt = totalMatas(c.id);
  const pendientes = pendCount() ? `<div class="alert alert-secondary">Pendientes por enviar: ${pendCount()} ${pendCount() === 1 ? "registro" : "registros"}</div>` : "";
  const acciones = c.estado === "ACTIVO" ? btn("go:p21", "Registrar gasto") + btn("go:p15", "Cerrar ciclo", "sec") : `<div class="alert alert-secondary">Ciclo cerrado el ${isoCorta(c.fecha_cierre)}.</div>`;
  const perdida = m.u < 0, tope = Math.max(m.g, m.i, 1);
  const principal = `<div class="kpi kpi-grande ${perdida ? "perdida" : "ganancia"}"><span>${ico(perdida ? "bajada" : "subida", 20)}${perdida ? "Pérdida" : "Utilidad neta"}</span><b>${money(m.u)}</b><small>Rentabilidad ${fmt(m.r, 1)} %</small></div>`;
  const indicadores = `<div class="kpis">${principal}${kpi("subida", "Ingresos", money(m.i))}${kpi("bajada", "Gastos", money(m.g))}${kpi("area", "Área efectiva", ha2(c.area_efectiva_ha))}${kpi("brote", "Total de matas", mt === null ? "—" : fmt(mt))}</div>`;
  const balance = `<div class="card"><h3>Ingresos y gastos</h3><div class="barras">${barra("barra-ingreso", "Ingresos", m.i, tope)}${barra("barra-gasto", "Gastos", m.g, tope)}</div>${kv("Utilidad por hectárea", money(m.ha))}</div>`;
  return `<h3 class="mb-2">Resumen del ciclo</h3>${indicadores}${balance}<div class="card"><h3>Vigencia del ciclo</h3>${vigenciaHtml(c)}</div>${cosechasHtml(c)}${fichasHtml(c)}${S.enLinea ? "" : banner("warn", msg("V-44"), "V-44")}${pendientes}${acciones}`;
}

/** Deja elegida una finca y un ciclo válidos para el panel: si la selección guardada ya no existe, toma la primera finca
 *  y, dentro de ella, el ciclo activo (o el primero). Devuelve los ciclos de la finca elegida. */
function ajustarSeleccion(fincas, cs) {
  if (!S.sel.finca || !fincas.some((f) => f.id === S.sel.finca)) S.sel.finca = fincas[0]?.id;
  const fc = cs.filter((c) => c.finca_id === S.sel.finca);
  if (!S.sel.ciclo || !fc.some((c) => c.id === S.sel.ciclo)) S.sel.ciclo = (fc.find((c) => c.estado === "ACTIVO") || fc[0])?.id;
  return fc;
}

// P-10 Inicio: selector de finca y ciclo, y el resumen del ciclo elegido (matas, gastos, ingresos, utilidad y proyección).
P.p10 = () => {
  const fincas = misFincas(), cs = misCiclos();
  if (!cs.length && !fincas.length) return P.p09();
  const fc = ajustarSeleccion(fincas, cs);
  const c = ciclo(S.sel.ciclo);
  const body = c ? resumenCicloHtml(c) : `<div class="alert alert-secondary">Esta finca aún no tiene ciclos. Cree el primero desde Fincas.</div>${btn("go:p14", "Nuevo ciclo")}`;
  const opcionesCiclo = fc.length ? fc.map((x) => [x.id, cyLabel(x).split(" · ").slice(1).join(" · ")]) : [["", "Sin ciclos"]];
  return { t: "Inicio", nav: 0, h: `${topBanner()}${fld("selFarm", "Finca", { opts: fincas.map((f) => [f.id, f.nombre]), value: S.sel.finca, rerender: 1 })}${fld("selCycle", "Ciclo", { opts: opcionesCiclo, value: S.sel.ciclo, rerender: 1 })}${body}` };
};

const NOMBRE_TIPO = { finca: "Finca", ciclo: "Ciclo", ciclo_cultivo: "Cultivo del ciclo", gasto: "Gasto", jornal: "Jornales", ingreso: "Ingreso" };
/** Descripción corta de un registro rechazado para la lista de P-25. */
const describir = (r) => {
  if (r.tipo === "finca") return r.nombre;
  if (r.tipo === "ciclo") return r.nombre_lote || "Ciclo";
  if (r.tipo === "ciclo_cultivo") return cultivo(r.cultivo_codigo)?.nombre || r.cultivo_codigo;
  if (r.tipo === "gasto") return `${r.categoria} · ${money(r.valor_cop)}`;
  if (r.tipo === "jornal") return `${r.jornales} × ${money(r.valor_diario_cop)}`;
  return `${r.cantidad} × ${money(r.precio_unitario_cop)}`;
};
/** P-25 Sincronizar: estado de la conexión, última sincronización, pendientes y registros rechazados con su motivo. */
P.p25 = () => {
  const rej = rechazados();
  const ult = S.ultimaSync ? (new Date(S.ultimaSync).toDateString() === new Date().toDateString() ? "hoy " : "antes ") + horaCO(S.ultimaSync) : "nunca";
  const lista = rej.map((r) => `<div class="card"><b>${NOMBRE_TIPO[r.tipo]} · ${esc(describir(r))}</b><div class="err" role="alert"><span>${esc(r.error?.mensaje || "")} <span class="muted">(${esc(r.error?.codigo || "")})</span></span></div>${["gasto", "jornal", "ingreso"].includes(r.tipo) ? btn("fixrej:" + r.tipo + ":" + r.id, "Corregir", "sec") : ""}${btn("dropdej:" + r.tipo + ":" + r.id, "Descartar del dispositivo", "danger")}</div>`).join("");
  return { t: "Sincronizar", back: 0, nav: 0, h: `${topBanner()}${S.enLinea ? banner("ok", "Con conexión: los registros se envían solos al abrir la app o al detectar internet.") : banner("warn", msg("V-44"), "V-44")}<div class="card"><h3>Estado de sincronización</h3>${kv("Pendientes por enviar", pendCount() + (pendCount() === 1 ? " registro" : " registros"))}${kv("Rechazados por el servidor", String(rej.length))}${kv("Última sincronización", ult)}</div>${rej.length ? `<h3>Rechazados</h3>${lista}` : ""}${btn("syncnow", "Sincronizar ahora", "", S.enLinea ? "" : "disabled")}` };
};
/** P-26 Cuenta: datos del usuario, política de datos y cerrar sesión. */
P.p26 = () => ({ t: "Cuenta", back: 0, nav: 0, h: `<div class="card"><b>${esc(S.usuario.nombre)}</b><div class="muted">${esc(S.usuario.correo)} · ${esc(S.usuario.ubicacion)}</div></div>${S.ctx.out ? banner("warn", pendCount() === 1 ? "Tiene 1 registro sin enviar. Se conservará en este dispositivo. ¿Cerrar sesión?" : msg("V-20").replace("N", pendCount()), "V-20") + btn("outyes", "Cerrar sesión") + btn("back", "Cancelar", "sec") : btn("outask", "Cerrar sesión", "danger")}<button class="linkbtn" data-act="go:p27">Política de datos y ayuda</button>` });

/** Sincronizar ahora (botón de P-25) y mostrar el resultado. */
A.syncnow = (el) => ejecutar(el, async () => {
  if (!S.enLinea) return;
  const r = await sincronizar();
  if (r.estado === "ok") okB("Datos sincronizados.");
  else if (r.estado === "sesion_vencida") return;
  else if (r.estado === "sin_conexion") S.banner = { k: "warn", m: msg("V-44"), c: "V-44" };
  else S.banner = { k: "warn", m: msg("V-45"), c: "V-45" };
});
/** Abrir un registro rechazado para corregirlo. */
A.fixrej = (tipo, id) => {
  import("../estado.js").then((m) => { const r = m.lista(tipo).find((x) => x.id === id); if (r) { S.sel.ciclo = r.ciclo_id; A.edit(tipo, id); } });
};
/** Descartar un registro rechazado (se borra del teléfono). */
A.dropdej = async (tipo, id) => { await descartar(tipo, id); render(); };
/** Cerrar sesión: si hay registros sin enviar, primero pregunta, porque se perderían. */
A.outask = () => { if (!pendCount()) return A.outyes(); S.ctx.out = true; render(); };
/** Cierra la sesión: borra la sesión y los datos en memoria y revoca el token (A-06); sin conexión lo revoca después. */
A.outyes = async () => {
  const token = S.usuario?.token;
  S.usuario = null; S.ctx = {}; S.claveTemporal = null;
  await borrarSesion();
  vaciarDatos();
  if (token) {
    try { const r = await llamar("POST", "/auth/salida", { token }); if (r.estado >= 500) await meta("salida_pendiente", token); }
    catch (e) { if (e instanceof ErrorRed) await meta("salida_pendiente", token); }
  }
  raiz("p01");
};
