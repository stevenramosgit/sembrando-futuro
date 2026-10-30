// Fórmulas del dominio (RF-13, RF-18, RF-24, RF-25, RF-28). Son las mismas del servidor (backend/app/domain/formulas.py).
import { rhu, sumarAnios, sumarMeses, techo } from "./formato.js";

export const K_TRESBOLILLO = 0.866025;
export const PLAZA_HA = 0.64;
/** Redondea a 4 decimales (precisión de las áreas en hectáreas). */
const r4 = (x) => Math.round(x * 1e4) / 1e4;

/** Convierte un área a hectáreas: m² ÷ 10.000; una plaza (medida tradicional del Cauca) son 0,64 ha. */
export function aHectareas(valor, unidad) {
  return unidad === "m2" ? valor / 1e4 : unidad === "plaza" ? valor * PLAZA_HA : valor;
}
/** Área efectiva = área bruta − área no sembrable, en hectáreas (RF-13). */
export const areaEfectiva = (bruta, noSembrable) => r4(r4(bruta) - r4(noSembrable));

// Matas: cuentas exactas con enteros (BigInt): distancias en centímetros, área en diezmilésimas de hectárea y el factor del
// tresbolillo (0,866025) como 866025/10^6. El resultado siempre se redondea hacia arriba: no existe media mata.
const cm = (x) => BigInt(Math.round(x * 100));
/** División entera redondeada hacia arriba con BigInt: techoDiv(7, 2) = 4. */
const techoDiv = (n, d) => (n + d - 1n) / d;
/** Matas por hectárea como fracción exacta [numerador, denominador]. */
function matasExactas(marco, a, b) {
  const A = cm(a);
  if (marco === "cuadrado") return [100000000n, A * A];
  if (marco === "rectangular") return [100000000n, A * cm(b)];
  return [100000000000000n, A * A * 866025n];
}
/** Matas por hectárea, hacia arriba con dos decimales (4.444,444… → 4.444,45). */
export function matasPorHa(marco, a, b) {
  const [n, d] = matasExactas(marco, a, b);
  return Number(techoDiv(n * 100n, d)) / 100;
}
/** Matas del ciclo: matas por hectárea exactas × área efectiva, hacia arriba. */
export function matasDelCiclo(marco, a, b, areaEfectivaHa) {
  const [n, d] = matasExactas(marco, a, b);
  return Number(techoDiv(n * BigInt(Math.round(areaEfectivaHa * 1e4)), d * 10000n));
}
/** Matas de un lote a partir de matas por hectárea ya calculadas, hacia arriba. Para un resultado exacto use matasDelCiclo. */
export const matasPorLote = (porHa, areaEfectivaHa) => Number(techoDiv(BigInt(Math.round(porHa * 100)) * BigInt(Math.round(areaEfectivaHa * 1e4)), 1000000n));
/** Costo de un registro de jornales = cantidad × valor del jornal, redondeado al peso (RF-24). */
export const costoJornal = (n, valor) => rhu(n * valor);
/** Total de una venta = cantidad × precio unitario, redondeado al peso (RF-25). */
export const totalIngreso = (q, precio) => rhu(q * precio);

/** RF-28: gastos incluye los jornales (cada registro ya redondeado al peso). */
export function calcularUtilidad(gastos, ingresos, area) {
  const g = gastos.reduce((s, x) => s + x, 0);
  const i = ingresos.reduce((s, x) => s + x, 0);
  const u = i - g;
  const rent = g === 0 ? 0 : Math.round((u / g) * 1000 + (u < 0 ? -1e-9 : 1e-9)) / 10;
  const porHa = area > 0 ? rhu(u / area) : 0;
  return { gastos: g, ingresos: i, utilidad: u, rentabilidad: rent, porHa };
}

// ---- vigencia del ciclo (modelo simplificado): igual que backend/app/domain/formulas.py
const DIA_MS = 86400000;
/** Días entre dos fechas AAAA-MM-DD. */
const dias = (a, b) => Math.round((Date.parse(b + "T00:00:00Z") - Date.parse(a + "T00:00:00Z")) / DIA_MS);
/** Fecha estimada de fin del ciclo: siembra + años de vigencia (null si el ciclo no tiene vigencia). */
export const fechaFinEstimada = (siembra, vigencia) => (vigencia == null ? null : sumarAnios(siembra, Number(vigencia)));

/** {fin, restantes, semaforo}: VERDE si falta más del 50 %, AMARILLO entre 20 % y 50 %, ROJO si falta menos del 20 % o ya se cumplió. */
export function semaforoVigencia(siembra, vigencia, hoy) {
  const fin = fechaFinEstimada(siembra, vigencia);
  if (fin === null) return { fin: null, restantes: null, semaforo: null };
  const total = dias(siembra, fin), faltan = dias(hoy, fin);
  const restantes = Math.round((Math.max(faltan, 0) / 365.25) * 10) / 10;
  const semaforo = faltan <= 0 || faltan < 0.2 * total ? "ROJO" : faltan <= 0.5 * total ? "AMARILLO" : "VERDE";
  return { fin, restantes, semaforo };
}

/** Costos aproximados con la ficha técnica del cultivo (valores por planta; jornales por cada base_plantas al año). */
export function estimarCostos(ficha, matas) {
  return {
    siembra: rhu(matas * (ficha.costo_hoyado_cop + ficha.costo_colino_cop)),
    insumos: rhu(matas * ficha.insumo_anual_cop),
    jornales: techo((matas / ficha.base_plantas) * (ficha.jornales_limpieza_anio + ficha.jornales_riego_anio), 2),
  };
}

/** Proyección orientativa de la cosecha de un cultivo del ciclo; null si la ficha no trae los datos. Igual que el servidor. */
export function proyectarCosecha(ficha, matas, siembra) {
  if (ficha.meses_primera_cosecha == null || ficha.produccion_base == null) return null;
  const produccion = techo((matas / ficha.base_plantas) * ficha.produccion_base, 2);
  return {
    meses: ficha.meses_primera_cosecha, primeraCosecha: siembra ? sumarMeses(siembra, ficha.meses_primera_cosecha) : null, temporadas: ficha.meses_cosecha || null, unica: !!ficha.cosecha_unica,
    produccion, precio: ficha.precio_ref_cop ?? null, precioFecha: ficha.precio_ref_fecha || null,
    ingreso: ficha.precio_ref_cop == null ? null : rhu(produccion * ficha.precio_ref_cop),
  };
}
