// Catálogo y calculadora de matas (P-16 a P-19). El catálogo funciona sin internet.
import { dn, esc, fmt, money } from "../calculos/formato.js";
import { estimarCostos, matasPorHa, matasPorLote } from "../calculos/formulas.js";
import { E, vDistancia } from "../calculos/validaciones.js";
import { D, S, ciclo, cultivo, misCiclos } from "../estado.js";
import { cyLabel } from "./panel.js";
import { A, P, btn, err1, fail, fld, go, kv, ejecutar, seg, topBanner, val } from "../ui.js";
import { cultOpts } from "./fincas.js";
import { parseDec } from "../calculos/formato.js";

const NOMBRE_MARCOS = "Cuadrado, rectangular, tresbolillo";
const GENERICA_MENOR = "Las matas quedan muy juntas: compiten por luz, agua y nutrientes, y la producción puede bajar.";
const GENERICA_MAYOR = "Las matas quedan muy separadas: se desaprovecha el terreno y baja la producción por hectárea.";

P.p16 = () => ({ t: "Catálogo", back: 0, nav: 4, h: `<p class="muted">Tres cultivos del norte del Cauca, disponibles sin internet.</p>` + D.catalogo.map((c) => `<div class="row"><button class="tap" data-act="cult:${c.codigo}"><span class="grow"><b>${esc(c.nombre)}</b><span class="muted" style="display:block">Unidad: ${esc(c.unidad_comercial)}</span></span><span aria-hidden="true">›</span></button></div>`).join("") });

const fichaHtml = (c) => {
  const f = c.ficha_tecnica;
  if (!f) return "";
  const dudoso = (f.datos_extra?.estado || "").startsWith("POR_");
  return `<div class="card"><h3>Costos de referencia por ${fmt(f.base_plantas)} plantas</h3>${kv("Hoyado (por planta)", money(f.costo_hoyado_cop))}${kv("Colino (por planta)", money(f.costo_colino_cop))}${kv("Insumos al año (por planta)", money(f.insumo_anual_cop))}${kv("Jornales de limpieza al año", dn(f.jornales_limpieza_anio))}${kv("Jornales de riego al año", dn(f.jornales_riego_anio))}${dudoso ? '<div class="banner warn">Valores por validar con una fuente técnica.</div>' : ""}</div>`;
};

P.p17 = () => {
  const c = cultivo(S.ctx.cult) || D.catalogo[0];
  const mn = c.distancia_min_m, mx = c.distancia_max_m;
  const fila = (d) => kv(`${fmt(d, 1)} × ${fmt(d, 1)} m`, fmt(matasPorHa("cuadrado", d), 0) + " matas/ha");
  return { t: c.nombre, h: `<div class="card"><h3>Ficha técnica</h3>${kv("Distancia recomendada", `${fmt(mn, 1)} a ${fmt(mx, 1)} m`)}${kv("Marcos", NOMBRE_MARCOS)}${kv("Unidad comercial", esc(c.unidad_comercial))}</div><div class="card"><h3>Densidad esperada (cuadrado)</h3>${fila(mn)}${fila((mn + mx) / 2)}${fila(mx)}</div>${fichaHtml(c)}<p class="muted">Fuente: ${esc(c.fuente_tecnica)}.</p>${btn("tocalc:" + c.codigo, "Calcular matas")}` };
};

P.p18 = () => {
  const m = val("cmarco");
  return { t: "Calcular matas", nav: 2, back: 0, h: `${topBanner()}${fld("cciclo", "Ciclo", { opts: [["", "Sin ciclo (solo por hectárea)"], ...misCiclos().map((c) => [c.id, cyLabel(c) + " (" + fmt(c.area_efectiva_ha, 4) + " ha)"])] })}${fld("ccu", "Cultivo", { opts: cultOpts() })}<label>Marco de siembra</label>${seg("cmarco", [["cuadrado", "Cuadrado"], ["rectangular", "Rectangular"], ["tresbolillo", "Tresbolillo"]])}${err1("cmarco")}${m ? fld("cda", m === "rectangular" ? "Distancia entre surcos (m)" : "Distancia entre matas (m)", { im: "decimal" }) : ""}${m === "rectangular" ? fld("cdb", "Distancia entre matas (m)", { im: "decimal" }) : ""}${btn("calc", "Calcular")}` };
};

P.p19 = () => {
  const r = S.ctx.res;
  const warn = r.warn ? `<div class="banner warn" role="alert">${esc(r.warn)} <span class="muted">(V-34)</span><br>${esc(r.efecto)}</div>` : "";
  return { t: "Resultado", nav: 2, h: `<div class="card hl"><h3>${esc(r.titulo)}</h3>${kv("Matas por hectárea", fmt(r.ha, 2))}${r.ef != null ? kv("Área efectiva", fmt(r.ef, 4) + " ha") + kv("Matas en el ciclo", fmt(r.lote)) : ""}</div>${warn}${r.est ? `<div class="card"><h3>Costos aproximados (ficha técnica)</h3>${kv("Siembra inicial", money(r.est.siembra))}${kv("Insumos por año", money(r.est.insumos))}${kv("Jornales por año", dn(r.est.jornales))}${r.estDudoso ? '<div class="muted">Valores de la ficha por validar.</div>' : ""}</div>` : ""}${btn("usecy", "Usar en un ciclo")}${btn("go:p18", "Calcular otra vez", "sec")}` };
};

A.cult = (c) => { S.ctx.cult = c; go("p17"); };
A.tocalc = (c) => go("p18", { ccu: c });
function validarCalculo(m) {
  if (!m) { fail("cmarco", "V-32"); return; }
  const ea = vDistancia(val("cda"));
  if (ea) S.e.cda = ea;
  const eb = m === "rectangular" ? vDistancia(val("cdb")) : null;
  if (eb) S.e.cdb = eb;
}

/** Aviso cuando las distancias quedan fuera del rango técnico del cultivo; null si están dentro. */
function avisoDeDistancia(c, ds) {
  const lo = ds.some((d) => d < c.distancia_min_m), hi = ds.some((d) => d > c.distancia_max_m);
  if (!lo && !hi) return null;
  return {
    warn: E("V-34", { r: `(${fmt(c.distancia_min_m, 1)}–${fmt(c.distancia_max_m, 1)} m)` }).m,
    efecto: lo ? c.advertencia_menor || GENERICA_MENOR : c.advertencia_mayor || GENERICA_MAYOR,
  };
}

function resultadoDelCalculo(m, da, db, l, c) {
  const ha = Math.round(matasPorHa(m, da, db) * 100) / 100;
  const res = { ha, ef: l ? l.area_efectiva_ha : null, lote: l ? matasPorLote(ha, l.area_efectiva_ha) : null,
    titulo: `${c ? c.nombre : "Cultivo sin elegir"} · ${m} ${dn(da)}${m === "rectangular" ? " × " + dn(db) + " m" : " m"}`,
    input: { ccult: val("ccu"), marco: m, ca: val("cda"), cb: val("cdb") } };
  if (!c) return res;
  Object.assign(res, avisoDeDistancia(c, m === "rectangular" ? [da, db] : [da]));
  if (c.ficha_tecnica && res.lote != null) {
    res.est = estimarCostos(c.ficha_tecnica, res.lote);
    res.estDudoso = (c.ficha_tecnica.datos_extra?.estado || "").startsWith("POR_");
  }
  return res;
}

A.calc = (el) => ejecutar(el, async () => {
  const m = val("cmarco");
  validarCalculo(m);
  if (Object.keys(S.e).length) return;
  const da = parseDec(val("cda")), db = m === "rectangular" ? parseDec(val("cdb")) : null;
  const l = val("cciclo") ? ciclo(val("cciclo")) : null, c = val("ccu") ? cultivo(val("ccu")) : null;
  S.ctx.res = resultadoDelCalculo(m, da, db, l, c);
  S.pila.push("p18");
  S.pantalla = "p19";
});
A.usecy = () => go("p14", S.ctx.res.input ? { ccult: S.ctx.res.input.ccult, marco: S.ctx.res.input.marco, ca: S.ctx.res.input.ca, cb: S.ctx.res.input.cb } : {});
