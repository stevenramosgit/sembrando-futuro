// Proyección de cosecha (ficha técnica): cuándo empieza a producir, en qué meses se cosecha y cuánto se espera producir y ganar.
// Es una estimación orientativa con los datos de la ficha (precio de referencia en pesos colombianos), no una promesa de venta.
import { dn, esc, fmt, mesAnio, money, temporadas } from "../calculos/formato.js";
import { proyectarCosecha } from "../calculos/formulas.js";
import { kv } from "../ui.js";

/** Unidad comercial sin la explicación entre paréntesis: «carga (125 kg …)» → «carga». */
const unidadCorta = (u) => u.split("(")[0].trim();
/** Plural sencillo de la unidad: 1 carga, 2 cargas. */
const plural = (u, n) => (n === 1 ? u : u + "s");
/** Evita que un valor (número y unidad) se parta en dos líneas. */
const nw = (s) => `<span class="nw">${s}</span>`;
/** Fecha del precio de referencia como día/mes/año. */
export const fechaPrecio = (iso) => iso.split("-").reverse().join("/");

/** Texto de la época de cosecha: una sola vez (yuca, plátano), los meses de temporada (café) o todo el año. */
const epocaDeCosecha = (unica, meses) => {
  if (unica) return "Una sola vez por siembra";
  return meses ? temporadas(meses) : "Todo el año";
};

/** Filas de producción e ingreso estimados; el ingreso solo aparece si la ficha tiene precio de referencia. */
function filasDeProduccion(p, u) {
  const produccion = kv(p.unica ? "Producción estimada" : "Producción estimada por año", nw(`${fmt(p.produccion, 2)} ${plural(u, p.produccion)}`));
  if (p.ingreso == null) return produccion;
  return produccion + kv(p.unica ? "Ingreso estimado" : "Ingreso estimado por año", nw(money(p.ingreso)));
}

/** Frase que dice con qué precio (y de qué fecha) se calculó el ingreso. */
function notaDelPrecio(p, u) {
  if (p.precio == null) return "";
  const fecha = p.precioFecha ? ` (${fechaPrecio(p.precioFecha)})` : "";
  return `Con el precio de referencia de ${nw(money(p.precio))} por ${esc(u)}${fecha}. `;
}

/** Tarjeta con la proyección de un cultivo. 'siembra' es la fecha de siembra del ciclo; sin ella (calculadora sin ciclo) se muestran los meses
 *  desde la siembra y las cantidades son por hectárea. Devuelve "" si la ficha no trae datos de cosecha. */
export function proyeccionHtml(cu, matas, siembra, titulo) {
  const f = cu.ficha_tecnica;
  const p = f && matas != null ? proyectarCosecha(f, matas, siembra) : null;
  if (!p) return "";
  const u = unidadCorta(cu.unidad_comercial);
  const cuando = p.primeraCosecha ? mesAnio(p.primeraCosecha) : `unos ${p.meses} meses después de sembrar`;
  const dudoso = (f.datos_extra?.estado_proyeccion || "").startsWith("POR_");
  const filas = kv("Primera cosecha", cuando) + kv("Época de cosecha", epocaDeCosecha(p.unica, p.temporadas)) + filasDeProduccion(p, u);
  const aviso = dudoso ? '<div class="alert alert-warning mt-2">Datos por validar con una fuente técnica.</div>' : "";
  return `<div class="card"><h3>${esc(titulo)}</h3>${filas}<div class="muted">${notaDelPrecio(p, u)}Es una estimación orientativa: el rendimiento y el precio cambian con el clima, el manejo y el mercado.</div>${aviso}</div>`;
}

/** Datos de cosecha de la ficha de un cultivo en el catálogo (P-17): sin cálculos, solo lo que dice la ficha. */
export function cosechaFichaHtml(cu) {
  const f = cu.ficha_tecnica;
  if (!f || f.meses_primera_cosecha == null) return "";
  const u = unidadCorta(cu.unidad_comercial);
  const produccion = f.produccion_base == null ? ""
    : kv(`Producción por ${fmt(f.base_plantas)} plantas`, nw(`${dn(f.produccion_base)} ${plural(u, f.produccion_base)}${f.cosecha_unica ? "" : " al año"}`));
  const precio = f.precio_ref_cop == null ? "" : kv(`Precio de referencia por ${esc(u)}`, nw(money(f.precio_ref_cop)));
  const fecha = f.precio_ref_fecha ? "Precio del " + fechaPrecio(f.precio_ref_fecha) + ". " : "";
  return `<div class="card"><h3>Cosecha de referencia</h3>${kv("Primera cosecha", `${f.meses_primera_cosecha} meses después de sembrar`)}`
    + `${kv("Época de cosecha", epocaDeCosecha(f.cosecha_unica, f.meses_cosecha))}${produccion}${precio}`
    + `<div class="muted">${fecha}${esc(f.datos_extra?.temporada || "")}</div></div>`;
}
