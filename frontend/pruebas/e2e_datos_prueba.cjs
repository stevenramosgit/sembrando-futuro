// Segunda prueba de extremo a extremo: usa las cuentas y datos de prueba del documento 19 (python -m app.cli cargar_prueba, ENTORNO=pruebas).
const { chromium } = require('playwright');
const BASE = process.env.BASE_URL || 'http://localhost:8000/';
const API = new URL('api/v1', BASE).toString();
const ok = (m) => console.log('✔', m);
function assert(c, m) { if (!c) { console.log('✘ FALLA:', m); process.exitCode = 1; throw new Error(m); } ok(m); }

(async () => {
  const browser = await chromium.launch();
  const ctx = await browser.newContext({ viewport: { width: 390, height: 780 }, locale: 'es-CO' });
  const page = await ctx.newPage();
  const errores = [];
  page.on('console', (m) => { if (m.type() === 'error' && !m.text().startsWith('Failed to load resource')) errores.push(m.text()); });
  page.on('pageerror', (e) => errores.push('pageerror: ' + e.message));
  const txt = () => page.locator('#screen').innerText();
  const clickAct = (a) => page.locator(`[data-act="${a}"]`).first().click();
  const llenar = (id, v) => page.fill('#' + id, v);
  const entrar = async (correo, clave) => { await page.waitForSelector('#lmail, [data-act="go:p07"], [data-act="outyes"]'); if (await page.locator('[data-act="outyes"]').count()) { await clickAct('outyes'); await page.waitForSelector('#lmail, [data-act="go:p07"]'); } if (await page.locator('[data-act="go:p07"]').count()) await clickAct('go:p07'); await llenar('lmail', correo); await llenar('lpass', clave); await clickAct('login'); };

  await page.goto(BASE);
  await page.waitForSelector('text=Cultive con cuentas claras');

  // ---- bloqueo de Carlos (5 intentos fallidos ya cumplidos) y cuenta de administración
  await entrar('carlos.ruiz@correo.com', 'Tierra#2026d');
  await page.waitForSelector('text=Cuenta bloqueada por 15 minutos');
  assert((await txt()).includes('(V-18)') && /a las \d\d:\d\d/.test(await txt()), 'P-07 V-18 para Carlos con la hora de desbloqueo');
  await llenar('lmail', 'admin.proyecto@correo.com'); await llenar('lpass', 'Cafe#Cauca2026');
  await clickAct('login');
  await page.waitForTimeout(1500);
  const t0 = await txt();
  assert(t0.includes('Ingresar') || t0.includes('administración'), 'la cuenta ADMIN no abre la PWA (o no existe en la base de datos de prueba)');

  // ---- cuenta pendiente: Pedro debe verificar el código
  await llenar('lmail', 'pedro.gomez@correo.com'); await llenar('lpass', 'Cultivo#2026b'); await clickAct('login');
  await page.waitForSelector('text=Escriba el código');
  assert((await txt()).includes('(V-19)'), 'P-07 → P-04 con V-19 para una cuenta pendiente');
  await llenar('otp', '482915'); await clickAct('otpv');
  await page.waitForSelector('text=Aún no tiene fincas');
  ok('Pedro activa su cuenta con el código 482915');
  await clickAct('go:p26'); await clickAct('outask');

  // ---- María con sus datos del servidor
  await entrar('maria.perez@correo.com', 'Siembra#2026a');
  await page.waitForSelector('text=Resumen del ciclo');
  await page.waitForFunction(() => document.body.innerText.includes('En línea'));
  await page.locator('[data-act="tab:p11"]').click();
  await page.waitForSelector('text=La Esperanza', { timeout: 15000 });
  const fincas = await txt();
  assert(fincas.includes('La Esperanza') && fincas.includes('El Mirador') && fincas.includes('Lote Alto') && fincas.includes('Lote Bajo'), 'P-11 trae las fincas y los ciclos (con su nombre de lote) de María desde el servidor (S-02)');
  await page.locator('[data-act="tab:p20"]').click();
  const ciclos = await page.locator('#selCycle option').allTextContents();
  assert(ciclos.length === 3, 'P-20 trae los 3 ciclos de María: ' + ciclos.join(' | '));
  const cafe = ciclos.findIndex((c) => c.includes('La Esperanza · Lote Alto · Café'));
  await page.selectOption('#selCycle', { index: cafe });
  t = await txt();
  assert(t.includes('$ 150.000') && t.includes('$ 500.000') && t.includes('233,3 %'), 'ciclo de café: gastos 150.000, ingresos 500.000, rentabilidad 233,3 % (documento 19)');

  // ---- cerrar un ciclo sin ingresos pide confirmación (V-30), y luego no admite registros (V-31)
  await page.locator('[data-act="tab:p11"]').click();
  await page.locator('.row:has-text("Plátano") [data-act^="close:"]').click();   // plátano: activo y sin ingresos
  await page.waitForSelector('text=Cerrar ciclo');
  await clickAct('closego');
  await page.waitForSelector('text=Este ciclo no tiene ingresos');
  assert((await txt()).includes('(V-30)'), 'P-15 avisa V-30');
  await clickAct('closeyes');
  await page.waitForSelector('text=Balance final');
  ok('P-15 cierra el ciclo después de confirmar');
  await clickAct('goroot:p10');
  await page.locator('[data-act="tab:p20"]').click();
  const platano = (await page.locator('#selCycle option').allTextContents()).findIndex((c) => c.includes('Plátano') && c.includes('cerrado'));
  await page.selectOption('#selCycle', { index: platano });
  assert((await txt()).includes('Ciclo cerrado: no admite nuevos registros'), 'P-20 indica que el ciclo cerrado no admite registros');
  await clickAct('go:p21'); await llenar('gfecha', '10/03/2026'); await page.selectOption('#gcat', 'abonos'); await llenar('gval', '1000'); await clickAct('savegas');
  assert((await txt()).includes('(V-31)'), 'P-21 rechaza el gasto en un ciclo cerrado (V-31)');
  await page.waitForFunction(() => !document.querySelector('[aria-label="Estado de conexión"]').textContent.includes('·'), null, { timeout: 15000 });

  // ---- sesión revocada por el administrador (V-46): la app conserva los datos
  const sesion = await page.evaluate(() => new Promise((res) => { const r = indexedDB.open('sembrando_futuro'); r.onsuccess = () => { const q = r.result.transaction('sesion').objectStore('sesion').get('actual'); q.onsuccess = () => res(q.result); }; }));
  await fetch(API + '/auth/salida', { method: 'POST', headers: { Authorization: 'Bearer ' + sesion.token } });
  await clickAct('back');
  await page.locator('[data-act="tab:p20"]').click();
  await page.selectOption('#selCycle', { index: cafe });
  await clickAct('go:p21'); await llenar('gfecha', '30/04/2026'); await page.selectOption('#gcat', 'otros'); await llenar('gval', '5000'); await clickAct('savegas');
  await page.waitForSelector('text=Su sesión venció', { timeout: 15000 });
  assert((await txt()).includes('(V-46)'), 'al revocar el token, la sincronización lleva a P-07 con V-46');
  await llenar('lpass', 'Siembra#2026a'); await clickAct('login');
  await page.waitForSelector('text=Resumen del ciclo');
  await page.locator('[data-act="tab:p20"]').click();
  await page.waitForFunction(() => !document.querySelector('[aria-label="Estado de conexión"]').textContent.includes('·'), null, { timeout: 15000 });
  ok('el gasto hecho con la sesión vencida se envió al ingresar de nuevo (los datos se conservaron)');
  const pull = await (await fetch(API + '/sync/pull', { headers: { Authorization: 'Bearer ' + (await page.evaluate(() => new Promise((res) => { const r = indexedDB.open('sembrando_futuro'); r.onsuccess = () => { const q = r.result.transaction('sesion').objectStore('sesion').get('actual'); q.onsuccess = () => res(q.result.token); }; }))) } })).json();
  assert(pull.registros.some((x) => x.tipo === 'gasto' && x.datos.valor_cop === 5000), 'el servidor tiene el gasto de 5.000');

  // ---- cinco claves malas: bloqueo
  await clickAct('go:p26'); await clickAct('outask');
  await page.waitForSelector('[data-act="outyes"], [data-act="go:p07"]', { state: 'attached' });
  if (await page.locator('[data-act="outyes"]').count()) await clickAct('outyes');
  await page.waitForSelector('text=Cultive con cuentas claras');
  for (let i = 0; i < 5; i++) { await entrar('luz.mena@correo.com', 'Mala#Clave2026'); await page.waitForTimeout(250); if (i < 4) await page.waitForSelector('text=Correo o clave incorrectos'); }
  await page.waitForSelector('text=Cuenta bloqueada', { timeout: 5000 });
  ok('5 claves malas bloquean la cuenta (V-18), exista o no la cuenta (Luz fue eliminada por limpieza)');

  assert(errores.length === 0, 'sin errores en la consola' + (errores.length ? ': ' + errores.join(' | ') : ''));
  await browser.close();
  console.log('\nE2E DATOS DE PRUEBA COMPLETO');
})().catch((e) => { console.error(e); process.exit(1); });
