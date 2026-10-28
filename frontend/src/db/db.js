// Base de datos local (IndexedDB). Es un envoltorio mínimo con la misma forma de uso que Dexie (dexie.org):
//   db.registros.put(x) · .get(k) · .bulkPut([]) · .delete(k) · .clear() · .toArray() · .where("tipo").equals(v).toArray()
// Sirve para que la PWA funcione sin dependencias ni paso de compilación. Si se prefiere Dexie, basta cambiar este archivo por:
//   import Dexie from "dexie"; export const db = new Dexie("sembrando_futuro");
//   db.version(1).stores({ registros: "id,tipo,uid,sync", catalogo: "codigo", meta: "k", sesion: "k" });
const NOMBRE = "sembrando_futuro";
const VERSION = 1;
const ESQUEMA = {
  registros: { clave: "id", indices: ["tipo", "uid", "sync"] },  // finca, ciclo, ciclo_cultivo, gasto, jornal e ingreso (campo tipo)
  catalogo: { clave: "codigo", indices: [] },                    // fichas de cultivo recibidas de C-01
  meta: { clave: "k", indices: [] },                             // valores sueltos: cursor de S-02, id del dispositivo, etc.
  sesion: { clave: "k", indices: [] },                           // sesión actual (token y datos de la cuenta)
};

let abierta = null;
function abrir() {
  if (abierta) return abierta;
  abierta = new Promise((resolver, rechazar) => {
    const pedido = indexedDB.open(NOMBRE, VERSION);
    pedido.onupgradeneeded = () => {
      const base = pedido.result;
      for (const [nombre, t] of Object.entries(ESQUEMA)) {
        if (base.objectStoreNames.contains(nombre)) continue;
        const almacen = base.createObjectStore(nombre, { keyPath: t.clave });
        t.indices.forEach((i) => almacen.createIndex(i, i));
      }
    };
    pedido.onsuccess = () => resolver(pedido.result);
    pedido.onerror = () => rechazar(pedido.error);
    pedido.onblocked = () => rechazar(new Error("La base de datos está bloqueada por otra pestaña."));
  });
  return abierta;
}

const promesa = (pedido) => new Promise((ok, mal) => { pedido.onsuccess = () => ok(pedido.result); pedido.onerror = () => mal(pedido.error); });

class Tabla {
  constructor(nombre) { this.nombre = nombre; }
  async _almacen(modo) { const b = await abrir(); const tx = b.transaction(this.nombre, modo); return { tx, a: tx.objectStore(this.nombre), fin: new Promise((ok, mal) => { tx.oncomplete = ok; tx.onerror = () => mal(tx.error); tx.onabort = () => mal(tx.error); }) }; }
  async get(clave) { const { a } = await this._almacen("readonly"); return promesa(a.get(clave)); }
  async put(obj) { const { a, fin } = await this._almacen("readwrite"); a.put(obj); await fin; return obj[ESQUEMA[this.nombre].clave]; }
  async bulkPut(lista) { const { a, fin } = await this._almacen("readwrite"); lista.forEach((o) => a.put(o)); await fin; }
  async delete(clave) { const { a, fin } = await this._almacen("readwrite"); a.delete(clave); await fin; }
  async clear() { const { a, fin } = await this._almacen("readwrite"); a.clear(); await fin; }
  async toArray() { const { a } = await this._almacen("readonly"); return promesa(a.getAll()); }
  async count() { const { a } = await this._almacen("readonly"); return promesa(a.count()); }
  where(indice) {
    return { equals: (valor) => ({ toArray: async () => { const { a } = await this._almacen("readonly"); return promesa(a.index(indice).getAll(valor)); } }) };
  }
}

export const db = { registros: new Tabla("registros"), catalogo: new Tabla("catalogo"), meta: new Tabla("meta"), sesion: new Tabla("sesion") };
export const listo = () => abrir();
export async function meta(k, valor) {
  if (valor === undefined) return (await db.meta.get(k))?.v;
  if (valor === null) return db.meta.delete(k);
  return db.meta.put({ k, v: valor });
}
