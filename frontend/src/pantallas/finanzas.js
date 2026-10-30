// Finanzas: gastos, jornales e ingresos (P-20 a P-24). Cada registro se guarda en el dispositivo y se envía cuando hay conexión.
import { dn, esc, fmt, money, parseDec, parseEnt, hoyISO, ahoraMs } from "../calculos/formato.js";
import { costoJornal, totalIngreso } from "../calculos/formulas.js";
import { CATEGORIAS, E, NOMBRE_CATEGORIA, msg, vCantidad, vFechaRegistro, vJornales, vObservaciones, vPrecio, vValorGasto, vValorJornal } from "../calculos/validaciones.js";
import { S, ciclo, cultivo, cultivosDe, nombresCultivos, eliminar, finanzas, gastosDe, guardar, ingresosDe, jornalesDe, lista, misCiclos, restaurar, uuid } from "../estado.js";
import { ico } from "../iconos.js";
import { A, DEFECTOS, P, badB, banner, btn, ejecutar, fld, fldFecha, go, kv, kvUtilidad, okB, render, topBanner, val } from "../ui.js";
import { cyLabel, isoCorta } from "./panel.js";

DEFECTOS.p21 = () => ({ gfecha: hoyISO() });
DEFECTOS.p22 = () => ({ jfecha: hoyISO() });
DEFECTOS.p23 = () => ({ ifecha: hoyISO() });

/** Límites del calendario: desde la siembra del ciclo hasta hoy (V-47). */
const limitesRegistro = () => { const c = ciclo(S.sel.ciclo); return { min_f: c?.fecha_siembra, max_f: hoyISO() }; };

/** Opciones de la lista de categorías de gasto. */
const catOpts = (primero) => [...(primero ? [["", primero]] : []), ...CATEGORIAS.map((c) => [c, NOMBRE_CATEGORIA[c]])];

const ICONO_MOV = { gasto: "recibo", jornal: "personas", ingreso: "subida" };
/** Gastos, jornales e ingresos de un ciclo en una sola lista, del más reciente al más antiguo. */
const movimientos = (cid) => {
  return [
    ...gastosDe(cid).map((x) => ({ k: "gasto", r: x, t: x.observaciones || NOMBRE_CATEGORIA[x.categoria], s: "Gasto · " + NOMBRE_CATEGORIA[x.categoria], v: -x.valor_cop })),
    ...jornalesDe(cid).map((x) => ({ k: "jornal", r: x, t: `Jornales (${dn(x.jornales)} × ${money(x.valor_diario_cop)})`, s: "Mano de obra", v: -costoJornal(x.jornales, x.valor_diario_cop) })),
    ...ingresosDe(cid).map((x) => ({ k: "ingreso", r: x, t: "Venta de " + (cultivo(x.cultivo_codigo)?.nombre.toLowerCase() || "cultivo"), s: `${dn(x.cantidad)} × ${money(x.precio_unitario_cop)}`, v: totalIngreso(x.cantidad, x.precio_unitario_cop) })),
  ].sort((a, b) => b.r.fecha.localeCompare(a.r.fecha) || b.r.updated_at.localeCompare(a.r.updated_at));
};

/** P-20 Finanzas del ciclo: totales, utilidad o pérdida y la lista de movimientos. */
P.p20 = () => {
  const cs = misCiclos();
  if (!cs.length) return { t: "Finanzas", nav: 3, back: 0, h: `<div class="alert alert-secondary">Cree un ciclo para registrar gastos e ingresos.</div>${btn("go:p14", "Nuevo ciclo")}` };
  if (!S.sel.ciclo || !cs.some((c) => c.id === S.sel.ciclo)) S.sel.ciclo = cs[0].id;
  const c = ciclo(S.sel.ciclo), m = finanzas(c.id);
  return { t: "Finanzas", nav: 3, back: 0, h: `${topBanner()}${fld("selCycle", "Ciclo", { opts: cs.map((x) => [x.id, cyLabel(x)]), value: S.sel.ciclo, rerender: 1 })}${c.estado === "CERRADO" ? `<div class="alert alert-secondary">Ciclo cerrado: no admite nuevos registros.</div>` : ""}<div class="card hl"><h3>${esc(nombresCultivos(c.id))}</h3>${kv("Gastos", money(m.g))}${kv("Ingresos", money(m.i))}${kvUtilidad(m.u, money(m.u))}${kv("Rentabilidad", fmt(m.r, 1) + " %")}</div>${movimientos(c.id).length ? `<p class="muted mb-2">Seleccione un registro para editarlo o eliminarlo.</p>` : ""}${movimientos(c.id).map((x) => `<div class="fila"><button class="tap" data-act="edit:${x.k}:${x.r.id}"><span class="chip-ico chip-${x.k}">${ico(ICONO_MOV[x.k], 20)}</span><span class="grow"><b>${esc(x.t)}</b><span class="muted d-block">${esc(x.s)} · ${isoCorta(x.r.fecha)}</span></span><b class="monto ${x.v < 0 ? "sale" : "entra"}">${x.v < 0 ? "− " : ""}${money(Math.abs(x.v))}</b></button>${x.r.sync === "PENDIENTE" ? '<span class="badge off">pend.</span>' : x.r.sync === "RECHAZADO" ? '<span class="badge off">rechazado</span>' : ""}</div>`).join("")}<div class="mt-3"></div>${btn("go:p21", "Registrar gasto")}${btn("go:p22", "Registrar jornales", "sec")}${btn("go:p23", "Registrar ingreso", "sec")}` };
};
/** Encabezado con el ciclo al que se le está registrando el movimiento. */
const cyHead = () => { const c = ciclo(S.sel.ciclo); return c ? `<div class="alert alert-secondary">${esc(cyLabel(c))}</div>` : ""; };

/** P-21 Registrar gasto. */
P.p21 = () => ({ t: "Registrar gasto", h: `${topBanner()}${cyHead()}${fldFecha("gfecha", "Fecha", limitesRegistro())}${fld("gcat", "Categoría", { opts: catOpts("Elija una categoría") })}${fld("gval", "Valor ($)", { im: "numeric", hint: "De $1 a $50.000.000, solo números." })}${fld("gobs", "Observaciones (opcional)", { hint: "Máximo 150 caracteres." })}${btn("savegas", "Guardar gasto")}` });
/** P-22 Registrar jornales (con el costo calculado mientras se escribe). */
P.p22 = () => ({ t: "Registrar jornales", h: `${topBanner()}${cyHead()}${fldFecha("jfecha", "Fecha", limitesRegistro())}${fld("jn", "Número de jornales", { im: "decimal", hint: "De 0,5 a 999, de medio en medio." })}${fld("jv", "Valor del jornal ($)", { im: "numeric" })}<div class="card hl" id="prevj"></div>${btn("savejor", "Guardar jornales")}` });
/** P-23 Registrar ingreso: cultivo vendido, cantidad en su unidad comercial y precio unitario. */
P.p23 = () => {
  const c = ciclo(S.sel.ciclo);
  const ccs = c ? cultivosDe(c.id) : [];
  const cod = ccs.length === 1 ? ccs[0].cultivo_codigo : val("icult");
  const u = cod ? cultivo(cod)?.unidad_comercial || "unidad" : "—";
  const elegir = ccs.length > 1 ? fld("icult", "Cultivo vendido", { opts: [["", "Elija un cultivo"], ...ccs.map((x) => [x.cultivo_codigo, cultivo(x.cultivo_codigo)?.nombre || x.cultivo_codigo])], rerender: 1 }) : "";
  return { t: "Registrar ingreso", h: `${topBanner()}${cyHead()}${elegir}${fldFecha("ifecha", "Fecha", limitesRegistro())}<div class="card"><h3>Unidad comercial</h3>${esc(u)}</div>${fld("iq", "Cantidad", { im: "decimal", hint: "De 0,1 a 10.000." })}${fld("ip", "Precio por unidad ($)", { im: "numeric" })}<div class="card hl" id="previ"></div>${btn("saveinc", "Guardar ingreso")}` };
};
/** P-24 Editar o eliminar un registro (si el servidor lo rechazó, muestra el motivo). */
P.p24 = () => {
  const { k, id } = S.ctx.rec;
  const r = lista(k).find((x) => x.id === id && !x.eliminado);
  if (!r) return P.p20();
  const f = k === "gasto"
    ? `${fldFecha("gfecha", "Fecha", limitesRegistro())}${fld("gcat", "Categoría", { opts: catOpts() })}${fld("gval", "Valor ($)", { im: "numeric" })}${fld("gobs", "Observaciones (opcional)")}`
    : k === "jornal"
      ? `${fldFecha("jfecha", "Fecha", limitesRegistro())}${fld("jn", "Número de jornales", { im: "decimal" })}${fld("jv", "Valor del jornal ($)", { im: "numeric" })}`
      : `${cultivosDe(S.sel.ciclo).length > 1 ? fld("icult", "Cultivo vendido", { opts: cultivosDe(S.sel.ciclo).map((x) => [x.cultivo_codigo, cultivo(x.cultivo_codigo)?.nombre || x.cultivo_codigo]) }) : ""}${fldFecha("ifecha", "Fecha", limitesRegistro())}${fld("iq", "Cantidad", { im: "decimal" })}${fld("ip", "Precio por unidad ($)", { im: "numeric" })}`;
  const rechazo = r.sync === "RECHAZADO" && r.error ? banner("bad", r.error.mensaje, r.error.codigo) : "";
  return { t: "Editar registro", h: `${topBanner()}${rechazo}${cyHead()}${f}${btn("saveedit", "Guardar cambios")}${btn("del", "Eliminar registro", "danger")}` };
};

// ---------------------------------------------------------------- acciones
const cicloAbierto = () => {
  const c = ciclo(S.sel.ciclo);
  if (!c) { S.banner = { k: "bad", m: "Primero cree un ciclo." }; return null; }
  if (c.estado === "CERRADO") { badB("V-31"); return null; }
  return c;
};
/** Lee y valida la fecha de un movimiento (entre la siembra y hoy). */
const fechaDe = (id, c) => { const r = vFechaRegistro(val(id), c.fecha_siembra); if (r.error) S.e[id] = r.error; return r.iso; };
/** Anota el error de un campo si lo hay. */
const campo = (id, e) => { if (e) S.e[id] = e; };

/** Valida un gasto y devuelve sus datos listos para guardar. */
function revisarGasto(c) {
  const fecha = fechaDe("gfecha", c);
  if (!val("gcat")) S.e.gcat = E("V-37");
  campo("gval", vValorGasto(val("gval")));
  campo("gobs", vObservaciones(val("gobs")));
  return { fecha, categoria: val("gcat"), valor_cop: parseEnt(val("gval")), observaciones: val("gobs").trim() || null };
}
/** Valida un registro de jornales y devuelve sus datos. */
function revisarJornal(c) {
  const fecha = fechaDe("jfecha", c);
  campo("jn", vJornales(val("jn")));
  campo("jv", vValorJornal(val("jv")));
  return { fecha, jornales: parseDec(val("jn")), valor_diario_cop: parseEnt(val("jv")) };
}
/** Valida un ingreso y devuelve sus datos. */
function revisarIngreso(c) {
  const fecha = fechaDe("ifecha", c);
  const ccs = cultivosDe(c.id);
  const cod = ccs.length === 1 ? ccs[0].cultivo_codigo : val("icult");
  if (!cod) S.e.icult = E("V-27");
  campo("iq", vCantidad(val("iq")));
  campo("ip", vPrecio(val("ip")));
  return { fecha, cultivo_codigo: cod, cantidad: parseDec(val("iq")), precio_unitario_cop: parseEnt(val("ip")) };
}
/** Vuelve a Finanzas, quita del historial los formularios ya usados y muestra el mensaje. */
const terminar = (m) => {
  S.pila = S.pila.filter((x) => !["p21", "p22", "p23", "p24"].includes(x));
  S.pantalla = "p20"; S.f = {};
  if (m) okB(m);
};

/** Guardar el gasto en el teléfono (la utilidad se recalcula al momento). */
A.savegas = (el) => ejecutar(el, async () => {
  const c = cicloAbierto(); if (!c) return;
  const d = revisarGasto(c); if (Object.keys(S.e).length) return;
  await guardar("gasto", { id: uuid(), ciclo_id: c.id, ...d, eliminado: false });
  terminar("Gasto guardado. La utilidad se actualizó.");
});
/** Guardar los jornales en el teléfono. */
A.savejor = (el) => ejecutar(el, async () => {
  const c = cicloAbierto(); if (!c) return;
  const d = revisarJornal(c); if (Object.keys(S.e).length) return;
  await guardar("jornal", { id: uuid(), ciclo_id: c.id, ...d, eliminado: false });
  terminar("Jornales guardados. Costo: " + money(costoJornal(d.jornales, d.valor_diario_cop)) + ".");
});
/** Guardar el ingreso en el teléfono. */
A.saveinc = (el) => ejecutar(el, async () => {
  const c = cicloAbierto(); if (!c) return;
  const d = revisarIngreso(c); if (Object.keys(S.e).length) return;
  await guardar("ingreso", { id: uuid(), ciclo_id: c.id, ...d, unidad_comercial: cultivo(d.cultivo_codigo)?.unidad_comercial || "unidad", eliminado: false });
  terminar("Ingreso guardado. La utilidad se actualizó.");
});
/** Abrir P-24 con los datos del registro. */
A.edit = (k, id) => {
  const r = lista(k).find((x) => x.id === id);
  S.ctx.rec = { k, id };
  S.sel.ciclo = r.ciclo_id;
  const pre = k === "gasto" ? { gfecha: r.fecha, gcat: r.categoria, gval: String(r.valor_cop), gobs: r.observaciones || "" }
    : k === "jornal" ? { jfecha: r.fecha, jn: dn(r.jornales), jv: String(r.valor_diario_cop) }
      : { icult: r.cultivo_codigo, ifecha: r.fecha, iq: dn(r.cantidad), ip: String(r.precio_unitario_cop) };
  go("p24", pre);
};
/** Guardar los cambios de un registro. */
A.saveedit = (el) => ejecutar(el, async () => {
  const { k, id } = S.ctx.rec;
  const c = cicloAbierto(); if (!c) return;
  const r = lista(k).find((x) => x.id === id);
  const d = k === "gasto" ? revisarGasto(c) : k === "jornal" ? revisarJornal(c) : revisarIngreso(c);
  if (Object.keys(S.e).length) return;
  await guardar(k, { ...r, ...d });
  terminar("Cambios guardados. Los saldos se recalcularon.");
});
/** Eliminar un registro (eliminación lógica) con la opción de deshacer durante 10 segundos. */
A.del = (el) => ejecutar(el, async () => {
  const { k, id } = S.ctx.rec;
  const c = cicloAbierto(); if (!c) return;
  const r = lista(k).find((x) => x.id === id);
  await eliminar(k, r);
  S.aviso = { m: "Registro eliminado. La utilidad se recalculó.", hasta: ahoraMs() + 10000, undo: { k, id } };
  terminar("");
});
/** Deshacer la última eliminación si aún no pasaron los 10 segundos (si pasaron, V-43). */
A.undo = async () => {
  const t = S.aviso;
  if (!t) return;
  if (ahoraMs() > t.hasta) { t.m = msg("V-43"); t.muerto = true; render(); return; }
  const r = lista(t.undo.k).find((x) => x.id === t.undo.id);
  if (r) await restaurar(t.undo.k, r);
  S.aviso = null;
  render();
};
