// Plan de pruebas (documento 14): casos de cálculo que también se ejecutan en el dispositivo (parte «cli»).
// Cada prueba deja lo que observó en resultados_plan_cli.json.
import test from "node:test";
import assert from "node:assert/strict";
import { createRequire } from "node:module";
import { areaEfectiva, aHectareas, calcularUtilidad, costoJornal, estimarCostos, matasDelCiclo, matasPorHa, matasPorLote, semaforoVigencia, totalIngreso } from "../src/calculos/formulas.js";
import { money } from "../src/calculos/formato.js";
import * as v from "../src/calculos/validaciones.js";
import { SEMILLA } from "../src/datos/semilla_catalogo.js";

const registro = createRequire(import.meta.url)("./registro_plan.cjs").abrir("cli");
if (process.env.REINICIAR_PLAN !== "0") registro.reiniciar();

function caso(id, fn) {
  test(id, () => {
    try { registro.anotar(id, true, fn()); } catch (e) { registro.anotar(id, false, "Falló: " + e.message.split("\n")[0]); throw e; }
  });
}
const miles = (n) => String(n).replace(/\B(?=(\d{3})+(?!\d))/g, ".");
const r2 = (x) => Math.round(x * 100) / 100;

caso("CP-RF-13-01", () => {
  const ha = aHectareas(1000, "m2");
  const ef = areaEfectiva(1.0, ha);
  assert.equal(ha, 0.1); assert.equal(ef, 0.9);
  return `Dispositivo: 1.000 m² = ${ha} ha; área efectiva ${ef} ha`;
});
caso("CP-RF-13-03", () => {
  const ha = aHectareas(1, "plaza");
  const ef = areaEfectiva(1.0, ha);
  assert.equal(ha, 0.64); assert.equal(ef, 0.36);
  return `Dispositivo: 1 plaza = ${ha} ha; con 1,0 ha brutas la efectiva es ${ef} ha`;
});
caso("CP-RF-18-01", () => { assert.equal(matasPorHa("cuadrado", 1), 10000); return "Dispositivo: cuadrado d = 1 m → 10.000 matas/ha"; });
caso("CP-RF-18-02", () => { assert.equal(matasPorHa("rectangular", 2, 1.5), 3333.34); return "Dispositivo: rectangular 2 × 1,5 m → 3.333,34 matas/ha (hacia arriba)"; });
caso("CP-RF-18-03", () => {
  const n = matasPorHa("tresbolillo", 3);
  const exacto = 10000 / (9 * 0.866025);
  assert.equal(n, 1283.01); assert.ok(n >= exacto && n - exacto < 0.01);
  return `Dispositivo: tresbolillo d = 3 m → ${n.toFixed(2)} matas/ha (valor exacto ${exacto.toFixed(4)}; redondeo hacia arriba con 2 decimales)`;
});
caso("CP-RF-18-04", () => {
  const n = matasPorHa("cuadrado", 1.5);
  assert.equal(n, 4444.45); assert.equal(matasDelCiclo("cuadrado", 1.5, 0, 0.9), 4000);
  return `Dispositivo: café cuadrado 1,5 m → ${n} matas/ha y ${matasDelCiclo("cuadrado", 1.5, 0, 0.9)} matas en 0,9 ha`;
});
caso("CP-RF-24-02", () => { assert.equal(costoJornal(3, 60000), 180000); return "Dispositivo: 3 jornales × $60.000 = $180.000"; });
caso("CP-RF-25-05", () => {
  const t = totalIngreso(10000, 50000000);
  assert.equal(t, 500000000000);
  return `Dispositivo: 10.000 × $50.000.000 = ${money(t)} (número exacto, dentro de los enteros seguros de JavaScript)`;
});
caso("CP-RF-28-01", () => { const r = calcularUtilidad([600000], [1000000], 1); assert.equal(r.utilidad, 400000); assert.equal(r.rentabilidad, 66.7); return `Dispositivo: utilidad ${miles(r.utilidad)}; rentabilidad ${r.rentabilidad} %`; });
caso("CP-RF-28-02", () => { const r = calcularUtilidad([150000], [500000], 0.9); assert.equal(r.utilidad, 350000); assert.equal(r.rentabilidad, 233.3); return `Dispositivo: utilidad ${miles(r.utilidad)}; rentabilidad ${r.rentabilidad} %`; });
caso("CP-RF-28-03", () => { const r = calcularUtilidad([], [500000], 0.9); assert.equal(r.rentabilidad, 0); return `Dispositivo: gastos = 0 → rentabilidad ${r.rentabilidad} % sin error`; });
caso("CP-RF-28-08", () => {
  const cafe = SEMILLA.cultivos.find((c) => c.codigo === "CAFE").ficha_tecnica;
  const e = estimarCostos(cafe, 4000);
  assert.deepEqual(e, { siembra: 1600000, insumos: 3320000, jornales: 28 });
  return `Dispositivo: café con 4.000 matas → siembra ${miles(e.siembra)}, insumos ${miles(e.insumos)}, ${e.jornales} jornales al año`;
});
caso("CP-RF-14-08", () => {
  const dia = 86400000, hoy = new Date("2026-10-28T12:00:00Z").getTime();
  const iso = (ms) => new Date(ms).toISOString().slice(0, 10);
  const hoyIso = iso(hoy);
  const sem = (anios, usados) => semaforoVigencia(iso(hoy - Math.round(usados * 365.25) * dia), anios, hoyIso).semaforo;
  const r = [sem(10, 2), sem(4, 2.5), sem(4, 3.5), sem(3, 4), semaforoVigencia(hoyIso, null, hoyIso).semaforo];
  assert.deepEqual(r, ["VERDE", "AMARILLO", "ROJO", "ROJO", null]);
  return `Dispositivo: ${r.map((x) => x ?? "sin semáforo").join(" / ")} para 10/2, 4/2,5, 4/3,5, vencido y sin vigencia`;
});
caso("CP-RNF-22", () => {
  // valores esperados del plan: ya traen el redondeo hacia arriba con 2 decimales
  const teor = [[matasPorHa("cuadrado", 1), 10000], [matasPorHa("rectangular", 2, 1.5), 3333.34], [matasPorHa("tresbolillo", 3), 1283.01],
    [matasPorHa("cuadrado", 1.5), 4444.45], [costoJornal(3, 60000), 180000], [calcularUtilidad([150000], [500000], 0.9).utilidad, 350000]];
  const peor = Math.max(...teor.map(([a, b]) => Math.abs(a - b) / b * 100));
  assert.ok(peor <= 0.0001, String(peor));
  return `Dispositivo: peor error relativo de ${teor.length} cálculos = ${peor.toExponential(2)} % (meta ≤ 0,0001 %)`;
});
