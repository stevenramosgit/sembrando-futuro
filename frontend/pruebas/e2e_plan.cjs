// Plan de pruebas (documento 14), parte «ui»: casos que se ejecutan en el navegador contra un servidor real.
// Cada caso crea su propia cuenta, así que se puede repetir sin reiniciar el servidor.
//   cd backend && ENTORNO=pruebas LIMITE_REGISTRO=200/minuto LIMITE_INGRESO=200/minuto uvicorn app.main:app --port 8000
//   (con la base migrada, cargar_semilla y cargar_prueba: el administrador de prueba es admin.proyecto@correo.com)
//   cd frontend && node pruebas/e2e_plan.cjs        (resultados en pruebas/resultados_plan_ui.json)
const { chromium } = require("playwright");
const crypto = require("crypto");
const { abrir } = require("./registro_plan.cjs");

const BASE = process.env.BASE_URL || "http://localhost:8000/";
// Los campos de fecha usan el calendario del navegador (type=date): se llenan con AAAA-MM-DD. Una fecha inexistente (31/02) no se puede elegir y deja el campo vacío.
const aIso = (id, v) => {
  if (!/(fecha|^cierre)$/.test(id)) return v;
  const m = /^(\d{2})\/(\d{2})\/(\d{4})$/.exec(v);
  if (!m) return v;
  const f = new Date(Date.UTC(+m[3], +m[2] - 1, +m[1]));
  return f.getUTCDate() === +m[1] && f.getUTCMonth() === +m[2] - 1 ? `${m[3]}-${m[2]}-${m[1]}` : "";
};
const API = new URL("api/v1", BASE).toString();
const CLAVE = "Siembra#2026a";
const registro = abrir("ui");
if (process.env.REINICIAR_PLAN !== "0") registro.reiniciar();
const SOLO = process.env.SOLO ? process.env.SOLO.split(",") : null;
let contador = 0;
const correoNuevo = () => `plan.${Date.now().toString(36)}${++contador}@correo.com`;
const uuid = () => crypto.randomUUID();
const ahoraIso = () => new Date().toISOString();
const miles = (n) => String(n).replace(/\B(?=(\d{3})+(?!\d))/g, ".");

let browser;

async function caso(id, fn) {
  if (SOLO && !SOLO.includes(id)) return;
  try {
    const r = await fn();
    const texto = typeof r === "string" ? r : r.texto;
    registro.anotar(id, true, texto, typeof r === "string" ? undefined : r.estado);
    console.log("✔", id, "-", texto);
  } catch (e) {
    const donde = (String(e.stack).match(/e2e_plan\.cjs:(\d+)/) || [])[1];
    registro.anotar(id, false, "Falló: " + String(e.message).split("\n")[0].slice(0, 300) + (donde ? ` (e2e_plan.cjs línea ${donde})` : ""));
    console.log("✘", id, "-", String(e.message).split("\n")[0], e.pantalla ? "PANTALLA: " + e.pantalla : "", donde ? "línea " + donde : "", (String(e.message).match(/waiting for locator\('[^']*'\)/) || [""])[0]);
  }
}
function exigir(c, m) { if (!c) throw new Error(m); }

// ---------------------------------------------------------------- servidor
async function api(ruta, { metodo = "GET", token, cuerpo } = {}) {
  const r = await fetch(API + ruta, { method: metodo, headers: { "Content-Type": "application/json", ...(token ? { Authorization: "Bearer " + token } : {}) }, body: cuerpo ? JSON.stringify(cuerpo) : undefined });
  let json = null; try { json = await r.json(); } catch { /* sin cuerpo */ }
  return { estado: r.status, json };
}
async function crearCuenta(correo = correoNuevo(), clave = CLAVE) {
  const r = await api("/auth/registro", { metodo: "POST", cuerpo: { nombre: "María Pérez", ubicacion: "Caloto, Cauca", correo, correo_confirmacion: correo, clave, autoriza_datos: true } });
  exigir(r.estado === 201, "registro " + r.estado);
  const v = await api("/auth/otp/verificar", { metodo: "POST", token: r.json.token_activacion, cuerpo: { codigo: "482915" } });
  exigir(v.estado === 200, "verificación " + v.estado);
  const i = await api("/auth/ingreso", { metodo: "POST", cuerpo: { correo, clave } });
  exigir(i.estado === 200, "ingreso " + i.estado);
  return { correo, clave, token: i.json.token };
}
const reg = (tipo, id, datos) => ({ tipo, id, updated_at: ahoraIso(), eliminado: false, datos });
/** Finca + ciclo de 0,9 ha con café (4.000 matas) y, según las opciones, un gasto, un jornal y un ingreso (los del RF-28-05). */
async function sembrar(cuenta, o = {}) {
  const f = uuid(), c = uuid(), cc = uuid();
  const lote = { finca_id: f, nombre_lote: "Lote Alto", pendiente_pct: 12, area_bruta_ha: 1.0, area_no_sembrable_ha: 0.1, area_efectiva_ha: 0.9, fecha_siembra: "2026-03-15", vigencia_anios: 7, estado: "ACTIVO" };
  const registros = [reg("finca", f, { nombre: "La Esperanza" }), reg("ciclo", c, lote), reg("ciclo_cultivo", cc, { ciclo_id: c, cultivo_codigo: "CAFE", marco: "cuadrado", dist_a_m: 1.5 })];
  if (o.gasto !== false) registros.push(reg("gasto", uuid(), { ciclo_id: c, fecha: "2026-04-12", categoria: "abonos", valor_cop: 100000, observaciones: "Abono orgánico" }));
  for (const [valor, cat] of o.gastos || []) registros.push(reg("gasto", uuid(), { ciclo_id: c, fecha: "2026-04-20", categoria: cat, valor_cop: valor, observaciones: "Gasto adicional" }));
  if (o.jornal !== false) registros.push(reg("jornal", uuid(), { ciclo_id: c, fecha: "2026-04-20", jornales: 2, valor_diario_cop: 25000 }));
  if (o.ingreso !== false) registros.push(reg("ingreso", uuid(), { ciclo_id: c, fecha: "2026-09-10", cantidad: 4, precio_unitario_cop: 125000 }));
  const r = await api("/sync/push", { metodo: "POST", token: cuenta.token, cuerpo: { dispositivo_id: "plan", registros } });
  exigir(r.estado === 200 && r.json.resultados.every((x) => x.estado === "ACEPTADO"), "sembrar: " + JSON.stringify(r.json).slice(0, 200));
  return { f, c, cc };
}
const registrosDe = async (cuenta, tipo) => (await api("/sync/pull", { token: cuenta.token })).json.registros.filter((x) => !tipo || x.tipo === tipo);

// ---------------------------------------------------------------- navegador
async function sesion(o = {}) {
  const ctx = await browser.newContext({ viewport: { width: 390, height: 780 }, locale: "es-CO", serviceWorkers: "allow", ...o });
  const page = await ctx.newPage();
  page.errores = [];
  page.dialogos = [];
  page.on("pageerror", (e) => page.errores.push(e.message));
  page.on("dialog", (d) => { page.dialogos.push(d.message()); d.dismiss(); });
  return { ctx, page };
}
const texto = (page) => page.locator("#screen").innerText();
const act = (page, a) => page.locator(`[data-act="${a}"]`).first();
const clic = (page, a) => act(page, a).click();
const llenar = (page, id, v) => page.fill("#" + id, aIso(id, v));
/** Va a una pestaña principal; si la pantalla actual no la muestra (un formulario), recarga la app (que conserva todo en el dispositivo). */
async function aNav(page, destino) {
  if (!(await act(page, destino).count())) { await page.reload(); await page.waitForSelector(".appbar"); await page.waitForTimeout(400); }
  await clic(page, destino);
}
const pendientes = async (page) => { const t = await page.locator('[aria-label="Estado de conexión"]').textContent(); const m = /·\s*(\d+)/.exec(t); return m ? Number(m[1]) : 0; };
const sinPendientes = (page, ms = 20000) => page.waitForFunction(() => !document.querySelector('[aria-label="Estado de conexión"]').textContent.includes("·"), null, { timeout: ms });
async function entrar(page, cuenta) {
  await page.goto(BASE);
  await page.waitForSelector("text=Cultive con cuentas claras");
  await clic(page, "go:p07");
  await llenar(page, "lmail", cuenta.correo); await llenar(page, "lpass", cuenta.clave);
  await clic(page, "login");
  await page.waitForSelector(".appbar h1:not(:has-text('Ingresar'))");
  await page.waitForTimeout(400);
}
async function sinConexion(ctx, page, si) {
  await ctx.setOffline(si);
  await page.evaluate((s) => window.dispatchEvent(new Event(s ? "offline" : "online")), si);
  await page.waitForTimeout(200);
}
const IDBSESION = () => new Promise((res) => { const r = indexedDB.open("sembrando_futuro"); r.onsuccess = () => { const q = r.result.transaction("sesion").objectStore("sesion").get("actual"); q.onsuccess = () => res(q.result || null); }; });
async function registrarGasto(page, valor, fecha = "25/04/2026", cat = "transporte", obs = "") {
  await clic(page, "go:p21");
  await llenar(page, "gfecha", fecha); await page.selectOption("#gcat", cat); await llenar(page, "gval", String(valor)); if (obs) await llenar(page, "gobs", obs);
  await clic(page, "savegas");
}
async function conUsuario(opciones, fn) {
  const cuenta = await crearCuenta();
  const datos = opciones === null ? null : await sembrar(cuenta, opciones);
  const s = await sesion();
  try { await entrar(s.page, cuenta); return await fn({ ...s, cuenta, datos }); } catch (e) {
    e.pantalla = await s.page.locator("#screen").innerText().then((t) => t.replace(/\n/g, " | ").slice(0, 400)).catch(() => "");
    throw e;
  } finally { await s.ctx.close(); }
}

// ================================================================ casos
async function ejecutar() {
  browser = await chromium.launch();

  await caso("CP-RF-01-05", async () => {
    const s = await sesion();
    try {
      await s.page.goto(BASE); await s.page.waitForSelector("text=Cultive con cuentas claras");
      await clic(s.page, "go:p07"); await llenar(s.page, "lmail", "admin.proyecto@correo.com"); await llenar(s.page, "lpass", "Cafe#Cauca2026"); await clic(s.page, "login");
      await s.page.waitForSelector("text=cuenta es de administración");
      const t = await texto(s.page);
      const guardada = await s.page.evaluate(IDBSESION);
      exigir(!t.includes("Resumen del ciclo") && guardada === null, "se abrió el panel o se guardó la sesión");
      return "El administrador no puede abrir sesión en la aplicación: aviso «Esta cuenta es de administración y no tiene pantallas en la aplicación. Use los comandos de administración del servidor.»; no se guarda la sesión ni se abre el panel";
    } finally { await s.ctx.close(); }
  });

  await caso("CP-RF-01-04", async () => {
    const s = await sesion();
    try {
      await s.page.goto(BASE); await s.page.waitForSelector("text=Cultive con cuentas claras");
      await clic(s.page, "go:p02");
      const t = (await texto(s.page)).toLowerCase();
      const selects = await s.page.locator("#screen select").count();
      exigir(!t.includes("administrador") && !t.includes("rol") && selects === 0, "la pantalla ofrece elegir rol");
      return "Pantalla: el formulario de registro no tiene campo ni opción de rol (0 listas desplegables, sin la palabra «administrador»)";
    } finally { await s.ctx.close(); }
  });

  await caso("CP-RF-02-07", async () => {
    const s = await sesion();
    try {
      let n = 0;
      s.page.on("request", (r) => { if (r.url().includes("/auth/registro") && r.method() === "POST") n++; });
      await s.page.goto(BASE); await s.page.waitForSelector("text=Cultive con cuentas claras");
      await clic(s.page, "go:p02");
      const c = correoNuevo();
      await llenar(s.page, "nombre", "Juan Gómez"); await llenar(s.page, "ubic", "Caloto, Cauca"); await llenar(s.page, "correo", c); await llenar(s.page, "correo2", c);
      await llenar(s.page, "clave", CLAVE); await s.page.check("#auth");
      await act(s.page, "reg").dblclick();
      await s.page.waitForSelector("text=Escriba el código");
      await s.page.waitForTimeout(500);
      exigir(n === 1, "se enviaron " + n + " solicitudes");
      return `Dos clics rápidos en «Registrarme»: se envió ${n} sola solicitud al servidor y se abrió la pantalla del código`;
    } finally { await s.ctx.close(); }
  });

  await caso("CP-RNF-09", async () => {
    const s = await sesion();
    try {
      await s.page.goto(BASE); await s.page.waitForSelector("text=Cultive con cuentas claras");
      await clic(s.page, "go:p02");
      await llenar(s.page, "nombre", "<script>alert(1)</script>"); await llenar(s.page, "correo", "x@correo.com"); await clic(s.page, "reg");
      const rechazoNombre = (await texto(s.page)).includes("(V-01)");
      await s.ctx.close();
      const cuenta = await crearCuenta(); await sembrar(cuenta);
      const s2 = await sesion();
      try {
        await entrar(s2.page, cuenta);
        const ataque = "<img src=x onerror=alert(2)><script>alert(3)</script>";
        await registrarGasto(s2.page, 5000, "26/04/2026", "otros", ataque);
        await s2.page.waitForTimeout(500);
        const t = await texto(s2.page);
        const t2 = await (async () => { await aNav(s2.page, "tab:p20"); return texto(s2.page); })();
        const inyectado = await s2.page.evaluate(() => document.querySelectorAll("#screen script, #screen img[src='x']").length);
        exigir(s2.page.dialogos.length === 0 && inyectado === 0, "se ejecutó código inyectado");
        return `Nombre «<script>alert(1)</script>» ${rechazoNombre ? "rechazado con V-01" : "NO rechazado"}; observaciones del gasto con <img onerror> y <script>: ${t.includes("(V-38)") || t2.includes("(V-38)") ? "rechazadas (V-38)" : "se muestran como texto"}; 0 diálogos de alerta y 0 elementos inyectados en la pantalla. OWASP ZAP: no se ejecutó`;
      } finally { await s2.ctx.close(); }
    } finally { try { await s.ctx.close(); } catch { /* ya cerrado */ } }
  });

  await caso("CP-RF-07-01", () => conUsuario(null, async ({ page }) => {
    const t = await texto(page);
    exigir(t.includes("Bienvenido a Sembrando Futuro") && t.includes("Registrar mi primera finca"), "no muestra la bienvenida");
    return "Cuenta sin fincas ni ciclos: muestra «Bienvenido a Sembrando Futuro» y el botón «Registrar mi primera finca»";
  }));

  await caso("CP-RF-07-02", () => conUsuario({}, async ({ page }) => {
    const t = await texto(page);
    for (const x of ["Área efectiva", "0,90 ha", "4.000", "Gastos", "Ingresos", "Utilidad neta", "$ 350.000"]) exigir(t.includes(x), "falta «" + x + "»");
    return "Ciclo con datos: muestra área efectiva 0,90 ha, 4.000 matas, gastos, ingresos y utilidad neta $ 350.000";
  }));

  await caso("CP-RF-28-04", () => conUsuario({ gastos: [[600000, "otros"]] }, async ({ page }) => {
    const t = await texto(page);
    const color = await page.locator(".kpi.perdida b").first().evaluate((e) => getComputedStyle(e).color).catch(() => null);
    const [r, g, b] = (color || "0,0,0").match(/\d+/g).map(Number);
    exigir(t.includes("Pérdida") && r > g + 60 && r > b + 60, `sin «Pérdida» en rojo (color ${color})`);
    return `Gastos mayores que ingresos: la pantalla muestra «Pérdida» con la cifra en rojo (${color}); no depende solo del color porque lleva la palabra`;
  }));

  await caso("CP-RF-28-08", () => conUsuario({}, async ({ page }) => {
    const t = await texto(page);
    exigir(t.includes("Costos aproximados") && t.includes("$ 1.600.000") && t.includes("$ 3.320.000") && t.includes("28") && t.includes("orientativos"), "falta el aviso o las cifras");
    return "Pantalla: «Costos aproximados (ficha técnica)» con siembra $ 1.600.000, insumos $ 3.320.000, 28 jornales y el aviso «Son valores orientativos de la ficha técnica, no un presupuesto.»";
  }));

  await caso("CP-RF-12-01", () => conUsuario(null, async ({ page }) => {
    await clic(page, "go:p12"); await llenar(page, "fnom", "La Esperanza"); await clic(page, "savefinca");
    await page.waitForSelector("text=Primer cultivo");
    await aNav(page, "tab:p11");
    const t = await texto(page);
    exigir(t.includes("La Esperanza"), "la finca no aparece");
    return "Pantalla: finca «La Esperanza» guardada y visible en «Mis fincas»";
  }));

  await caso("CP-RF-13-03", () => conUsuario({}, async ({ page }) => {
    await clic(page, "tab:p11"); await page.locator('[data-act^="area:"]').first().click(); await page.waitForSelector("text=Área efectiva");
    await page.selectOption("#unit", "plaza"); await llenar(page, "nosemb", "1");
    const t = await texto(page);
    exigir(t.includes("0,64 ha") && t.includes("0,36 ha"), "no convierte la plaza");
    return "Pantalla: 1 plaza = 0,64 ha; con 1,0 ha brutas la efectiva es 0,36 ha";
  }));

  await caso("CP-RF-13-02", async () => {
    const cuenta = await crearCuenta(); await sembrar(cuenta);
    const s = await sesion();
    try {
      await entrar(s.page, cuenta);
      const intento = async (v) => { await aNav(s.page, "tab:p11"); await s.page.locator('[data-act^="area:"]').first().click(); await s.page.waitForSelector("text=Área efectiva"); await s.page.selectOption("#unit", "ha"); await llenar(s.page, "nosemb", v); await clic(s.page, "savearea"); await s.page.waitForTimeout(300); return texto(s.page); };
      const t1 = await intento("1"), t2 = await intento("1,5");
      const t3 = await intento("0,9999");
      await sinPendientes(s.page);
      const c = (await registrosDe(cuenta, "ciclo"))[0].datos;
      exigir(t1.includes("(V-26)") && t2.includes("(V-26)") && !t3.includes("(V-26)") && c.area_efectiva_ha === 0.0001, `1→${t1.includes("V-26")}, 1,5→${t2.includes("V-26")}, 0,9999→${c.area_efectiva_ha}`);
      return `Pantalla: 1,0 ha y 1,5 ha no sembrables dan V-26; 0,9999 ha se acepta (efectiva 0,0001 ha) y el servidor lo recibe con área efectiva ${c.area_efectiva_ha}`;
    } finally { await s.ctx.close(); }
  });

  await caso("CP-RF-23-05", () => conUsuario({}, async ({ page }) => {
    await registrarGasto(page, 100000, "31/02/2026", "abonos");
    const t = await texto(page);
    const escrito = await page.inputValue("#gfecha");
    exigir(t.includes("(V-28)") && escrito === "", "V-28 o el calendario dejó pasar la fecha");
    return "Pantalla: la fecha inexistente 31/02/2026 no se puede elegir en el calendario (el campo queda vacío) y se rechaza con V-28";
  }));

  await caso("CP-RF-25-05", () => conUsuario({}, async ({ page }) => {
    await clic(page, "tab:p20"); await clic(page, "go:p23");
    await llenar(page, "ifecha", "10/09/2026"); await llenar(page, "iq", "10000"); await llenar(page, "ip", "50000000");
    const previa = await texto(page);
    await clic(page, "saveinc"); await page.waitForSelector("text=Ingreso guardado");
    await clic(page, "tab:p10");
    const t = await texto(page);
    exigir(previa.includes("$ 500.000.000.000") && t.includes("$ 500.000.500.000") && !/NaN|e\+/.test(t), "total mal mostrado: vista previa «" + previa.replace(/\n/g, " | ").slice(-170) + "»; resumen «" + t.replace(/\n/g, " | ").slice(120, 420) + "»");
    return "Pantalla: 10.000 × $ 50.000.000 muestra «$ 500.000.000.000» completo en la vista previa y el resumen suma $ 500.000.500.000 (los $ 500.000 anteriores más el nuevo ingreso), sin NaN ni notación científica";
  }));

  await caso("CP-RF-27-03", () => conUsuario({}, async ({ page }) => {
    await clic(page, "tab:p20");
    await page.locator(".fila .tap", { hasText: "Jornales" }).first().click();
    await page.waitForSelector("text=Editar registro");
    await llenar(page, "jn", "3");
    await clic(page, "saveedit");
    await page.waitForSelector("text=Cambios guardados");
    const t = await texto(page);
    exigir(t.includes("$ 325.000") || (await (async () => { await clic(page, "tab:p10"); return texto(page); })()).includes("$ 325.000"), "no recalcula la utilidad");
    return "Pantalla: jornal de 2 a 3 jornales ($ 25.000 diarios): aviso «Los saldos se recalcularon» y la utilidad pasa de $ 350.000 a $ 325.000";
  }));

  // ---- deshacer (V-43, RF-27-01 y RF-27-02): el tiempo se controla para medir 9, 10 y 11 s con exactitud
  const deshacer = (ms) => conUsuario({ gastos: [[150000, "transporte"]] }, async ({ page }) => {
    await clic(page, "tab:p20");
    const antes = await texto(page);
    await page.evaluate(() => { window.__t = Date.now(); Date.now = () => window.__t; });
    await page.locator(".fila .tap", { hasText: "Gasto adicional" }).first().click();
    await page.waitForSelector("text=Editar registro");
    await clic(page, "del");
    await page.waitForSelector("text=Registro eliminado");
    const sin = (await texto(page)).includes("Gasto adicional");
    await page.evaluate((m) => { window.__t += m; }, ms);
    await page.waitForTimeout(1200);
    if (await act(page, "undo").count()) await clic(page, "undo");
    await page.waitForTimeout(300);
    const t = await texto(page);
    const toast = await page.locator("#toast").innerText().catch(() => "");
    return { vuelve: t.includes("Gasto adicional"), v43: toast.includes("Ya no se puede deshacer"), desaparecio: !sin, saldoIgual: t.match(/\$ [\d.]+/g)?.join() === antes.match(/\$ [\d.]+/g)?.join() };
  });
  const seguro = (ms) => deshacer(ms).catch((e) => ({ error: e.message.split("\n")[0] }));
  const d9 = await seguro(9000), d10 = await seguro(10000), d11 = await seguro(11000);
  await caso("CP-RF-27-01", async () => { exigir(d9.desaparecio && d9.vuelve && d9.saldoIgual, JSON.stringify(d9)); return "Gasto de $ 150.000 eliminado y «Deshacer» a los 9 s: el gasto vuelve a la lista y los saldos quedan como antes"; });
  await caso("CP-RF-27-02", async () => { exigir(d10.vuelve && d11.v43 && !d11.vuelve, JSON.stringify({ d10, d11 })); return "«Deshacer» a los 10 s: funciona (el gasto vuelve); a los 11 s: aparece «Ya no se puede deshacer.» y el gasto sigue eliminado"; });
  await caso("CP-V-43-OK", async () => { exigir(d10.vuelve, JSON.stringify(d10)); return "Deshacer a los 10 s: se acepta y el registro vuelve"; });
  await caso("CP-V-43-ERR", async () => { exigir(d11.v43 && !d11.vuelve, JSON.stringify(d11)); return "Deshacer a los 11 s: muestra «Ya no se puede deshacer.», no avanza y el registro sigue eliminado"; });

  // ---- cierre del ciclo (V-30, RF-15-02)
  const cerrar = (opciones) => conUsuario(opciones, async ({ page }) => {
    await clic(page, "go:p15");
    const hoy = new Date(Date.now() - 5 * 3600000).toISOString().slice(0, 10).split("-").reverse().join("/");
    await llenar(page, "cierre", hoy);
    await clic(page, "closego");
    await page.waitForTimeout(300);
    const t = await texto(page);
    const pregunta = t.includes("¿Desea cerrarlo de todos modos?");
    const conserva = (await page.inputValue("#cierre").catch(() => "")) === hoy.split("/").reverse().join("-");
    let cerro = t.includes("El ciclo se cerró");
    if (pregunta) { await clic(page, "closeyes"); await page.waitForTimeout(400); cerro = (await texto(page)).includes("El ciclo se cerró"); }
    return { pregunta, conserva, cerro };
  });
  const segura = (o) => cerrar(o).catch((e) => ({ error: e.message.split("\n")[0] }));
  const sinIng = await segura({ ingreso: false }), conIng = await segura({});
  await caso("CP-RF-15-02", async () => { exigir(sinIng.pregunta && sinIng.cerro, JSON.stringify(sinIng)); return "Ciclo sin ingresos: pide confirmación «Este ciclo no tiene ingresos. ¿Desea cerrarlo de todos modos?»; al confirmar, se cierra"; });
  await caso("CP-V-30-ERR", async () => { exigir(sinIng.pregunta && sinIng.conserva, JSON.stringify(sinIng)); return "Ciclo sin ingresos: muestra «Este ciclo no tiene ingresos. ¿Desea cerrarlo de todos modos?», no avanza y conserva la fecha escrita"; });
  await caso("CP-V-30-OK", async () => { exigir(!conIng.pregunta && conIng.cerro, JSON.stringify(conIng)); return "Ciclo con ingresos: cierra directamente, sin pregunta"; });

  // ---- catálogo
  await caso("CP-RF-17-01", () => conUsuario({}, async ({ ctx, page }) => {
    await clic(page, "tab:p16"); await clic(page, "cult:CAFE");
    const sinAviso = (t) => t.split("\n").filter((l) => !/Sin conexión|En línea/.test(l)).join("\n");
    const online = sinAviso(await texto(page));
    await sinConexion(ctx, page, true);
    await page.reload(); await page.waitForSelector(".appbar");
    await clic(page, "tab:p16"); await clic(page, "cult:CAFE");
    const offline = sinAviso(await texto(page));
    exigir(online.length > 50 && online === offline, "las fichas difieren: «" + online.slice(0, 80) + "» / «" + offline.slice(0, 80) + "»");
    return `La ficha del café se ve idéntica con y sin conexión (${online.length} caracteres: distancias, marcos, fuente y costos de referencia)`;
  }));

  await caso("CP-RF-37-01", () => conUsuario(null, async ({ page }) => {
    await clic(page, "tab:p16");
    const t = await texto(page);
    const idb = await page.evaluate(() => new Promise((res) => { const r = indexedDB.open("sembrando_futuro"); r.onsuccess = () => { const n = [...r.result.objectStoreNames]; res(n); }; }));
    exigir(["Café", "Plátano", "Yuca"].every((x) => t.includes(x)), "faltan cultivos");
    return `Dispositivo: el catálogo muestra Café, Plátano y Yuca sin que el usuario haga nada (almacenes locales: ${idb.join(", ")})`;
  }));

  // ---- sin conexión, sincronización, cierre de sesión
  await caso("CP-RF-07-03", () => conUsuario({}, async ({ ctx, page }) => {
    await sinConexion(ctx, page, true);
    await registrarGasto(page, 30000); await page.waitForSelector("text=Gasto guardado");
    await aNav(page, "tab:p10");
    const t = await texto(page), p = await page.locator('[aria-label="Estado de conexión"]').textContent();
    exigir(p.includes("Sin conexión") && p.includes("· 1") && t.includes("Pendientes por enviar: 1"), p);
    return `Modo sin conexión: el indicador pasa a «${p.trim()}» y el panel muestra «Pendientes por enviar: 1 registro»`;
  }));

  await caso("CP-RF-23-03", () => conUsuario({}, async ({ ctx, page }) => {
    await sinConexion(ctx, page, true);
    await registrarGasto(page, 30000); await page.waitForSelector("text=Gasto guardado");
    await clic(page, "tab:p10");
    const t = await texto(page);
    exigir(t.includes("$ 320.000") && (await pendientes(page)) === 1, "no actualiza la utilidad");
    return "Sin conexión: el gasto de $ 30.000 queda PENDIENTE (1) y la utilidad baja de $ 350.000 a $ 320.000";
  }));

  await caso("CP-V-44-OK", () => conUsuario({}, async ({ page }) => { const t = await texto(page); exigir(!t.includes("Sin conexión: sus datos"), "avisa sin conexión estando en línea"); return "Con conexión: no aparece el aviso de falta de conexión y se puede continuar"; }));
  await caso("CP-V-44-ERR", () => conUsuario({}, async ({ ctx, page }) => {
    await sinConexion(ctx, page, true);
    const t = await texto(page);
    exigir(t.includes("Sin conexión: sus datos están guardados en este dispositivo y se enviarán solos."), "falta el mensaje");
    return "Sin conexión: muestra «Sin conexión: sus datos están guardados en este dispositivo y se enviarán solos.» y deja seguir trabajando";
  }));

  await caso("CP-RF-12-04", () => conUsuario(null, async ({ ctx, cuenta, page }) => {
    await sinConexion(ctx, page, true);
    await clic(page, "go:p12"); await llenar(page, "fnom", "Finca sin señal"); await clic(page, "savefinca");
    await page.waitForSelector("text=Primer cultivo");
    const n = await pendientes(page);
    await sinConexion(ctx, page, false);
    await sinPendientes(page);
    const fincas = await registrosDe(cuenta, "finca");
    exigir(n === 1 && fincas.some((f) => f.datos.nombre === "Finca sin señal"), `pendientes ${n}`);
    return `Finca creada sin conexión queda PENDIENTE (${n}); al volver internet se envía sola y el servidor la tiene («Finca sin señal»)`;
  }));

  await caso("CP-RF-35-01", () => conUsuario({}, async ({ ctx, cuenta, page }) => {
    await sinConexion(ctx, page, true);
    await registrarGasto(page, 30000); await page.waitForSelector("text=Gasto guardado");
    await page.close();
    const nueva = await ctx.newPage();
    await nueva.goto(BASE); await nueva.waitForSelector(".appbar");
    await nueva.locator('[data-act="tab:p20"]').click();
    const t = await texto(nueva);
    exigir(t.includes("30.000"), "el gasto se perdió");
    await ctx.setOffline(false); await nueva.evaluate(() => window.dispatchEvent(new Event("online"))); await sinPendientes(nueva);
    const g = (await registrosDe(cuenta, "gasto")).filter((x) => x.datos.valor_cop === 30000).length;
    exigir(g === 1, "gastos de 30.000 en el servidor: " + g);
    return "Modo avión → gasto → cierre de la pestaña → reapertura sin internet: el gasto sigue guardado (0 % de pérdida); al volver internet llega 1 sola vez al servidor";
  }));

  await caso("CP-RF-35-02", () => conUsuario(null, async ({ ctx, cuenta, page }) => {
    await sinConexion(ctx, page, true);
    await clic(page, "tab:p16"); exigir((await texto(page)).includes("Café"), "sin catálogo");
    await clic(page, "tab:p10"); await clic(page, "go:p12"); await llenar(page, "fnom", "La Esperanza"); await clic(page, "savefinca");
    await page.waitForSelector("text=Primer cultivo");
    await llenar(page, "cnom", "Lote Alto"); await llenar(page, "carea", "1"); await llenar(page, "cpend", "12"); await llenar(page, "cfecha", "15/03/2026"); await llenar(page, "cvig", "7");
    await page.selectOption("#ccult", "CAFE"); await page.locator('[data-act="seg"][data-v="cuadrado"]').click(); await llenar(page, "ca", "1,5");
    await clic(page, "savecy"); await page.waitForSelector("text=Resumen del ciclo");
    await registrarGasto(page, 100000, "12/04/2026", "abonos"); await page.waitForSelector("text=Gasto guardado");
    await clic(page, "go:p22"); await llenar(page, "jfecha", "20/04/2026"); await llenar(page, "jn", "2"); await llenar(page, "jv", "25000"); await clic(page, "savejor");
    await clic(page, "go:p23"); await llenar(page, "ifecha", "10/09/2026"); await llenar(page, "iq", "4"); await llenar(page, "ip", "125000"); await clic(page, "saveinc");
    await page.waitForSelector("text=Ingreso guardado");
    const t = await texto(page), n = await pendientes(page);
    exigir(t.includes("$ 350.000") && n === 6, `pendientes ${n}`);
    await sinConexion(ctx, page, false); await sinPendientes(page);
    const tipos = (await registrosDe(cuenta)).map((x) => x.tipo).sort().join(",");
    exigir(tipos === "ciclo,ciclo_cultivo,finca,gasto,ingreso,jornal", tipos);
    globalThis.__sinConexion36 = { n, tipos };
    return `Sin internet funcionaron el catálogo, la finca, el ciclo, el gasto, el jornal y el ingreso (utilidad $ 350.000, ${n} registros pendientes). Al volver la conexión se enviaron los ${n}: el servidor tiene ${tipos}`;
  }));

  await caso("CP-RF-36-01", async () => {
    const r = globalThis.__sinConexion36;
    exigir(r && r.n === 6, "depende de CP-RF-35-02");
    return `Con ${r.n} registros PENDIENTES al volver la conexión: se enviaron solos, el indicador quedó sin pendientes (SINCRONIZADO) y el servidor los tiene (${r.tipos})`;
  });

  await caso("CP-V-45-ERR", () => conUsuario({}, async ({ page }) => {
    await page.route("**/sync/push", (r) => r.fulfill({ status: 500, contentType: "application/json", body: '{"error":{"codigo":"V-45","mensaje":"x"}}' }));
    await registrarGasto(page, 30000); await page.waitForSelector("text=Gasto guardado");
    await clic(page, "tab:p10"); await page.locator('[data-act="go:p25"]').click(); await page.waitForSelector("text=Estado de sincronización");
    await clic(page, "syncnow"); await page.waitForTimeout(800);
    const t = await texto(page), n = await pendientes(page);
    exigir(t.includes("No pudimos enviar sus datos ahora. Lo intentaremos de nuevo.") && n === 1, `pendientes ${n}`);
    globalThis.__v45 = { t, n };
    return `Error 500 del servidor: muestra «No pudimos enviar sus datos ahora. Lo intentaremos de nuevo.»; el gasto sigue PENDIENTE (${n}) en el dispositivo`;
  }));
  await caso("CP-V-45-OK", () => conUsuario({}, async ({ page }) => {
    await registrarGasto(page, 30000); await page.waitForSelector("text=Gasto guardado"); await sinPendientes(page);
    return "Envío correcto: el gasto pasa a sincronizado sin avisos de error";
  }));
  await caso("CP-RNF-25", async () => {
    const v = globalThis.__v45; exigir(v, "depende de CP-V-45-ERR");
    const tabu = /Traceback|TypeError|undefined|\bNaN\b|Failed to fetch|\bstack\b|Error 500|\bSQL\b|Exception/;
    exigir(!tabu.test(v.t), "se ven trazas técnicas: " + (tabu.exec(v.t) || [""])[0]);
    return "Servidor: 500 con mensaje V-45 sin trazas (prueba test_CP_RNF_25). Pantalla: ante un error 500 se muestra solo el texto «No pudimos enviar sus datos ahora…», sin trazas ni códigos técnicos; no se muestran palabras como Traceback, undefined o Failed to fetch";
  });

  await caso("CP-V-20-OK", () => conUsuario({}, async ({ page }) => {
    await clic(page, "go:p26"); await clic(page, "outask");
    await page.waitForSelector("text=Cultive con cuentas claras", { timeout: 8000 });
    return "Cerrar sesión sin pendientes: cierra directamente, sin pedir confirmación";
  }));
  const salida = () => conUsuario({}, async ({ ctx, cuenta, page }) => {
    await sinConexion(ctx, page, true);
    for (const v of [11000, 12000, 13000]) { await aNav(page, "tab:p10"); await registrarGasto(page, v, "25/04/2026", "otros"); await page.waitForSelector("text=Gasto guardado"); await page.waitForTimeout(150); }
    const n = await pendientes(page);
    await clic(page, "tab:p10"); await clic(page, "go:p26");
    await page.waitForSelector("text=Política de datos y ayuda", { timeout: 5000 });
    await clic(page, "outask");
    const t = await texto(page);
    const aviso = t.includes("Tiene 3 registros sin enviar. Se conservarán en este dispositivo. ¿Cerrar sesión?");
    await clic(page, "back");
    const sigueDentro = (await texto(page)).includes("Resumen del ciclo") && (await pendientes(page)) === 3;
    await clic(page, "go:p26"); await clic(page, "outask"); await clic(page, "outyes");
    await page.waitForSelector("text=Cultive con cuentas claras", { timeout: 8000 });
    await sinConexion(ctx, page, false);
    await clic(page, "go:p07"); await llenar(page, "lmail", cuenta.correo); await llenar(page, "lpass", cuenta.clave); await clic(page, "login");
    await page.waitForSelector(".appbar h1:not(:has-text('Ingresar'))"); await page.waitForTimeout(500);
    const antes = await pendientes(page).catch(() => -1);
    await sinPendientes(page, 25000);
    const g = (await registrosDe(cuenta, "gasto")).filter((x) => [11000, 12000, 13000].includes(x.datos.valor_cop)).length;
    return { n, aviso, sigueDentro, antes, g };
  });
  const sal = await salida().catch((e) => ({ error: e.message.split("\n")[0].slice(0, 80) + (e.message.match(/waiting for locator\(.[^)]*\)/) || [""])[0],  pantalla: e.pantalla, linea: (String(e.stack).match(/e2e_plan\.cjs:(\d+)/) || [])[1] }));
  await caso("CP-V-20-ERR", async () => { exigir(sal.n === 3 && sal.aviso && sal.sigueDentro, JSON.stringify(sal)); return "Cerrar sesión con 3 pendientes: muestra «Tiene 3 registros sin enviar. Se conservarán en este dispositivo. ¿Cerrar sesión?», no cierra mientras no se confirme y conserva los datos"; });
  await caso("CP-RF-04-01", async () => { exigir(sal.n === 3 && sal.aviso && sal.sigueDentro, JSON.stringify(sal)); return "Cerrar sesión con 3 registros PENDIENTES: advierte «Tiene 3 registros sin enviar», pide confirmación (Cancelar deja la sesión abierta) y conserva los datos locales"; });
  await caso("CP-RF-04-02", async () => { exigir(sal.g === 3, JSON.stringify(sal)); return `Cerrar sesión y volver a ingresar con la misma cuenta: los 3 registros creados sin conexión se conservaron al cerrar sesión y se enviaron solos al ingresar de nuevo (el servidor tiene los ${sal.g} gastos)`; });

  await caso("CP-RNF-11", async () => {
    const cuenta = await crearCuenta(); await sembrar(cuenta);
    const s = await sesion();
    try {
      await entrar(s.page, cuenta);
      await sinConexion(s.ctx, s.page, true);
      await registrarGasto(s.page, 21000); await s.page.waitForSelector("text=Gasto guardado");
      // 1) el envío se corta antes de llegar al servidor
      await s.page.route("**/sync/push", (r) => r.abort());
      await sinConexion(s.ctx, s.page, false);
      await s.page.waitForTimeout(1500);
      const pend1 = await pendientes(s.page);
      // 2) el servidor recibe el registro pero la respuesta se pierde
      await s.page.unroute("**/sync/push");
      await s.page.route("**/sync/push", async (r) => { await r.fetch(); await r.abort(); });
      await s.page.evaluate(() => window.dispatchEvent(new Event("online")));
      await s.page.waitForTimeout(1500);
      const pend2 = await pendientes(s.page);
      // 3) el navegador se cierra de golpe
      await s.page.close();
      const nueva = await s.ctx.newPage();
      await nueva.goto(BASE); await nueva.waitForSelector(".appbar"); await nueva.waitForTimeout(800);
      await nueva.unroute("**/sync/push").catch(() => {});
      const pend3 = await pendientes(nueva);
      await nueva.evaluate(() => window.dispatchEvent(new Event("online")));
      await sinPendientes(nueva);
      const g = (await registrosDe(cuenta, "gasto")).filter((x) => x.datos.valor_cop === 21000).length;
      exigir(pend1 === 1 && g === 1, `pendientes ${pend1}/${pend2}/${pend3}, servidor ${g}`);
      return `Envío cortado antes de llegar (${pend1} pendiente), respuesta perdida tras llegar (${pend2} pendiente) y cierre brusco del navegador (al reabrir había ${pend3} pendiente y el envío automático terminó): 0 registros perdidos y 1 solo gasto de $ 21.000 en el servidor (0 duplicados)`;
    } finally { await s.ctx.close(); }
  });

  await caso("CP-RNF-10", () => conUsuario({}, async ({ ctx, page }) => {
    await sinConexion(ctx, page, true);
    await page.reload(); await page.waitForSelector(".appbar");
    const hechos = [];
    await clic(page, "tab:p16"); hechos.push("catálogo");
    await clic(page, "tab:p18"); await page.selectOption("#ccu", "CAFE"); await page.locator('[data-act="seg"][data-v="cuadrado"]').click(); await llenar(page, "cda", "1,5"); await clic(page, "calc"); await page.waitForSelector("text=Matas por hectárea"); hechos.push("calculadora");
    await clic(page, "tab:p10"); await registrarGasto(page, 9000); await page.waitForSelector("text=Gasto guardado"); hechos.push("gasto");
    await clic(page, "go:p22"); await llenar(page, "jfecha", "20/04/2026"); await llenar(page, "jn", "1"); await llenar(page, "jv", "30000"); await clic(page, "savejor"); hechos.push("jornal");
    await clic(page, "tab:p11"); hechos.push("fincas"); await clic(page, "tab:p20"); hechos.push("finanzas");
    return { texto: `Parte del dispositivo: con modo avión y la app recargada funcionaron ${hechos.length} de ${hechos.length} funciones locales probadas (${hechos.join(", ")}). Parte del servidor (inactividad mensual ≤ 7,2 h): requiere medir un mes de operación con el servidor publicado`, estado: "Pendiente" };
  }).then((t) => t));

  // ---- rendimiento (RNF-01)
  await caso("CP-RNF-01", () => conUsuario({}, async ({ ctx, page }) => {
    const cdp = await ctx.newCDPSession(page);
    await cdp.send("Emulation.setCPUThrottlingRate", { rate: 4 });
    await clic(page, "tab:p18"); await page.selectOption("#ccu", "CAFE"); await page.locator('[data-act="seg"][data-v="cuadrado"]').click();
    const tiempos = [];
    for (let i = 0; i < 20; i++) {
      if (i > 0) { await clic(page, "go:p18"); await page.selectOption("#ccu", "CAFE"); await page.locator('[data-act="seg"][data-v="cuadrado"]').click(); }
      await llenar(page, "cda", (1 + i * 0.05).toFixed(2).replace(".", ","));
      const ms = await page.evaluate(async () => {
        const antes = document.querySelector("#screen").innerText;
        const t0 = performance.now();
        document.querySelector('[data-act="calc"]').click();
        while (document.querySelector("#screen").innerText === antes && performance.now() - t0 < 5000) await new Promise((r) => requestAnimationFrame(r));
        return performance.now() - t0;
      });
      tiempos.push(ms);
    }
    await cdp.send("Emulation.setCPUThrottlingRate", { rate: 1 });
    const ord = [...tiempos].sort((a, b) => a - b);
    const p95 = ord[Math.ceil(0.95 * ord.length) - 1], max = ord[ord.length - 1];
    exigir(p95 <= 2000, `p95 ${p95} ms`);
    return `20 cálculos de matas por hectárea medidos con performance.now() y el procesador 4 veces más lento: p95 = ${p95.toFixed(0)} ms, máximo = ${max.toFixed(0)} ms (meta ≤ 2.000 ms). Medido en el entorno de desarrollo (Chromium sin pantalla), no en un teléfono de 2 GB de RAM`;
  }));

  // ---- accesibilidad (RNF-07): medición automática; no reemplaza a Lighthouse ni a la revisión con usuarios
  await caso("CP-RNF-07", async () => {
    const s = await sesion();
    const cuenta = await crearCuenta(); await sembrar(cuenta);
    try {
      const medir = () => s.page.evaluate(() => {
        const lum = (c) => { const [r, g, b] = c.map((v) => { v /= 255; return v <= 0.03928 ? v / 12.92 : ((v + 0.055) / 1.055) ** 2.4; }); return 0.2126 * r + 0.7152 * g + 0.0722 * b; };
        const parse = (s) => (s.match(/[\d.]+/g) || [0, 0, 0, 1]).map(Number);
        const fondo = (e) => { while (e) { const c = parse(getComputedStyle(e).backgroundColor); if ((c[3] ?? 1) > 0.5) return c; e = e.parentElement; } return [255, 255, 255, 1]; };
        // RNF-07: el texto de contenido mide 18 px o más; las etiquetas secundarias (pestañas, pastillas, insignias y botones
        // segmentados) pueden medir 16 px. Ningún texto baja de 16 px.
        const malos = { letra: [], letra18: [], boton: [], contraste: [] };
        let secundarios = 0;
        let textos = 0, botones = 0;
        const visible = (e) => { const r = e.getBoundingClientRect(); const st = getComputedStyle(e); return r.width > 0 && r.height > 0 && st.visibility !== "hidden" && st.display !== "none"; };
        document.querySelectorAll("#app *, body *").forEach((e) => {
          if (!visible(e)) return;
          const propio = [...e.childNodes].some((n) => n.nodeType === 3 && n.textContent.trim());
          if (propio) {
            textos++;
            const st = getComputedStyle(e), px = parseFloat(st.fontSize);
            if (px < 16) malos.letra.push(`${e.tagName.toLowerCase()}.${e.className} «${e.textContent.trim().slice(0, 25)}» ${px}px`);
            const secundario = e.closest(".tabs, .pill, .badge, .seg, .sr");
            if (secundario) secundarios++;
            if (px < 18 && !secundario) malos.letra18.push(`${e.tagName.toLowerCase()}.${e.className} «${e.textContent.trim().slice(0, 25)}» ${px}px`);
            const f = parse(st.color), b = fondo(e), l1 = lum(f), l2 = lum(b), cr = (Math.max(l1, l2) + 0.05) / (Math.min(l1, l2) + 0.05);
            const grande = px >= 24 || (px >= 18.66 && Number(st.fontWeight) >= 700);
            if (cr < (grande ? 3 : 4.5)) malos.contraste.push(`${e.tagName.toLowerCase()}.${e.className} «${e.textContent.trim().slice(0, 25)}» ${cr.toFixed(2)}:1`);
          }
          if (e.matches("button, a, select, input:not([type=hidden]):not([type=checkbox]), [role=button]")) {
            botones++;
            const r = e.getBoundingClientRect();
            if (r.height < 47.5 || r.width < 47.5) malos.boton.push(`${e.tagName.toLowerCase()}.${e.className} «${(e.textContent || e.id).trim().slice(0, 20)}» ${Math.round(r.width)}×${Math.round(r.height)}`);
          }
        });
        return { textos, botones, malos, secundarios };
      });
      const resultado = {};
      const pantallas = [["Bienvenida", async () => { await s.page.goto(BASE); await s.page.waitForSelector("text=Cultive con cuentas claras"); }],
        ["Registro", async () => { await clic(s.page, "go:p02"); }],
        ["Ingreso", async () => { await s.page.goto(BASE); await s.page.waitForSelector("text=Cultive con cuentas claras"); await clic(s.page, "go:p07"); }],
        ["Panel", async () => { await llenar(s.page, "lmail", cuenta.correo); await llenar(s.page, "lpass", cuenta.clave); await clic(s.page, "login"); await s.page.waitForSelector("text=Resumen del ciclo"); }],
        ["Registrar gasto", async () => { await clic(s.page, "go:p21"); }],
        ["Calculadora", async () => { await clic(s.page, "back"); await clic(s.page, "tab:p18"); }],
        ["Catálogo", async () => { await clic(s.page, "tab:p16"); }]];
      for (const [nombre, ir] of pantallas) { await ir(); await s.page.waitForTimeout(250); resultado[nombre] = await medir(); }
      const sumar = (k) => Object.values(resultado).reduce((n, r) => n + r.malos[k].length, 0);
      const ejemplos = (k) => [...new Set(Object.values(resultado).flatMap((r) => r.malos[k]))].slice(0, 4).join("; ");
      globalThis.__acc = { letra: sumar("letra"), letra18: sumar("letra18"), boton: sumar("boton"), contraste: sumar("contraste") };
      const textosTotal = Object.values(resultado).reduce((n, r) => n + r.textos, 0), botonesTotal = Object.values(resultado).reduce((n, r) => n + r.botones, 0);
      const secTotal = Object.values(resultado).reduce((n, r) => n + r.secundarios, 0);
      const detalle = `Medición automática en ${pantallas.length} pantallas (${textosTotal} textos, ${botonesTotal} botones/campos): texto de contenido menor de 18 px: ${sumar("letra18")}${sumar("letra18") ? " (" + ejemplos("letra18") + ")" : ""}; etiquetas secundarias (pestañas, pastillas, insignias, botones segmentados) medidas: ${secTotal}, todas de 16 px o más; texto menor de 16 px: ${sumar("letra")}${sumar("letra") ? " (" + ejemplos("letra") + ")" : ""}; controles menores de 48 × 48 px: ${sumar("boton")}${sumar("boton") ? " (" + ejemplos("boton") + ")" : ""}; contraste bajo (< 4,5:1): ${sumar("contraste")}${sumar("contraste") ? " (" + ejemplos("contraste") + ")" : ""}. Lighthouse y la revisión manual con WCAG 2.1 AA no se ejecutaron`;
      exigir(sumar("letra") + sumar("letra18") + sumar("boton") + sumar("contraste") === 0, detalle);
      // La medición automática pasa, pero Lighthouse y la revisión con personas no se hicieron: el caso queda pendiente.
      return { texto: detalle, estado: "Pendiente" };
    } finally { await s.ctx.close(); }
  });

  await browser.close();
}

ejecutar().then(() => console.log("\nPlan de pruebas (parte ui) terminado")).catch((e) => { console.error(e); process.exit(1); });
