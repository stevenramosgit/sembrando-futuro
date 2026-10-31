// Cierre de sesión en el dispositivo (RF-03, OWASP ASVS 3.3.2 nivel 2): 30 minutos sin uso, 12 horas como máximo
// y verificador PBKDF2 de la clave para volver a entrar sin conexión.
import test from "node:test";
import assert from "node:assert/strict";
import { claveCoincide, crearVerificador, motivoDeCierre } from "../src/sesion.js";

const MIN = 60000, HORA = 60 * MIN, T0 = Date.parse("2026-10-30T08:00:00Z");

test("sesión vigente: 29 minutos sin uso y 11 horas desde el ingreso", () => {
  assert.equal(motivoDeCierre({ autenticado_en: T0, ultima_actividad: T0 + 11 * HORA - 29 * MIN }, T0 + 11 * HORA), null);
});
test("30 minutos sin uso cierran la sesión (V-51)", () => {
  assert.equal(motivoDeCierre({ autenticado_en: T0, ultima_actividad: T0 }, T0 + 30 * MIN), "V-51");
});
test("12 horas desde el ingreso la cierran aunque se use sin parar (V-52)", () => {
  assert.equal(motivoDeCierre({ autenticado_en: T0, ultima_actividad: T0 + 12 * HORA - MIN }, T0 + 12 * HORA), "V-52");
});
test("una sesión guardada por una versión anterior (sin hora de ingreso) pide la clave", () => {
  assert.equal(motivoDeCierre({ token: "tkn_x" }, T0), "V-52");
});
test("el verificador acepta la clave correcta, rechaza otra y no guarda la clave", async () => {
  const v = await crearVerificador("Siembra#2026a");
  assert.equal(v.repeticiones, 600000);
  assert.ok(!JSON.stringify(v).includes("Siembra"));
  assert.equal(await claveCoincide("Siembra#2026a", v), true);
  assert.equal(await claveCoincide("Siembra#2026b", v), false);
  const otro = await crearVerificador("Siembra#2026a");
  assert.notEqual(otro.huella, v.huella, "cada verificador usa una sal distinta");
});
