// Fincas y ciclos (P-11 a P-15, P-28). Un ciclo trae su área, su vigencia y uno o más cultivos (cada uno con su marco de siembra).
import { dn, esc, fmt, isoAEs, money, parseDec, hoyISO } from "../calculos/formato.js";
import { aHectareas, areaEfectiva, semaforoVigencia } from "../calculos/formulas.js";
import { E, vAreaBruta, vCierre, vDistancia, vLugar, vPendiente, vSiembra, vVigencia } from "../calculos/validaciones.js";
import { S, ciclo, ciclosDe, cultivo, cultivosDe, D, finanzas, finca, guardar, misFincas, nombresCultivos, uuid } from "../estado.js";
import { A, DEFECTOS, P, badB, banner, btn, ejecutar, fail, fld, go, kv, kvUtilidad, okB, raiz, seg, entrar, topBanner, val } from "../ui.js";
import { cyLabel, isoCorta } from "./panel.js";

const r4 = (x) => Math.round(x * 1e4) / 1e4;
DEFECTOS.p14 = () => ({ cfecha: isoAEs(hoyISO()) });
DEFECTOS.p15 = () => ({ cierre: isoAEs(hoyISO()) });
DEFECTOS.p13 = () => ({ unit: "m2" });

export const cultOpts = (primero) => [["", primero || "Elija un cultivo"], ...D.catalogo.map((c) => [c.codigo, c.nombre])];
const COLOR = { VERDE: "Verde", AMARILLO: "Amarillo", ROJO: "Rojo" };
/** Texto del semáforo de vigencia de un ciclo (vacío si el ciclo no tiene vigencia). */
export const textoVigencia = (c) => {
  const v = semaforoVigencia(c.fecha_siembra, c.vigencia_anios, hoyISO());
  return v.fin === null ? "" : `Vigencia ${COLOR[v.semaforo]} · ${dn(v.restantes)} años restantes (hasta ${isoCorta(v.fin)})`;
};

P.p11 = () => {
  let h = topBanner();
  misFincas().forEach((f) => {
    const cs = ciclosDe(f.id);
    h += `<div class="card"><h3>${esc(f.nombre)} <span class="muted">· ${fmt(cs.reduce((s, c) => s + c.area_bruta_ha, 0), 1)} ha</span></h3>`;
    cs.forEach((c) => {
      const vig = c.estado === "ACTIVO" ? textoVigencia(c) : "";
      h += `<div class="row" style="flex-wrap:wrap"><div class="grow"><b>${esc(c.nombre_lote || "Ciclo")}</b> · ${esc(nombresCultivos(c.id) || "sin cultivos")} · <span class="badge ${c.estado === "ACTIVO" ? "" : "off"}">${c.estado}</span><div class="muted">Área efectiva ${fmt(c.area_efectiva_ha, 4)} ha</div>${vig ? `<div class="muted">${esc(vig)}</div>` : ""}</div><div style="display:flex;gap:6px;flex-wrap:wrap"><button class="badge" data-act="fin:${c.id}">Finanzas</button>${c.estado === "ACTIVO" ? `<button class="badge" data-act="area:${c.id}">Área real</button><button class="badge" data-act="addcult:${c.id}">Agregar cultivo</button><button class="badge" data-act="close:${c.id}">Cerrar</button>` : ""}</div></div>`;
    });
    h += `<button class="badge" data-act="newcy:${f.id}">Nuevo ciclo</button></div>`;
  });
  return { t: "Mis fincas", nav: 1, h: h + btn("go:p12", "Agregar finca") };
};

P.p12 = () => ({ t: "Nueva finca", h: `${topBanner()}${fld("fnom", "Nombre de la finca")}${btn("savefinca", "Guardar finca")}` });

const toHa = () => {
  const t = val("nosemb").trim();
  const v = t === "" ? 0 : parseDec(t);
  return v === null ? null : aHectareas(v, val("unit") || "m2");
};
P.p13 = () => {
  const c = ciclo(S.ctx.cy);
  return { t: "Área efectiva", h: `${topBanner()}<div class="card"><h3>${esc(c.nombre_lote || "Ciclo")}</h3>${kv("Área bruta", fmt(c.area_bruta_ha, 4) + " ha")}</div>${fld("unit", "Unidad del área no sembrable", { opts: [["m2", "m²"], ["ha", "hectáreas"], ["plaza", "plazas"]], value: val("unit") || "m2", rerender: 1 })}${fld("nosemb", "Área no sembrable", { im: "decimal", hint: "1 ha = 10.000 m² = 1,5625 plazas (1 plaza = 0,64 ha)." })}<div class="card hl" id="prev13"></div>${btn("savearea", "Guardar")}${btn("go:p11", "Ahora no", "sec")}` };
};

/** Campos de un cultivo del ciclo: cultivo, marco de siembra y distancias. */
const camposCultivo = () => {
  const mc = val("marco");
  return `${fld("ccult", "Cultivo", { opts: cultOpts() })}<label>Marco de siembra (opcional)</label>${seg("marco", [["cuadrado", "Cuadrado"], ["rectangular", "Rectangular"], ["tresbolillo", "Tresbolillo"]])}${mc ? fld("ca", mc === "rectangular" ? "Distancia entre surcos (m)" : "Distancia entre matas (m)", { im: "decimal" }) : ""}${mc === "rectangular" ? fld("cb", "Distancia entre matas (m)", { im: "decimal" }) : ""}`;
};
/** Revisa cultivo y marco; devuelve {cultivo_codigo, marco, dist_a_m, dist_b_m} o null si hay errores. */
const revisarCultivo = (yaTiene = []) => {
  const mc = val("marco");
  if (!val("ccult")) S.e.ccult = E("V-27");
  else if (yaTiene.includes(val("ccult"))) S.e.ccult = E("V-50");
  let a = null, b = null, e;
  if (mc) {
    if ((e = vDistancia(val("ca")))) S.e.ca = e; else a = parseDec(val("ca"));
    if (mc === "rectangular") { if ((e = vDistancia(val("cb")))) S.e.cb = e; else b = parseDec(val("cb")); }
  }
  return { cultivo_codigo: val("ccult"), marco: mc || null, dist_a_m: a, dist_b_m: b };
};

P.p14 = () => ({ t: "Nuevo ciclo", h: `${topBanner()}${fld("cfinca", "Finca", { opts: [["", "Elija una finca"], ...misFincas().map((f) => [f.id, f.nombre])] })}${fld("cnom", "Nombre del lote (opcional)", { hint: "Solo es una referencia para usted, por ejemplo «Lote de abajo»." })}${fld("carea", "Área bruta (ha)", { im: "decimal", hint: "De 0,0001 a 10.000 hectáreas. El área no sembrable se define después con «Área real»." })}${fld("cpend", "Pendiente (%)", { im: "decimal", hint: "De 0 a 100 %." })}${fld("cfecha", "Fecha de siembra (día/mes/año)", { im: "numeric" })}${fld("cvig", "Vigencia estimada en años (opcional)", { im: "numeric", hint: "Cuántos años estima que este terreno se usará con estos cultivos (1 a 50)." })}<h3>Primer cultivo</h3>${camposCultivo()}${btn("savecy", "Iniciar ciclo")}` });

P.p28 = () => {
  const c = ciclo(S.ctx.cy);
  return { t: "Agregar cultivo", h: `${topBanner()}<div class="banner">${esc(cyLabel(c))}</div>${camposCultivo()}${btn("savecult", "Agregar al ciclo")}${btn("back", "Cancelar", "sec")}` };
};

P.p15 = () => {
  const c = ciclo(S.ctx.cy), m = finanzas(c.id);
  if (S.ctx.done) return { t: "Ciclo cerrado", back: 0, h: `<div class="banner ok">El ciclo se cerró el ${isoCorta(c.fecha_cierre)}. Ya no admite nuevos registros.</div><div class="card hl"><h3>Balance final</h3>${kv("Gastos", money(m.g))}${kv("Ingresos", money(m.i))}${kvUtilidad(m.u, money(m.u))}${kv("Rentabilidad", fmt(m.r, 1) + " %")}${kv("Utilidad por hectárea", money(m.ha))}</div>${btn("goroot:p10", "Volver al inicio")}` };
  return { t: "Cerrar ciclo", h: `${topBanner()}<div class="card"><h3>${esc(cyLabel(c))}</h3>${kv("Siembra", isoCorta(c.fecha_siembra))}${kv("Gastos", money(m.g))}${kv("Ingresos", money(m.i))}</div>${fld("cierre", "Fecha de cierre (día/mes/año)", { im: "numeric" })}${S.ctx.ask ? banner("warn", E("V-30").m, "V-30") + btn("closeyes", "Sí, cerrar ciclo") + btn("back", "Cancelar", "sec") : btn("closego", "Cerrar ciclo") + btn("back", "Cancelar", "sec")}` };
};

// ---------------------------------------------------------------- acciones
A.savefinca = (el) => ejecutar(el, async () => {
  const fn = val("fnom").trim();
  if (vLugar(fn)) { S.e.fnom = E("V-22"); return; }
  const f = await guardar("finca", { id: uuid(), nombre: fn });
  S.pila.push("p12");
  S.pantalla = "p14";
  entrar("p14", { cfinca: f.id }, DEFECTOS.p14);
  okB("Finca guardada. Ahora cree su primer ciclo.");
});
A.savearea = (el) => ejecutar(el, async () => {
  const c = ciclo(S.ctx.cy), ha = toHa();
  const nosemb = ha === null ? null : r4(ha);
  if (nosemb === null || nosemb >= c.area_bruta_ha) return fail("nosemb", "V-26");
  await guardar("ciclo", { ...c, area_no_sembrable_ha: nosemb, area_efectiva_ha: areaEfectiva(c.area_bruta_ha, nosemb) });
  S.pila.pop();
  S.pantalla = "p11";
  okB("Área efectiva guardada: " + fmt(ciclo(c.id).area_efectiva_ha, 4) + " ha.");
});
A.area = (id) => { S.ctx.cy = id; go("p13"); };
A.newcy = (id) => go("p14", { cfinca: id });
A.addcult = (id) => { S.ctx.cy = id; go("p28"); };
/** Valida el formulario del ciclo; deja los errores en S.e y devuelve la fecha de siembra leída. */
function validarCiclo(nom) {
  if (!val("cfinca")) S.e.cfinca = E("V-27");
  if (nom && vLugar(nom)) S.e.cnom = E("V-22");
  const reglas = [["carea", vAreaBruta(val("carea"))], ["cpend", vPendiente(val("cpend"))], ["cvig", vVigencia(val("cvig"))]];
  for (const [campo, e] of reglas) if (e) S.e[campo] = e;
  const f = vSiembra(val("cfecha"));
  if (f.error) S.e.cfecha = f.error;
  return f;
}

A.savecy = (el) => ejecutar(el, async () => {
  const nom = val("cnom").trim();
  const f = validarCiclo(nom);
  const cc = revisarCultivo();
  if (Object.keys(S.e).length) return;
  const bruta = parseDec(val("carea"));
  const vig = val("cvig").trim();
  const c = await guardar("ciclo", { id: uuid(), finca_id: val("cfinca"), nombre_lote: nom || null, pendiente_pct: parseDec(val("cpend")), area_bruta_ha: bruta, area_no_sembrable_ha: 0, area_efectiva_ha: bruta, fecha_siembra: f.iso, vigencia_anios: vig === "" ? null : Number(vig), estado: "ACTIVO", fecha_cierre: null });
  await guardar("ciclo_cultivo", { id: uuid(), ciclo_id: c.id, ...cc });
  S.sel = { finca: c.finca_id, ciclo: c.id };
  raiz("p10");
  okB("Ciclo iniciado. Gastos e ingresos empiezan en cero.");
});
A.savecult = (el) => ejecutar(el, async () => {
  const c = ciclo(S.ctx.cy);
  if (c.estado === "CERRADO") return badB("V-31");
  const cc = revisarCultivo(cultivosDe(c.id).map((x) => x.cultivo_codigo));
  if (Object.keys(S.e).length) return;
  await guardar("ciclo_cultivo", { id: uuid(), ciclo_id: c.id, ...cc });
  S.pila = [];
  S.sel.ciclo = c.id;
  raiz("p11");
  okB("Cultivo agregado al ciclo.");
});
A.close = (id) => { S.ctx = { cy: id }; go("p15"); };
A.fin = (id) => { S.sel.ciclo = id; raiz("p20"); };
const cerrar = async (iso) => {
  const c = ciclo(S.ctx.cy);
  await guardar("ciclo", { ...c, estado: "CERRADO", fecha_cierre: iso });
  S.ctx.done = true; S.ctx.ask = false;
};
A.closego = (el) => ejecutar(el, async () => {
  const c = ciclo(S.ctx.cy), r = vCierre(val("cierre"), c.fecha_siembra);
  if (r.error) return void (S.e.cierre = r.error);
  if (finanzas(c.id).i === 0) { S.ctx.ask = true; return; }
  await cerrar(r.iso);
});
A.closeyes = (el) => ejecutar(el, async () => {
  const c = ciclo(S.ctx.cy), r = vCierre(val("cierre"), c.fecha_siembra);
  if (r.error) return void (S.e.cierre = r.error);
  await cerrar(r.iso);
});
