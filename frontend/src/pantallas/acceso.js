// Acceso: bienvenida, registro, verificación del código, cambio de correo, ingreso y política de datos (P-01, P-02, P-04, P-06, P-07, P-27).
import { llamar, ErrorRed, error } from "../api.js";
import { CORREO_CONTACTO } from "../config.js";
import { esc, pad } from "../calculos/formato.js";
import { E, vClave, vCodigoOtp, vCorreo, vNombre, vUbicacion } from "../calculos/validaciones.js";
import { S, cargarCatalogo, cargarDatos, guardarSesion, misFincas } from "../estado.js";
import { pedirSync } from "../sync.js";
import { A, MSG_SIN_RED, P, badB, banner, btn, chk, ejecutar, err1, fail, fld, go, okB, raiz, topBanner, val, warnB } from "../ui.js";

const CAMPOS = { nombre: "nombre", ubicacion: "ubic", correo: "correo", correo_confirmacion: "correo2", clave: "clave", autoriza_datos: "auth",
  correo_nuevo: "nmail", correo_nuevo_confirmacion: "nmail2", codigo: "otp" };

/** Llama a la API; si no hay conexión muestra el aviso y devuelve null. */
async function enviar(metodo, ruta, opciones) {
  try { return await llamar(metodo, ruta, opciones); } catch (e) {
    if (e instanceof ErrorRed) { S.banner = { k: "warn", m: MSG_SIN_RED }; return null; }
    throw e;
  }
}
/** Muestra un error de la API: por campo si trae `campos`, o como aviso. */
function mostrarError(r, campoUnico) {
  const e = error(r);
  if (!e || r.estado >= 500) return badB("V-45");
  if (e.campos) { for (const [k, v] of Object.entries(e.campos)) S.e[CAMPOS[k] || k] = { c: v.codigo, m: v.mensaje }; return; }
  if (campoUnico) { S.e[campoUnico] = { c: e.codigo, m: e.mensaje }; return; }
  S.banner = { k: "bad", m: e.mensaje, c: e.codigo };
}

// ---------------------------------------------------------------- pantallas
P.p01 = () => ({ t: "Sembrando Futuro", back: 0, h: `<div style="padding-top:28px"><h2>Cultive con cuentas claras</h2><p>Calcule cuántas matas siembra por hectárea y sepa cuánto gana en cada cosecha. Funciona sin internet.</p></div>${topBanner()}${btn("go:p07", "Ingresar")}${btn("go:p02", "Crear cuenta", "sec")}<button class="linkbtn" data-act="go:p27">Política de datos y ayuda</button>` });

P.p02 = () => ({ t: "Crear cuenta", h: `${topBanner()}${fld("nombre", "Nombre completo", { ac: "name", max: 80 })}${fld("ubic", "Ubicación (municipio o vereda)", { max: 80 })}${fld("correo", "Correo", { type: "email", ac: "email" })}${fld("correo2", "Confirmar correo", { type: "email" })}${fld("clave", "Clave", { type: "password", ac: "new-password", hint: "De 10 a 64 caracteres con mayúscula, minúscula, número y símbolo (!@#$%^&*()_+-=[]{}|;:,.<>?). Sin espacios ni tildes." })}${chk("auth", 'Autorizo el tratamiento de mis datos personales (Ley 1581 de 2012). <a href="#" data-act="go:p27" style="color:var(--primary)">Ver política</a>')}${err1("auth")}<div style="height:12px"></div>${btn("reg", "Crear cuenta")}` });

const espera = () => Math.max(0, Math.ceil(((S.ctx.otp?.esperaHasta || 0) - Date.now()) / 1000));
P.p04 = () => {
  const w = espera();
  const left = S.ctx.otp?.restantes ?? 3;
  return { t: "Verifique su correo", back: 0, h: `<h2>Escriba el código</h2><p>Enviamos un código de 6 dígitos a <b>${esc(S.ctx.email || "")}</b>. Vale 15 minutos.</p>${topBanner()}${fld("otp", "Código de 6 dígitos", { im: "numeric", max: 8, ac: "one-time-code" })}${btn("otpv", "Activar cuenta")}<p class="muted" id="wait">Reenvíos disponibles: ${left}.${w ? ` Puede pedir otro código en ${Math.floor(w / 60)}:${pad(w % 60)}.` : ""}</p>${btn("otpr", "Reenviar código", "sec")}<button class="linkbtn" data-act="go:p06">Cambiar correo</button>` };
};
export const textoEspera = () => { const w = espera(); const left = S.ctx.otp?.restantes ?? 3; return `Reenvíos disponibles: ${left}.${w ? ` Puede pedir otro código en ${Math.floor(w / 60)}:${pad(w % 60)}.` : ""}`; };

P.p06 = () => ({ t: "Cambiar correo", h: `<p>La cuenta aún no está activa. Escriba el correo correcto y le enviaremos un código nuevo. Cuenta como un reenvío.</p>${topBanner()}${fld("nmail", "Correo nuevo", { type: "email" })}${fld("nmail2", "Confirmar correo nuevo", { type: "email" })}${btn("chm", "Enviar código nuevo")}${btn("back", "Cancelar", "sec")}` });

P.p07 = () => ({ t: "Ingresar", back: 0, h: `<div style="height:8px"></div>${topBanner()}${fld("lmail", "Correo", { type: "email", ac: "email" })}${fld("lpass", "Clave", { type: "password", ac: "current-password" })}${btn("login", "Ingresar")}<button class="linkbtn" data-act="go:p02">Crear cuenta</button>` });

P.p27 = () => ({ t: "Política de datos", h: `<div class="legal"><b>Responsables.</b> Mikael Steven Ramos Musse y Kevin Zambrano, estudiantes de Ingeniería de Sistemas de Unicomfacauca.

<b>Datos que se recolectan.</b> Nombre, correo, ubicación, clave (solo como hash con sal) y los datos que usted registra: fincas, ciclos (con sus cultivos), gastos, jornales e ingresos.

<b>Para qué se usan.</b> Crear y proteger su cuenta, enviar el código de verificación, calcular matas por hectárea y utilidad, y sincronizar sus datos. No se usan para publicidad ni se comparten con terceros.

<b>Sus derechos.</b> Conocer, actualizar y rectificar sus datos, pedir prueba de la autorización, presentar quejas ante la Superintendencia de Industria y Comercio, revocar la autorización y pedir la eliminación de sus datos.

<b>Cómo ejercerlos.</b> Escribiendo al correo ${esc(CORREO_CONTACTO)}. Las consultas se responden en máximo 10 días hábiles y los reclamos en máximo 15 días hábiles.

<b>Conservación.</b> Mientras la cuenta esté activa. Una cuenta que no se activa en 24 horas se elimina sola.</div>` });

// ---------------------------------------------------------------- sesión
/** Abre la sesión con la respuesta de A-05. Devuelve false si la cuenta es de administración. */
export async function abrirSesion(d) {
  if (d.usuario.rol === "ADMIN") {
    S.banner = { k: "warn", m: "Esta cuenta es de administración y no tiene pantallas en la aplicación. Use los comandos de administración del servidor." };
    return false;
  }
  S.usuario = { ...d.usuario, token: d.token, expira_en: d.expira_en };
  await guardarSesion({ ...S.usuario });
  await cargarDatos(S.usuario.id);
  await cargarCatalogo();
  S.sel = { finca: null, ciclo: null };
  S.activacion = null;
  S.claveTemporal = null;
  raiz(misFincas().length ? "p10" : "p09");
  pedirSync(100);
  return true;
}

// ---------------------------------------------------------------- acciones
const correosDistintos = (a, b) => !b || b.toLowerCase() !== a.toLowerCase();

function validarRegistro(nombre, ubic, mail, m2, clave) {
  const reglas = [["nombre", vNombre(nombre)], ["ubic", vUbicacion(ubic)], ["correo", vCorreo(mail)], ["clave", vClave(clave, mail, nombre)]];
  for (const [campo, e] of reglas) if (e) S.e[campo] = e;
  if (correosDistintos(mail, m2)) S.e.correo2 = E("V-04");
  if (!S.f.auth) S.e.auth = E("V-08");
}

A.reg = (el) => ejecutar(el, async () => {
  const nombre = val("nombre").trim(), ubic = val("ubic").trim(), mail = val("correo").trim(), m2 = val("correo2").trim(), clave = val("clave");
  validarRegistro(nombre, ubic, mail, m2, clave);
  if (Object.keys(S.e).length) return;
  const r = await enviar("POST", "/auth/registro", { cuerpo: { nombre, ubicacion: ubic, correo: mail, correo_confirmacion: m2, clave, autoriza_datos: true } });
  if (!r) return;
  if (r.estado !== 201) return mostrarError(r);
  S.activacion = r.datos.token_activacion;
  S.claveTemporal = clave;  // solo en memoria: sirve para ingresar solo después de activar
  S.ctx = { email: r.datos.correo, otp: { restantes: r.datos.reenvios_restantes, esperaHasta: Date.now() + r.datos.espera_segundos * 1000 } };
  S.f = {};
  S.pantalla = "p04";
  okB("Cuenta creada. Le enviamos el código a su correo.");
});

function sesionDeActivacionVencida() {
  S.pantalla = "p07"; S.pila = []; S.f = {};
  warnB("V-46");
}
const cuentaVencida = () => { S.pantalla = "p02"; S.pila = []; S.f = {}; badB("V-15"); };

A.otpv = (el) => ejecutar(el, async () => {
  const c = val("otp").trim();
  if (vCodigoOtp(c)) return fail("otp", "V-09");
  const r = await enviar("POST", "/auth/otp/verificar", { token: S.activacion, cuerpo: { codigo: c } });
  if (!r) return;
  if (r.estado === 200) {
    const correo = S.ctx.email, clave = S.claveTemporal;
    S.claveTemporal = null; S.activacion = null;
    if (clave) {
      const i = await enviar("POST", "/auth/ingreso", { cuerpo: { correo, clave } });
      if (i && i.estado === 200 && (await abrirSesion(i.datos))) { okB("Cuenta activada. Bienvenido, " + S.usuario.nombre.split(" ")[0] + "."); return; }
    }
    S.pantalla = "p07"; S.pila = []; S.f = { lmail: correo };
    okB("Cuenta activada. Ingrese con su correo y su clave.");
    return;
  }
  if (r.estado === 410) return cuentaVencida();
  if (r.estado === 401) return sesionDeActivacionVencida();
  mostrarError(r, "otp");
});

A.otpr = (el) => ejecutar(el, async () => {
  const r = await enviar("POST", "/auth/otp/reenviar", { token: S.activacion });
  if (!r) return;
  if (r.estado === 200) {
    S.ctx.otp = { restantes: r.datos.reenvios_restantes, esperaHasta: Date.now() + r.datos.espera_segundos * 1000 };
    S.f = {};
    return okB("Enviamos un código nuevo. El anterior ya no sirve.");
  }
  if (r.estado === 410) return cuentaVencida();
  if (r.estado === 401) return sesionDeActivacionVencida();
  const e = error(r);
  if (e?.codigo === "V-13") S.ctx.otp = { ...S.ctx.otp, esperaHasta: Date.now() + (e.espera_segundos || 60) * 1000 };
  if (e?.codigo === "V-14") S.ctx.otp = { ...S.ctx.otp, restantes: 0 };
  mostrarError(r);
});

function respuestaCambioCorreo(r) {
  if (r.estado === 200) {
    S.ctx = { email: r.datos.correo, otp: { restantes: r.datos.reenvios_restantes, esperaHasta: Date.now() + r.datos.espera_segundos * 1000 } };
    S.pila.pop(); S.pantalla = "p04"; S.f = {};
    return okB("Cambiamos el correo y enviamos un código nuevo a " + r.datos.correo + ".");
  }
  if (r.estado === 410) return cuentaVencida();
  if (r.estado === 401) return sesionDeActivacionVencida();
  const er = error(r);
  if (er?.codigo === "V-05" || er?.codigo === "V-06") { S.e.nmail = { c: er.codigo, m: er.mensaje }; return; }
  mostrarError(r);
}

A.chm = (el) => ejecutar(el, async () => {
  const m = val("nmail").trim(), m2 = val("nmail2").trim();
  const e = vCorreo(m);
  if (e) S.e.nmail = e;
  if (correosDistintos(m, m2)) S.e.nmail2 = E("V-04");
  if (Object.keys(S.e).length) return;
  const r = await enviar("POST", "/auth/correo/cambiar", { token: S.activacion, cuerpo: { correo_nuevo: m, correo_nuevo_confirmacion: m2 } });
  if (!r) return;
  respuestaCambioCorreo(r);
});

A.login = (el) => ejecutar(el, async () => {
  const m = val("lmail").trim().toLowerCase(), p = val("lpass");
  if (!m || !p) return badB("V-16");
  const r = await enviar("POST", "/auth/ingreso", { cuerpo: { correo: m, clave: p } });
  if (!r) return;
  if (r.estado === 200) { await abrirSesion(r.datos); return; }
  const e = error(r);
  if (r.estado === 403 && e?.codigo === "V-19") {
    S.activacion = e.token_activacion; S.claveTemporal = p;
    S.ctx = { email: m, otp: { restantes: 3, esperaHasta: 0 } };
    S.pantalla = "p04"; S.f = {};
    S.banner = { k: "warn", m: e.mensaje, c: "V-19" };
    return;
  }
  if (r.estado === 410) return cuentaVencida();
  mostrarError(r);
});
