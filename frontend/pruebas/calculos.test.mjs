// Pruebas del cálculo y de las reglas V-xx del dispositivo. Los valores esperados son los mismos de los documentos 14 y 22 y de las pruebas del servidor.
import test from "node:test";
import assert from "node:assert/strict";
import { areaEfectiva, aHectareas, calcularUtilidad, costoJornal, estimarCostos, fechaFinEstimada, semaforoVigencia, matasPorHa, matasPorLote, totalIngreso } from "../src/calculos/formulas.js";
import { fmt, hoyISO, isoAEs, money, parseDec, parseFechaEs, rhu, unAnioDespues } from "../src/calculos/formato.js";
import * as v from "../src/calculos/validaciones.js";
import { MENSAJES } from "../src/datos/mensajes.js";
import { SEMILLA } from "../src/datos/semilla_catalogo.js";

const r2 = (x) => Math.round(x * 100) / 100;

test("matas por hectárea (CB-04 a CB-08)", () => {
  assert.equal(r2(matasPorHa("rectangular", 1.0, 1.5)), 6666.67);
  assert.equal(r2(matasPorHa("cuadrado", 1.5)), 4444.44);
  assert.equal(r2(matasPorHa("tresbolillo", 1.5)), 5132.0);
  assert.equal(r2(matasPorHa("cuadrado", 2.5)), 1600.0);
});
test("matas del lote redondea la mitad hacia arriba (CB-05 con 0,9 ha)", () => {
  assert.equal(matasPorLote(4444.44, 0.9), 4000);
  assert.equal(matasPorLote(1600, 0.5), 800);
  assert.equal(rhu(2.5), 3);
  assert.equal(rhu(-2.5), -3);
});
test("área efectiva y conversión de unidades (RF-13)", () => {
  assert.equal(areaEfectiva(1.0, 0.1), 0.9);
  assert.equal(aHectareas(1000, "m2"), 0.1);
  assert.equal(aHectareas(1, "plaza"), 0.64);
  assert.equal(aHectareas(2, "ha"), 2);
});
test("costos por registro (RF-24, RF-25)", () => {
  assert.equal(costoJornal(2, 25000), 50000);
  assert.equal(costoJornal(0.5, 33333), 16667);
  assert.equal(totalIngreso(4, 125000), 500000);
  assert.equal(totalIngreso(0.1, 15), 2);
});
test("utilidad (CB-25 a CB-28)", () => {
  const u = (g, i, a) => { const r = calcularUtilidad(g, i, a); return [r.gastos, r.ingresos, r.utilidad, r.rentabilidad, r.porHa]; };
  assert.deepEqual(u([], [], 0.9), [0, 0, 0, 0, 0]);
  assert.deepEqual(u([], [500000], 0.9), [0, 500000, 500000, 0, 555556]);
  assert.deepEqual(u([100000, 30000, 20000], [500000], 0.9), [150000, 500000, 350000, 233.3, 388889]);
  assert.deepEqual(u([120000, 80000], [50000], 0.9), [200000, 50000, -150000, -75, -166667]);
});
test("formato colombiano", () => {
  assert.equal(fmt(1234567.891, 2), "1.234.567,89");
  assert.equal(money(500000), "$ 500.000");
  assert.equal(fmt(-0.04, 1), "0,0");
  assert.equal(isoAEs("2026-03-15"), "15/03/2026");
});
test("fechas: día/mes/año, hoy en Colombia y límites", () => {
  assert.equal(parseFechaEs("15/03/2026"), "2026-03-15");
  assert.equal(parseFechaEs("31/02/2026"), null);
  assert.equal(parseFechaEs("2026-03-15"), null);
  assert.equal(hoyISO(Date.UTC(2026, 9, 27, 3, 0)), "2026-10-26"); // 03:00 UTC = 22:00 del día anterior en Colombia
  assert.equal(unAnioDespues("2026-02-28"), "2027-02-28");
  assert.equal(unAnioDespues("2028-02-29"), "2029-02-28");
});
test("números escritos con coma o punto", () => {
  assert.equal(parseDec("1,5"), 1.5);
  assert.equal(parseDec("1.5"), 1.5);
  assert.equal(parseDec("1,5,2"), null);
  assert.equal(parseDec("abc"), null);
});

const pares = [
  ["V-01", v.vNombre, "María Pérez", "aaaaa"], ["V-02", v.vUbicacion, "Caloto, Cauca", "0"], ["V-03", v.vCorreo, "Maria@Correo.com", "0@0"],
  ["V-09", v.vCodigoOtp, "482915", "48A"], ["V-22", v.vLugar, "La Esperanza", "x"], ["V-24", v.vAreaBruta, "1,5", "0"],
  ["V-25", v.vPendiente, "12", "101"], ["V-33", v.vDistancia, "1,5", "0"], ["V-35", v.vValorGasto, "50000000", "50000001"],
  ["V-36", v.vValorGasto, "100", "cien"], ["V-38", v.vObservaciones, "Abono orgánico", "Abono <b>"], ["V-39", v.vJornales, "0,5", "0,3"],
  ["V-40", v.vValorJornal, "25000", "0"], ["V-41", v.vCantidad, "0,1", "0,09"], ["V-42", v.vPrecio, "1", "0"],
];
for (const [codigo, f, bueno, malo] of pares) {
  test(`regla ${codigo}`, () => {
    assert.equal(f(bueno), null);
    assert.equal(f(malo).c, codigo);
  });
}
test("clave V-07", () => {
  for (const ok of ["Siembra#2026a", "Cafe#Cauca2026", "Aa1!kLmPq9z"]) assert.equal(v.vClave(ok), null, ok);
  for (const mal of ["corta1A!", "sinmayuscula1!", "SINMINUSCULA1!", "SinNumero!!ab", "SinSimbolo123a", "Con espacio1A!", "Tildeé1A!!!!", "Aaaaa1!bcdef", "Abcdef1!ghij"]) assert.equal(v.vClave(mal)?.c, "V-07", mal);
  assert.equal(v.vClave("Maria.perez1!X", "maria.perez@correo.com")?.c, "V-07");
});
test("fechas V-28, V-29, V-47 y V-48", () => {
  assert.equal(v.vSiembra("15/03/2026").iso, "2026-03-15");
  assert.equal(v.vSiembra("15/03/2019").error.c, "V-48");
  assert.equal(v.vSiembra("hoy").error.c, "V-28");
  assert.equal(v.vCierre("14/03/2026", "2026-03-15").error.c, "V-29");
  assert.equal(v.vFechaRegistro("14/03/2026", "2026-03-15").error.c, "V-47");
  assert.equal(v.vFechaRegistro("15/03/2026", "2026-03-15").iso, "2026-03-15");
});
test("mensajes: las reglas V-01 a V-50 existen (V-23 está retirada) y V-34 trae el rango", () => {
  for (let n = 1; n <= 50; n++) if (n !== 23) assert.ok(MENSAJES["V-" + String(n).padStart(2, "0")]);
  assert.match(v.msg("V-34", { r: "(1,0–2,0 m)" }), /\(1,0–2,0 m\)/);
  assert.match(v.msg("V-10", { n: 3 }), /Le quedan 3 intentos/);
  assert.match(v.msg("V-18", { t: "14:30" }), /14:30/);
});
test("catálogo semilla: 3 cultivos con rango, marcos y ficha técnica (documento 19)", () => {
  assert.deepEqual(SEMILLA.cultivos.map((c) => c.codigo).sort(), ["CAFE", "PLATANO", "YUCA"]);
  for (const c of SEMILLA.cultivos) {
    assert.ok(c.distancia_min_m < c.distancia_max_m && c.marcos_permitidos.length);
    assert.ok(c.ficha_tecnica.base_plantas > 0);
  }
  const cafe = SEMILLA.cultivos.find((c) => c.codigo === "CAFE").ficha_tecnica;
  assert.deepEqual([cafe.costo_hoyado_cop, cafe.costo_colino_cop, cafe.insumo_anual_cop], [300, 100, 830]);
});
test("regla V-49: vigencia en años de 1 a 50, opcional", () => {
  for (const ok of ["", " ", "1", "7", "50"]) assert.equal(v.vVigencia(ok), null, ok);
  for (const mal of ["0", "51", "2,5", "abc", "-1"]) assert.equal(v.vVigencia(mal)?.c, "V-49", mal);
});
test("fin estimado y semáforo de vigencia (siembra 15/03/2026, 7 años)", () => {
  assert.equal(fechaFinEstimada("2026-03-15", 7), "2033-03-15");
  assert.equal(fechaFinEstimada("2026-03-15", null), null);
  const s = (hoy) => semaforoVigencia("2026-03-15", 7, hoy);
  assert.equal(s("2026-10-27").semaforo, "VERDE");
  assert.equal(s("2031-03-15").semaforo, "AMARILLO");
  assert.equal(s("2031-03-15").restantes, 2);
  assert.equal(s("2032-06-01").semaforo, "ROJO");
  assert.equal(s("2035-01-01").restantes, 0);
  assert.deepEqual(semaforoVigencia("2026-03-15", null, "2026-10-27"), { fin: null, restantes: null, semaforo: null });
});
test("costos aproximados con la ficha del café (por 1.000 plantas)", () => {
  const f = SEMILLA.cultivos.find((c) => c.codigo === "CAFE").ficha_tecnica;
  assert.deepEqual(estimarCostos(f, 1000), { siembra: 400000, insumos: 830000, jornales: 7 });
  assert.deepEqual(estimarCostos(f, 4000), { siembra: 1600000, insumos: 3320000, jornales: 28 });
});
