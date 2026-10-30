// Catálogo y calculadora de matas (P-16 a P-19). El catálogo funciona sin internet.
import { dn, esc, fmt, ha2, money } from "../calculos/formato.js";
import { estimarCostos, matasDelCiclo, matasPorHa } from "../calculos/formulas.js";
import { cosechaFichaHtml, proyeccionHtml } from "./cosecha.js";
import { E, vDistancia } from "../calculos/validaciones.js";
import { D, S, ciclo, cultivo, misCiclos } from "../estado.js";
import { cyLabel } from "./panel.js";
import { A, P, btn, err1, fail, fld, go, kv, ejecutar, seg, topBanner, val } from "../ui.js";
import { cultOpts } from "./fincas.js";
import { parseDec } from "../calculos/formato.js";

const NOMBRE_MARCOS = "Cuadrado, rectangular, tresbolillo";
const GENERICA_MENOR = "Las matas quedan muy juntas: compiten por luz, agua y nutrientes, y la producción puede bajar.";
const GENERICA_MAYOR = "Las matas quedan muy separadas: se desaprovecha el terreno y baja la producción por hectárea.";

/** P-16 Catálogo: los cultivos disponibles, sin necesidad de internet. */
P.p16 = () => ({ t: "Catálogo", back: 0, nav: 4, h: `<p class="muted">Tres cultivos del norte del Cauca, disponibles sin internet.</p>` + D.catalogo.map((c) => `<div class="fila"><button class="tap" data-act="cult:${c.codigo}"><span class="grow"><b>${esc(c.nombre)}</b><span class="muted" style="display:block">Unidad: ${esc(c.unidad_comercial)}</span></span><span aria-hidden="true">›</span></button></div>`).join("") });

/** Ficha de un cultivo: unidad comercial, distancias recomendadas, marcos permitidos, costos de referencia y fuente. */
const fichaHtml = (c) => {
  const f = c.ficha_tecnica;
  if (!f) return "";
  const dudoso = (f.datos_extra?.estado || "").startsWith("POR_");
  return `<div class="card"><h3>Costos de referencia por ${fmt(f.base_plantas)} plantas</h3>${kv("Hoyado (por planta)", money(f.costo_hoyado_cop))}${kv("Colino (por planta)", money(f.costo_colino_cop))}${kv("Insumos al año (por planta)", money(f.insumo_anual_cop))}${kv("Jornales de limpieza al año", dn(f.jornales_limpieza_anio))}${kv("Jornales de riego al año", dn(f.jornales_riego_anio))}${dudoso ? '<div class="alert alert-warning">Valores por validar con una fuente técnica.</div>' : ""}</div>`;
};

/** P-17 Detalle de un cultivo: su ficha y su cosecha de referencia. */
P.p17 = () => {
  const c = cultivo(S.ctx.cult) || D.catalogo[0];
  const mn = c.distancia_min_m, mx = c.distancia_max_m;
  const fila = (d) => kv(`${fmt(d, 1)} × ${fmt(d, 1)} m`, fmt(matasPorHa("cuadrado", d), 2) + " matas/ha");
  return { t: c.nombre, h: `<div class="card"><h3>Ficha técnica</h3>${kv("Distancia recomendada", `${fmt(mn, 1)} a ${fmt(mx, 1)} m`)}${kv("Marcos", NOMBRE_MARCOS)}${kv("Unidad comercial", esc(c.unidad_comercial))}</div><div class="card"><h3>Densidad esperada (cuadrado)</h3>${fila(mn)}${fila((mn + mx) / 2)}${fila(mx)}</div>${fichaHtml(c)}${cosechaFichaHtml(c)}<p class="muted">Fuente: ${esc(c.fuente_tecnica)}.</p>${btn("tocalc:" + c.codigo, "Calcular matas")}` };
};

/** P-18 Calcular matas: cultivo, ciclo opcional, marco de siembra y distancias. */
P.p18 = () => {
  const m = val("cmarco");
  return { t: "Calcular matas", nav: 2, back: 0, h: `${topBanner()}${fld("cciclo", "Ciclo", { opts: [["", "Sin ciclo (solo por hectárea)"], ...misCiclos().map((c) => [c.id, cyLabel(c) + " (" + ha2(c.area_efectiva_ha) + ")"])] })}${fld("ccu", "Cultivo", { opts: cultOpts() })}<label>Marco de siembra</label>${seg("cmarco", [["cuadrado", "Cuadrado"], ["rectangular", "Rectangular"], ["tresbolillo", "Tresbolillo"]])}${err1("cmarco")}${m ? fld("cda", m === "rectangular" ? "Distancia entre surcos (m)" : "Distancia entre matas (m)", { im: "decimal" }) : ""}${m === "rectangular" ? fld("cdb", "Distancia entre matas (m)", { im: "decimal" }) : ""}${btn("calc", "Calcular")}` };
};

/** P-19 Resultado: matas por hectárea y del ciclo (hacia arriba), aviso de distancia, costos y proyección de cosecha. */
P.p19 = () => {
  const r = S.ctx.res;
  const warn = r.warn ? `<div class="alert alert-warning" role="alert">${esc(r.warn)} <span class="muted">(V-34)</span><br>${esc(r.efecto)}</div>` : "";
  return { t: "Resultado", nav: 2, h: `<div class="card hl"><h3>${esc(r.titulo)}</h3>${kv("Matas por hectárea", fmt(r.ha, 2))}${r.ef != null ? kv("Área efectiva", ha2(r.ef)) + kv("Matas en el ciclo", fmt(r.lote)) : ""}</div>${warn}${r.est ? `<div class="card"><h3>Costos aproximados (ficha técnica)</h3>${kv("Siembra inicial", money(r.est.siembra))}${kv("Insumos por año", money(r.est.insumos))}${kv("Jornales por año", dn(r.est.jornales))}${r.estDudoso ? '<div class="muted">Valores de la ficha por validar.</div>' : ""}</div>` : ""}${r.cultivo ? proyeccionHtml(r.cultivo, r.ef != null ? r.lote : r.ha, r.siembra, r.ef != null ? "Proyección de cosecha del ciclo" : "Proyección de cosecha por hectárea") : ""}${btn("usecy", "Usar en un ciclo")}${btn("go:p18", "Calcular otra vez", "sec")}` };
};

/** Abrir el detalle de un cultivo. */
A.cult = (c) => { S.ctx.cult = c; go("p17"); };
/** Abrir la calculadora con el cultivo ya elegido. */
A.tocalc = (c) => go("p18", { ccu: c });
/** Valida marco y distancias antes de calcular. */
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

/** Datos del ciclo elegido que usa el cálculo: área efectiva, matas del ciclo (redondeadas hacia arriba) y fecha de siembra.
 *  Sin ciclo (cálculo libre) solo se muestran las matas por hectárea. */
function datosDelCiclo(m, da, db, l) {
  if (!l) return { ef: null, lote: null, siembra: null };
  return { ef: l.area_efectiva_ha, lote: matasDelCiclo(m, da, db, l.area_efectiva_ha), siembra: l.fecha_siembra };
}

/** Título del resultado, por ejemplo "Café · tresbolillo 2 m" o "Yuca · rectangular 1 × 0,8 m". */
function tituloDelCalculo(m, da, db, c) {
  const medidas = m === "rectangular" ? `${dn(da)} × ${dn(db)} m` : `${dn(da)} m`;
  return `${c ? c.nombre : "Cultivo sin elegir"} · ${m} ${medidas}`;
}

/** Arma el resultado de P-19: matas por hectárea, matas del ciclo, aviso si la distancia sale del rango del cultivo
 *  y costos estimados con la ficha técnica (marcados "por validar" si la ficha aún no está validada). */
function resultadoDelCalculo(m, da, db, l, c) {
  const res = { ha: matasPorHa(m, da, db), ...datosDelCiclo(m, da, db, l), cultivo: c || null, titulo: tituloDelCalculo(m, da, db, c),
    input: { ccult: val("ccu"), marco: m, ca: val("cda"), cb: val("cdb") } };
  if (!c) return res;
  Object.assign(res, avisoDeDistancia(c, m === "rectangular" ? [da, db] : [da]));
  if (c.ficha_tecnica && res.lote != null) {
    res.est = estimarCostos(c.ficha_tecnica, res.lote);
    res.estDudoso = (c.ficha_tecnica.datos_extra?.estado || "").startsWith("POR_");
  }
  return res;
}

/** Calcular y mostrar el resultado. */
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
/** Crear un ciclo con los datos del cálculo ya llenos. */
A.usecy = () => go("p14", S.ctx.res.input ? { ccult: S.ctx.res.input.ccult, marco: S.ctx.res.input.marco, ca: S.ctx.res.input.ca, cb: S.ctx.res.input.cb } : {});
