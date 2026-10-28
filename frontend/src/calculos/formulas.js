// Fórmulas del dominio (RF-13, RF-18, RF-24, RF-25, RF-28). Son las mismas del servidor (backend/app/domain/formulas.py).
import { rhu, sumarAnios } from "./formato.js";

export const K_TRESBOLILLO = 0.866025;
export const PLAZA_HA = 0.64;
const r4 = (x) => Math.round(x * 1e4) / 1e4;

export function aHectareas(valor, unidad) {
  return unidad === "m2" ? valor / 1e4 : unidad === "plaza" ? valor * PLAZA_HA : valor;
}
export const areaEfectiva = (bruta, noSembrable) => r4(r4(bruta) - r4(noSembrable));

export function matasPorHa(marco, a, b) {
  return marco === "cuadrado" ? 10000 / (a * a) : marco === "rectangular" ? 10000 / (a * b) : 10000 / (a * a * K_TRESBOLILLO);
}
export const matasPorLote = (porHa, areaEfectivaHa) => rhu(Math.round(porHa * 100) / 100 * areaEfectivaHa);
export const costoJornal = (n, valor) => rhu(n * valor);
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
const dias = (a, b) => Math.round((Date.parse(b + "T00:00:00Z") - Date.parse(a + "T00:00:00Z")) / DIA_MS);
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
    jornales: Math.round((matas / ficha.base_plantas) * (ficha.jornales_limpieza_anio + ficha.jornales_riego_anio) * 10 + 1e-9) / 10,
  };
}
