// Estado de la aplicación: datos del usuario en memoria (copia de IndexedDB), selectores y escritura con marca de pendiente.
import { db, meta } from "./db/db.js";
import { SEMILLA } from "./datos/semilla_catalogo.js";
import { ahoraISOms } from "./calculos/formato.js";
import { calcularUtilidad, costoJornal, matasPorHa, matasPorLote, totalIngreso } from "./calculos/formulas.js";

export const TIPOS = ["finca", "ciclo", "ciclo_cultivo", "gasto", "jornal", "ingreso"];
const LISTA = { finca: "fincas", ciclo: "ciclos", ciclo_cultivo: "ciclo_cultivos", gasto: "gastos", jornal: "jornales", ingreso: "ingresos" };

/** Estado de la pantalla. */
export const S = {
  pantalla: "p01", pila: [], usuario: null, enLinea: navigator.onLine, f: {}, e: {}, ctx: {}, aviso: null, ocupado: false,
  sel: { finca: null, ciclo: null }, banner: null, activacion: null, claveTemporal: null, sincronizando: false, ultimaSync: null,
};
/** Copia en memoria de los registros del usuario que inició sesión. */
export const D = { fincas: [], ciclos: [], ciclo_cultivos: [], gastos: [], jornales: [], ingresos: [], catalogo: [] };

let avisarCambio = () => {};
export const alCambiarDatos = (fn) => { avisarCambio = fn; };

export const uuid = () => (crypto.randomUUID ? crypto.randomUUID() : "id-" + Math.random().toString(16).slice(2) + Date.now().toString(16));

// ---------------------------------------------------------------- catálogo
const SEMILLA_POR_CODIGO = Object.fromEntries(SEMILLA.cultivos.map((c) => [c.codigo, c]));
/** La ficha del servidor (C-01) no trae los textos de advertencia: se toman de la semilla incluida en la aplicación. */
const unir = (c) => ({ ...(SEMILLA_POR_CODIGO[c.codigo] || {}), ...c });
export async function cargarCatalogo() {
  const guardado = await db.catalogo.toArray();
  const base = SEMILLA.cultivos.map((c) => unir(guardado.find((g) => g.codigo === c.codigo) || c));
  guardado.filter((g) => !SEMILLA_POR_CODIGO[g.codigo]).forEach((g) => base.push(g));
  D.catalogo = base.sort((a, b) => a.nombre.localeCompare(b.nombre, "es"));
}
export const cultivo = (codigo) => D.catalogo.find((c) => c.codigo === codigo);

// ---------------------------------------------------------------- carga y escritura
export async function cargarDatos(uid) {
  const todos = await db.registros.where("uid").equals(uid).toArray();
  for (const t of TIPOS) D[LISTA[t]] = todos.filter((r) => r.tipo === t);
}
export function vaciarDatos() { for (const t of TIPOS) D[LISTA[t]] = []; }
export const lista = (tipo) => D[LISTA[tipo]];
export const todosLosRegistros = () => TIPOS.flatMap((t) => lista(t));

/** Crea o cambia un registro: lo marca PENDIENTE con un updated_at nuevo y lo guarda en el dispositivo. */
export async function guardar(tipo, obj, momento = ahoraISOms()) {
  const r = { ...obj, tipo, uid: S.usuario.id, updated_at: momento, sync: "PENDIENTE", error: null };
  const arr = lista(tipo);
  const i = arr.findIndex((x) => x.id === r.id);
  if (i >= 0) arr[i] = r; else arr.push(r);
  await db.registros.put(r);
  avisarCambio();
  return r;
}
/** Elimina de forma lógica (solo gastos, jornales e ingresos). */
export const eliminar = (tipo, r) => guardar(tipo, { ...r, eliminado: true });
export const restaurar = (tipo, r) => guardar(tipo, { ...r, eliminado: false });
/** Quita del dispositivo un registro que el servidor rechazó y nunca se aceptó. */
export async function descartar(tipo, id) {
  const arr = lista(tipo);
  const i = arr.findIndex((x) => x.id === id);
  if (i >= 0) arr.splice(i, 1);
  await db.registros.delete(id);
}

// ---------------------------------------------------------------- selectores (solo registros no eliminados)
const vivos = (a) => a.filter((x) => !x.eliminado);
export const misFincas = () => D.fincas;
export const misCiclos = () => D.ciclos;
export const finca = (id) => D.fincas.find((f) => f.id === id);
export const ciclo = (id) => D.ciclos.find((c) => c.id === id);
export const gastosDe = (id) => vivos(D.gastos).filter((x) => x.ciclo_id === id);
export const jornalesDe = (id) => vivos(D.jornales).filter((x) => x.ciclo_id === id);
export const ingresosDe = (id) => vivos(D.ingresos).filter((x) => x.ciclo_id === id);
export const ciclosDe = (idFinca) => D.ciclos.filter((c) => c.finca_id === idFinca);
/** Cultivos de un ciclo (tabla intermedia CICLO_CULTIVO), cada uno con su marco y distancias. */
export const cultivosDe = (idCiclo) => vivos(D.ciclo_cultivos).filter((x) => x.ciclo_id === idCiclo);
export const nombresCultivos = (idCiclo) => cultivosDe(idCiclo).map((x) => cultivo(x.cultivo_codigo)?.nombre || x.cultivo_codigo).join(" + ");

export function finanzas(idCiclo) {
  const c = ciclo(idCiclo);
  const gs = gastosDe(idCiclo).map((x) => x.valor_cop);
  const js = jornalesDe(idCiclo).map((x) => costoJornal(x.jornales, x.valor_diario_cop));
  const is = ingresosDe(idCiclo).map((x) => totalIngreso(x.cantidad, x.precio_unitario_cop));
  const r = calcularUtilidad([...gs, ...js], is, c.area_efectiva_ha);
  return { g: r.gastos, i: r.ingresos, u: r.utilidad, r: r.rentabilidad, ha: r.porHa };
}
/** Matas de un cultivo del ciclo (null si no tiene marco). Cada cultivo ocupa el área efectiva con su propio marco. */
export function matasDe(cc) {
  const c = ciclo(cc.ciclo_id);
  if (!cc.marco || cc.dist_a_m == null) return null;
  return matasPorLote(matasPorHa(cc.marco, cc.dist_a_m, cc.dist_b_m), c.area_efectiva_ha);
}
/** Total de matas del ciclo: suma de los cultivos que tienen marco (null si ninguno). */
export function totalMatas(idCiclo) {
  const v = cultivosDe(idCiclo).map(matasDe).filter((x) => x !== null);
  return v.length ? v.reduce((a, b) => a + b, 0) : null;
}
export const pendientes = () => todosLosRegistros().filter((r) => r.sync === "PENDIENTE");
export const rechazados = () => todosLosRegistros().filter((r) => r.sync === "RECHAZADO");
export const pendCount = () => pendientes().length;

// ---------------------------------------------------------------- sesión
export async function guardarSesion(s) { await db.sesion.put({ k: "actual", ...s }); }
export const leerSesion = async () => db.sesion.get("actual");
export const borrarSesion = async () => db.sesion.delete("actual");
export async function idDispositivo() {
  let id = await meta("dispositivo_id");
  if (!id) { id = uuid(); await meta("dispositivo_id", id); }
  return id;
}
