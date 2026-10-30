// Dirección base de los servicios REST (Autenticación, Finca, Ciclo, Catálogo, Sincronización). La PWA solo los consume con fetch():
// no contiene lógica de servidor. Por defecto usa el mismo dominio desde el que se sirve (Render y local). Para alojar los
// servicios aparte, ponga en index.html  <meta name="api-base" content="https://servicios.ejemplo.co/api/v1">
// (y en el servidor CORS_ORIGENES con el dominio de la PWA).
const aviso = typeof document !== "undefined" ? document.querySelector('meta[name="api-base"]')?.content : "";
export const API_BASE = (aviso || "/api/v1").replace(/\/+$/, "");
export const CORREO_CONTACTO = "mikaelramos@unicomfacauca.edu.co";
