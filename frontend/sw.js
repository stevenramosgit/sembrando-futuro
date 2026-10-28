// Service Worker: guarda la aplicación en el dispositivo para que abra sin internet. Las llamadas a la API nunca se guardan.
// Al cambiar cualquier archivo de la aplicación, suba el número de VERSION para que los teléfonos descarguen la versión nueva.
const VERSION = "sf-v6";
const ARCHIVOS = [
  "./",
  "index.html",
  "manifest.webmanifest",
  "icons/apple-touch-icon.png",
  "icons/icon-192.png",
  "icons/icon-512.png",
  "icons/icon-maskable-512.png",
  "src/api.js",
  "src/app.js",
  "src/calculos/formato.js",
  "src/calculos/formulas.js",
  "src/calculos/validaciones.js",
  "src/config.js",
  "src/datos/mensajes.js",
  "src/datos/semilla_catalogo.js",
  "src/db/db.js",
  "src/estado.js",
  "src/estilos.css",
  "src/pantallas/acceso.js",
  "src/pantallas/calculadora.js",
  "src/pantallas/finanzas.js",
  "src/pantallas/fincas.js",
  "src/pantallas/panel.js",
  "src/sync.js",
  "src/ui.js",
];

self.addEventListener("install", (e) => {
  e.waitUntil(caches.open(VERSION).then((c) => c.addAll(ARCHIVOS)).then(() => self.skipWaiting()));
});

self.addEventListener("activate", (e) => {
  e.waitUntil(caches.keys().then((claves) => Promise.all(claves.filter((k) => k !== VERSION).map((k) => caches.delete(k)))).then(() => self.clients.claim()));
});

self.addEventListener("fetch", (e) => {
  const req = e.request;
  const url = new URL(req.url);
  if (req.method !== "GET" || url.origin !== location.origin) return;
  if (url.pathname.startsWith("/api/")) return; // siempre a la red
  e.respondWith((async () => {
    const cache = await caches.open(VERSION);
    const guardado = await cache.match(req, { ignoreSearch: true });
    const red = fetch(req).then((r) => { if (r.ok) cache.put(req, r.clone()); return r; }).catch(() => null);
    if (guardado) { e.waitUntil(red); return guardado; }          // primero lo guardado; se actualiza en segundo plano
    const r = await red;
    if (r) return r;
    if (req.mode === "navigate") return (await cache.match("index.html")) || (await cache.match("./"));
    return new Response("Sin conexión", { status: 503, statusText: "Sin conexión" });
  })());
});
