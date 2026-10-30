// Sincronización con el servidor: S-01 (enviar), S-02 (recibir) y C-01 (catálogo). Funciona sin conexión: lo pendiente espera.
import { llamar, ErrorRed, error } from "./api.js";
import { db, meta } from "./db/db.js";
import { S, TIPOS, cargarCatalogo, idDispositivo, lista, todosLosRegistros } from "./estado.js";

const LIMITE = 500;
const SOLAPE_MS = 10 * 60 * 1000; // al pedir cambios se retrocede 10 min: repetir un registro no daña (es idempotente) y evita perder uno viejo
let enCurso = null;
let temporizador = null;
let alTerminar = () => {};
let alVencerSesion = () => {};
/** Recibe las funciones que se llaman al terminar una sincronización y cuando la sesión venció. */
export const configurarSync = ({ terminar, sesionVencida }) => { alTerminar = terminar; alVencerSesion = sesionVencida; };

/** Convierte un registro local en el formato de S-01: separa los campos de control (id, tipo, fecha, eliminado) de los datos. */
export function datosDeEnvio(r) {
  const { id, tipo, uid, sync, error: _e, updated_at, eliminado, ...datos } = r;
  return { tipo, id, updated_at, eliminado: !!eliminado, datos };
}
/** Convierte un registro del servidor (S-01/S-02) en el formato local. */
export const aLocal = (x, uid) => ({ ...x.datos, id: x.id, tipo: x.tipo, uid, updated_at: x.updated_at, eliminado: !!x.eliminado, sync: "OK", error: null });

/** Pide una sincronización en un momento; varias peticiones seguidas se juntan en una. */
export function pedirSync(espera = 1500) {
  clearTimeout(temporizador);
  temporizador = setTimeout(() => { sincronizar().catch(() => {}); }, espera);
}

/** Sincroniza ahora. Si ya hay una sincronización en curso, devuelve esa misma (nunca corren dos a la vez). */
export function sincronizar() {
  if (enCurso) return enCurso;
  enCurso = ejecutar().finally(() => { enCurso = null; S.sincronizando = false; alTerminar(); });
  return enCurso;
}

/** Si se cerró sesión sin conexión, avisa al servidor ahora para que revoque aquel token. */
async function revocarPendiente() {
  const t = await meta("salida_pendiente");
  if (!t) return;
  try {
    const r = await llamar("POST", "/auth/salida", { token: t });
    if (r.estado < 500 && r.estado !== 429) await meta("salida_pendiente", null);
  } catch { /* se intenta en la siguiente conexión */ }
}

/** Respuesta con falla (sesión vencida u otro error) o null si el servidor respondió 200. */
function fallaDeRespuesta(r) {
  if (r.estado === 401) { alVencerSesion(); return { estado: "sesion_vencida" }; }
  if (r.estado !== 200) return { estado: "falla", error: error(r) };
  return null;
}

/** 1. Envía lo pendiente (S-01), en lotes de hasta 500 y en el orden finca → ciclo → cultivos del ciclo → movimientos. */
async function enviarPendientes(token) {
  const orden = Object.fromEntries(TIPOS.map((t, i) => [t, i]));
  const pend = todosLosRegistros().filter((r) => r.sync === "PENDIENTE").sort((a, b) => orden[a.tipo] - orden[b.tipo] || a.updated_at.localeCompare(b.updated_at));
  for (let i = 0; i < pend.length; i += LIMITE) {
    const trozo = pend.slice(i, i + LIMITE);
    const r = await llamar("POST", "/sync/push", { token, cuerpo: { dispositivo_id: await idDispositivo(), enviado_en: new Date().toISOString(), registros: trozo.map(datosDeEnvio) } });
    const falla = fallaDeRespuesta(r);
    if (falla) return falla;
    await aplicarResultados(trozo, r.datos.resultados);
  }
  return null;
}

/** 2. Recibe los cambios del servidor (S-02) hasta que no haya más. */
async function recibirCambios(token) {
  const cursor = await meta("cursor_pull");
  let desde = cursor ? new Date(Date.parse(cursor) - SOLAPE_MS).toISOString() : undefined;
  for (let vueltas = 0; vueltas < 200; vueltas++) {
    const r = await llamar("GET", "/sync/pull", { token, consulta: { desde, limite: LIMITE } });
    const falla = fallaDeRespuesta(r);
    if (falla) return falla;
    const regs = r.datos.registros;
    await aplicarDelServidor(regs);
    if (regs.length) { desde = regs[regs.length - 1].updated_at; await meta("cursor_pull", desde); }
    if (!r.datos.hay_mas) {
      if (!regs.length && !cursor) await meta("cursor_pull", r.datos.servidor_ahora);
      break;
    }
  }
  return null;
}

/** Orden de la sincronización: 1) enviar lo pendiente, 2) recibir cambios, 3) actualizar el catálogo. Sin conexión no hace nada
 *  y lo pendiente espera; un error de red no borra nada. */
async function ejecutar() {
  if (!S.enLinea) return { estado: "sin_conexion" };
  await revocarPendiente();
  if (!S.usuario) return { estado: "sin_sesion" };
  S.sincronizando = true;
  const token = S.usuario.token;
  try {
    const falla = (await enviarPendientes(token)) || (await recibirCambios(token));
    if (falla) return falla;
    // 3. catálogo (C-01)
    await actualizarCatalogo(token);
    S.ultimaSync = Date.now();
    await meta("ultima_sync", S.ultimaSync);
    return { estado: "ok" };
  } catch (e) {
    if (e instanceof ErrorRed) return { estado: "sin_conexion" };
    console.error(e);
    return { estado: "falla" };
  }
}

/** Marca un registro enviado según la respuesta del servidor; devuelve true si cambió. */
function aplicarResultado(actual, enviado, res) {
  // si mientras se enviaba la persona volvió a editar el registro, sigue pendiente
  if (actual.updated_at !== enviado.updated_at) return false;
  if (res.estado === "ACEPTADO") { actual.sync = "OK"; actual.error = null; return true; }
  if (res.estado === "ACTUALIZADO_POR_SERVIDOR" && res.registro) { Object.assign(actual, aLocal(res.registro, enviado.uid)); return true; }
  if (res.estado === "RECHAZADO") { actual.sync = "RECHAZADO"; actual.error = { codigo: res.codigo, mensaje: res.mensaje }; return true; }
  return false;
}

/** Aplica la respuesta de S-01 a los registros enviados y los guarda en IndexedDB. */
async function aplicarResultados(enviados, resultados) {
  const porId = Object.fromEntries(resultados.map((x) => [x.id, x]));
  const cambios = [];
  for (const r of enviados) {
    const res = porId[r.id];
    const actual = res && lista(r.tipo).find((x) => x.id === r.id);
    if (actual && aplicarResultado(actual, r, res)) cambios.push(actual);
  }
  if (cambios.length) await db.registros.bulkPut(cambios);
}

/** Última escritura gana: un cambio local pendiente o rechazado más nuevo se conserva y se enviará. */
const conservaLocal = (local, x) => !!local && (local.sync === "PENDIENTE" || local.sync === "RECHAZADO") && local.updated_at > x.updated_at;

/** Guarda en el teléfono los registros que llegaron del servidor (S-02), salvo los que tienen un cambio local más nuevo. */
async function aplicarDelServidor(registros) {
  const cambios = [];
  for (const x of registros) {
    if (!TIPOS.includes(x.tipo)) continue;
    const arr = lista(x.tipo);
    const i = arr.findIndex((r) => r.id === x.id);
    if (conservaLocal(i >= 0 ? arr[i] : null, x)) continue;
    const nuevo = aLocal(x, S.usuario.id);
    if (i >= 0) arr[i] = nuevo; else arr.push(nuevo);
    cambios.push(nuevo);
  }
  if (cambios.length) await db.registros.bulkPut(cambios);
}

/** Pide al servidor solo los cultivos que cambiaron desde la última vez (C-01); con 304 no hay nada nuevo. */
async function actualizarCatalogo(token) {
  const desde = await meta("catalogo_actualizado_en");
  const r = await llamar("GET", "/catalogo", { token, consulta: { desde } });
  if (r.estado === 304 || r.estado !== 200) return;
  await db.catalogo.bulkPut(r.datos.cultivos);
  await meta("catalogo_actualizado_en", r.datos.actualizado_en);
  await cargarCatalogo();
}
