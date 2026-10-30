const { chromium } = require('playwright');
const OUT = process.env.OUT || require('os').tmpdir() + '/sembrando_e2e';
require('fs').mkdirSync(OUT, { recursive: true });
// Prueba de extremo a extremo en Chromium contra un servidor real (ENTORNO=pruebas para que el código OTP sea 482915).
//   cd backend && ENTORNO=pruebas uvicorn app.main:app --port 8000      (en otra terminal, con la base migrada y cargar_semilla)
//   cd frontend && npm install && npx playwright install chromium && npm run test:e2e
const BASE = process.env.BASE_URL || 'http://localhost:8000/';
// Los campos de fecha usan el calendario del navegador (type=date): se llenan con AAAA-MM-DD. Una fecha inexistente (31/02) no se puede elegir y deja el campo vacío.
const aIso = (id, v) => {
  if (!/(fecha|^cierre)$/.test(id)) return v;
  const m = /^(\d{2})\/(\d{2})\/(\d{4})$/.exec(v);
  if (!m) return v;
  const f = new Date(Date.UTC(+m[3], +m[2] - 1, +m[1]));
  return f.getUTCDate() === +m[1] && f.getUTCMonth() === +m[2] - 1 ? `${m[3]}-${m[2]}-${m[1]}` : "";
};
const API = new URL('api/v1', BASE).toString();
const CORREO = `juan.gomez.${Date.now().toString(36)}@correo.com`;
let pasos = 0;
const ok = (m) => console.log('✔', m);
function assert(c, m) { if (!c) { console.log('✘ FALLA:', m); process.exitCode = 1; throw new Error(m); } ok(m); }

(async () => {
  const browser = await chromium.launch();
  const ctx = await browser.newContext({ viewport: { width: 390, height: 780 }, locale: 'es-CO', serviceWorkers: 'allow' });
  const page = await ctx.newPage();
  const errores = [];
  page.on('console', (m) => { if (m.type() === 'error' && !m.text().startsWith('Failed to load resource')) errores.push(m.text()); });
  page.on('pageerror', (e) => errores.push('pageerror: ' + e.message));
  const txt = () => page.locator('#screen').innerText();
  const shot = (n) => page.screenshot({ path: `${OUT}/${String(++pasos).padStart(2, '0')}_${n}.png` });
  const clickAct = (a) => page.locator(`[data-act="${a}"]`).first().click();
  const llenar = async (id, v) => { await page.fill('#' + id, aIso(id, v)); };

  await page.goto(BASE);
  await page.waitForSelector('text=Cultive con cuentas claras');
  await shot('bienvenida');
  assert((await page.title()) === 'Sembrando Futuro', 'P-01 abre con el título correcto');

  // ---- registro con errores
  await clickAct('go:p02');
  await clickAct('reg');
  let t = await txt();
  assert(t.includes('(V-01)') && t.includes('(V-07)') && t.includes('(V-08)'), 'P-02 muestra V-01, V-07 y V-08 con campos vacíos');
  await shot('registro_errores');

  // ---- registro válido
  await llenar('nombre', 'Juan Gómez'); await llenar('ubic', 'Caloto, Cauca');
  await llenar('correo', CORREO); await llenar('correo2', CORREO);
  await llenar('clave', 'Siembra#2026a'); await page.check('#auth');
  await clickAct('reg');
  await page.waitForSelector('text=Escriba el código');
  await shot('verificar');
  // código incorrecto
  await llenar('otp', '111111'); await clickAct('otpv');
  await page.waitForSelector('text=Código incorrecto');
  assert((await txt()).includes('Le quedan 4 intentos'), 'P-04 V-10 con intentos restantes');
  // reenvío inmediato → V-13
  await clickAct('otpr');
  await page.waitForSelector('text=Espere');
  assert((await txt()).includes('(V-13)'), 'P-04 V-13 al reenviar antes de 60 s');
  await llenar('otp', '482915'); await clickAct('otpv');
  await page.waitForSelector('text=Aún no tiene fincas');
  assert((await txt()).includes('En línea'), 'activa la cuenta e ingresa solo (P-09)');
  await shot('panel_vacio');

  // ---- finca y ciclo (el área, la vigencia y los cultivos viven en el ciclo; no hay lotes)
  await clickAct('go:p12');
  await clickAct('savefinca');
  assert((await txt()).includes('(V-22)'), 'P-12 V-22 sin nombre de finca');
  await llenar('fnom', 'La Esperanza');
  await clickAct('savefinca');
  await page.waitForSelector('text=Primer cultivo');
  await shot('nuevo_ciclo');
  // ciclo con errores
  await llenar('carea', '0'); await llenar('cpend', '120'); await llenar('cfecha', '99/99/2026'); await llenar('cvig', '51');
  await clickAct('savecy');
  t = await txt();
  assert(['V-24', 'V-25', 'V-28', 'V-49', 'V-27'].every((c) => t.includes('(' + c + ')')), 'P-14 V-24, V-25, V-28, V-49 y V-27 (sin cultivo)');
  const fincas = await page.locator('#cfinca option').allTextContents();
  assert(fincas.some((x) => x.includes('La Esperanza')), 'la finca creada aparece en la lista');
  await llenar('cnom', 'Lote Alto'); await llenar('carea', '1'); await llenar('cpend', '12');
  await llenar('cfecha', '15/03/2026'); await llenar('cvig', '7');
  await page.selectOption('#ccult', 'CAFE');
  await page.locator('[data-act="seg"][data-v="cuadrado"]').click();
  await llenar('ca', '1,5');
  await clickAct('savecy');
  await page.waitForSelector('text=Resumen del ciclo');
  t = await txt();
  assert(t.includes('4.445') && t.includes('1,00 ha'), 'P-10 café 1,5 m en 1 ha = 4.445 matas');
  assert(t.includes('Verde') && t.includes('años restantes') && t.includes('15/03/2033'), 'P-10 vigencia de 7 años: fin 15/03/2033 y semáforo verde');
  // área real
  await page.locator('[data-act="tab:p11"]').click();
  await page.locator('[data-act^="area:"]').first().click();
  await page.waitForSelector('text=Área efectiva');
  await llenar('nosemb', '1000');
  assert((await txt()).includes('0,10 ha') && (await txt()).includes('0,90 ha'), 'P-13 convierte 1000 m² en 0,1 ha y calcula 0,9 ha');
  await clickAct('savearea');
  await page.waitForSelector('text=Mis fincas');
  // segundo cultivo en el mismo ciclo (muchos a muchos)
  await page.locator('[data-act^="addcult:"]').first().click();
  await page.waitForSelector('text=Agregar al ciclo');
  await clickAct('savecult');
  assert((await txt()).includes('(V-27)'), 'P-28 V-27 sin cultivo');
  await page.selectOption('#ccult', 'CAFE');
  await clickAct('savecult');
  assert((await txt()).includes('(V-50)'), 'P-28 V-50: el café ya está en el ciclo');
  await page.selectOption('#ccult', 'PLATANO');
  await page.locator('[data-act="seg"][data-v="rectangular"]').click();
  await llenar('ca', '3'); await llenar('cb', '2');
  await clickAct('savecult');
  await page.waitForSelector('text=Cultivo agregado');
  assert((await txt()).includes('Café + Plátano') || (await txt()).includes('Plátano + Café'), 'P-11 el ciclo muestra sus dos cultivos');
  await page.locator('[data-act="tab:p10"]').click();
  await page.waitForSelector('text=Resumen del ciclo');
  t = await txt();
  assert(t.includes('5.500') && t.includes('0,90 ha'), 'P-10 total de matas 5.500 (4.000 de café + 1.500 de plátano) con 0,9 ha');
  assert(t.includes('Costos aproximados') && t.includes('$ 1.600.000') && t.includes('$ 3.320.000'), 'P-10 costos de la ficha del café con 4.000 matas');
  assert(t.includes('por validar'), 'P-10 avisa que los valores del plátano están por validar');
  await shot('panel_ciclo');

  // ---- finanzas
  await clickAct('go:p21');
  await llenar('gfecha', '12/04/2026'); await page.selectOption('#gcat', 'abonos'); await llenar('gval', '100000'); await llenar('gobs', 'Abono orgánico');
  await clickAct('savegas');
  await page.waitForSelector('text=Gasto guardado');
  await clickAct('go:p22');
  await llenar('jfecha', '20/04/2026'); await llenar('jn', '2'); await llenar('jv', '25000');
  assert((await txt()).includes('$ 50.000'), 'P-22 muestra el costo 2 × 25.000 = 50.000');
  await clickAct('savejor');
  await clickAct('go:p23');
  await llenar('ifecha', '10/09/2026'); await llenar('iq', '4'); await llenar('ip', '125000');
  await clickAct('saveinc');
  assert((await txt()).includes('(V-27)'), 'P-23 V-27: con dos cultivos hay que elegir cuál se vendió');
  await page.selectOption('#icult', 'CAFE');
  await llenar('ifecha', '10/09/2026'); await llenar('iq', '4'); await llenar('ip', '125000');
  assert((await txt()).includes('$ 500.000'), 'P-23 muestra el total 500.000');
  await clickAct('saveinc');
  await page.waitForSelector('text=Ingreso guardado');
  t = await txt();
  assert(t.includes('$ 350.000') && t.includes('233,3 %'), 'P-20 utilidad 350.000 y rentabilidad 233,3 %');
  await shot('finanzas');
  // validaciones de finanzas
  await clickAct('go:p21'); await llenar('gfecha', '01/01/2020'); await llenar('gval', '0'); await clickAct('savegas');
  t = await txt();
  assert(t.includes('(V-47)') && t.includes('(V-35)') && t.includes('(V-37)'), 'P-21 V-47, V-35 y V-37');
  await clickAct('back');

  // ---- sincronización con el servidor real
  await page.waitForFunction(() => !document.querySelector('[aria-label="Estado de conexión"]').textContent.includes('·'), null, { timeout: 15000 });
  ok('los registros se enviaron solos (sin pendientes)');
  const sesion = await page.evaluate(() => new Promise((res) => { const r = indexedDB.open('sembrando_futuro'); r.onsuccess = () => { const q = r.result.transaction('sesion').objectStore('sesion').get('actual'); q.onsuccess = () => res(q.result); }; }));
  const pull = await (await fetch(API + '/sync/pull', { headers: { Authorization: 'Bearer ' + sesion.token } })).json();
  const tipos = pull.registros.map((x) => x.tipo).sort().join(',');
  assert(tipos === 'ciclo,ciclo_cultivo,ciclo_cultivo,finca,gasto,ingreso,jornal', 'el servidor recibió finca, ciclo, 2 cultivos del ciclo, gasto, jornal e ingreso: ' + tipos);
  const ciclo = pull.registros.find((x) => x.tipo === 'ciclo');
  const res = await (await fetch(`${API}/ciclos/${ciclo.id}/resumen`, { headers: { Authorization: 'Bearer ' + sesion.token } })).json();
  assert(res.utilidad_neta_cop === 350000 && res.total_matas === 5500 && res.cultivos.length === 2 && res.ciclo.semaforo === 'VERDE' && res.ciclo.fecha_fin_estimada === '2033-03-15' && res.rentabilidad_pct === 233.3 && res.utilidad_por_ha_cop === 388889, 'R-01 coincide con los números de la pantalla');

  // ---- sin conexión
  await ctx.setOffline(true);
  await page.evaluate(() => window.dispatchEvent(new Event('offline')));
  await clickAct('go:p21');
  await llenar('gfecha', '25/04/2026'); await page.selectOption('#gcat', 'transporte'); await llenar('gval', '30000');
  await clickAct('savegas');
  await page.waitForSelector('text=Gasto guardado');
  t = await txt();
  assert(t.includes('Sin conexión') && t.includes('· 1'), 'sin conexión: el gasto queda pendiente (1)');
  await shot('sin_conexion');
  // recargar sin internet: la app abre desde el dispositivo
  await page.waitForTimeout(500);
  await page.reload();
  await page.waitForSelector('.appbar');
  t = await txt();
  assert(t.includes('Finanzas') || t.includes('Inicio'), 'la app abre sin internet y conserva la sesión');
  assert(t.includes('Sin conexión') || t.includes('En línea'), 'muestra estado de conexión');
  await ctx.setOffline(false);
  await page.evaluate(() => window.dispatchEvent(new Event('online')));
  await page.waitForFunction(() => !document.querySelector('[aria-label="Estado de conexión"]').textContent.includes('·'), null, { timeout: 20000 });
  ok('al volver internet, el gasto pendiente se envía solo');
  const pull2 = await (await fetch(API + '/sync/pull', { headers: { Authorization: 'Bearer ' + sesion.token } })).json();
  assert(pull2.registros.filter((x) => x.tipo === 'gasto').length === 2, 'el servidor tiene los 2 gastos');

  // ---- eliminar y deshacer
  await page.locator('[data-act="tab:p20"]').click();
  await page.locator('.fila .tap', { hasText: 'Transporte' }).first().click();
  await page.waitForSelector('text=Editar registro');
  await clickAct('del');
  await page.waitForSelector('text=Registro eliminado');
  await shot('eliminado');
  assert(!(await txt()).includes('30.000') || (await page.locator('.fila', { hasText: 'Transporte' }).count()) === 0, 'el gasto eliminado desaparece de la lista');
  await clickAct('undo');
  await page.waitForSelector('.fila:has-text("Transporte")');
  ok('Deshacer devuelve el gasto');

  // ---- catálogo y calculadora (sin internet)
  await page.locator('[data-act="tab:p16"]').click();
  assert((await txt()).includes('Café') && (await txt()).includes('Yuca') && !(await txt()).includes('Cacao'), 'P-16 lista los 3 cultivos');
  await page.locator('[data-act="tab:p18"]').click();
  await page.selectOption('#ccu', 'CAFE');
  await page.locator('[data-act="seg"][data-v="cuadrado"]').click();
  await llenar('cda', '2,5'); await clickAct('calc');
  await page.waitForSelector('text=Matas por hectárea');
  t = await txt();
  assert(t.includes('1.600,00') && t.includes('(V-34)'), 'P-19 café cuadrado 2,5 m = 1.600 matas/ha con advertencia V-34');
  await shot('calculadora');

  // ---- cerrar sesión con pendientes y volver
  await page.locator('[data-act="go:p26"]').click();
  await clickAct('outask');
  await page.locator('[data-act="outyes"]').or(page.getByText('Cultive con cuentas claras')).first().waitFor();
  if (await page.locator('[data-act="outyes"]').count()) { assert((await txt()).includes('(V-20)'), 'P-26 avisa V-20 si hay registros sin enviar'); await clickAct('outyes'); }
  await page.waitForSelector('text=Cultive con cuentas claras');
  ok('cierra sesión (sin pendientes no pide confirmación)');
  const rev = await fetch(API + '/sync/pull', { headers: { Authorization: 'Bearer ' + sesion.token } });
  assert(rev.status === 401, 'el servidor revocó el token (A-06)');
  await clickAct('go:p07');
  await llenar('lmail', CORREO); await llenar('lpass', 'mala'); await clickAct('login');
  await page.waitForSelector('text=Correo o clave incorrectos');
  ok('P-07 V-17 con clave incorrecta');
  await llenar('lpass', 'Siembra#2026a'); await clickAct('login');
  await page.waitForSelector('text=Resumen del ciclo');
  assert((await txt()).includes('$ 320.000'), 'al ingresar de nuevo se recuperan los datos (del dispositivo y del servidor)');

  assert(errores.length === 0, 'sin errores en la consola del navegador' + (errores.length ? ': ' + errores.join(' | ') : ''));
  await browser.close();
  console.log('\nE2E COMPLETO');
})().catch((e) => { console.error(e); process.exit(1); });
