// Acceso: bienvenida, registro, verificación del código, cambio de correo, ingreso y política de datos (P-01, P-02, P-04, P-06, P-07, P-27).
import { llamar, ErrorRed, error } from "../api.js";
import { CORREO_CONTACTO } from "../config.js";
import { esc, pad } from "../calculos/formato.js";
import { E, vClave, vCodigoOtp, vCorreo, vNombre, vUbicacion } from "../calculos/validaciones.js";
import { S, cargarCatalogo, cargarDatos, guardarSesion, leerSesion, misFincas } from "../estado.js";
import { INTENTOS_SIN_CONEXION, claveCoincide, crearVerificador } from "../sesion.js";
import { pedirSync } from "../sync.js";
import { ico } from "../iconos.js";
import { A, MSG_SIN_RED, P, badB, btn, chk, ejecutar, err1, fail, fld, go, okB, raiz, topBanner, val, warnB } from "../ui.js";

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
/** P-01 Bienvenida: qué hace la aplicación y los botones Crear cuenta e Ingresar. */
/** Tarjeta de ejemplo de la portada: un ciclo de café con los mismos valores del ejemplo de referencia del plan de pruebas. */
const EJEMPLO = `<div class="ejemplo" aria-label="Ejemplo de resumen de un ciclo"><div class="ejemplo-cab"><b>Café · Lote de arriba</b><span>Ejemplo</span></div>`
  + `<div class="ejemplo-kpis"><div><span>Área efectiva</span><b>0,90 ha</b></div><div><span>Matas en el ciclo</span><b>4.000</b></div><div><span>Gastos</span><b>$ 150.000</b></div><div><span>Ingresos</span><b>$ 500.000</b></div></div>`
  + `<div class="ejemplo-utilidad"><span>Utilidad neta · rentabilidad 233,3 %</span><b>$ 350.000</b></div>`
  + `<div class="ejemplo-grafica"><div class="ejemplo-leyenda"><span>Gastos e ingresos por mes</span><span><i class="g"></i>Gastos <i class="i"></i>Ingresos</span></div>`
  + `<div class="ejemplo-barras">${[["Jun", 30, 0], ["Jul", 55, 0], ["Ago", 22, 14], ["Sep", 38, 62], ["Oct", 18, 100]].map(([m, g, i]) => `<div><span class="g" style="height:${g}%"></span><span class="i" style="height:${i}%"></span><em>${m}</em></div>`).join("")}</div></div></div>`;

/** Lo que permite hacer la aplicación (portada). */
const FUNCIONES = [
  ["brote", "Matas por hectárea", "Marco cuadrado, rectangular o tresbolillo, con aviso si la distancia no es la recomendada."],
  ["mapa", "Fincas y ciclos", "Registre sus fincas y ciclos y descuente caminos, agua o construcciones en m², hectáreas o plazas."],
  ["grafica", "Gastos, jornales y ventas", "Utilidad, rentabilidad y utilidad por hectárea calculadas al instante."],
  ["wifi", "Sin internet", "Lo que anote se guarda en el teléfono y se envía solo cuando vuelve la señal."],
];
/** Pasos para empezar (portada). */
const PASOS = [
  ["Registre su finca", "Cree su cuenta y agregue su finca en un minuto."],
  ["Inicie un ciclo", "Escriba el área, la fecha de siembra y elija el cultivo: la aplicación le dice cuántas matas necesita."],
  ["Anote y compare", "Registre cada gasto, jornal y venta. Al cerrar el ciclo verá su balance final."],
];

// P-01 Bienvenida: presentación con el logo, ejemplo de resumen, funciones, pasos y botones para ingresar o crear la cuenta.
P.p01 = () => ({ t: "Sembrando Futuro", back: 0, sinTituloPc: true, h: `<section class="heroe"><div class="heroe-texto"><img class="logo-heroe" src="img/logo.webp" alt="Sembrando Futuro: iniciativa para el desarrollo agropecuario" width="200" height="218"><p class="eyebrow">Gestión agrícola para fincas del Cauca</p><h2 class="heroe-titulo">Cultive con cuentas claras</h2><p class="heroe-sub">Calcule cuántas matas siembra por hectárea, anote gastos, jornales y ventas, y sepa cuánto gana en cada cosecha. Funciona sin internet.</p>${topBanner()}<div class="heroe-botones"><button class="btn btn-primario" data-act="go:p02">Crear cuenta gratis ${ico("flecha", 18)}</button><button class="btn btn-contorno" data-act="go:p07">Ingresar</button></div><p class="heroe-nota">Funciona en el computador y en el celular, también sin internet.</p></div>${EJEMPLO}</section>`
  + `<section class="seccion"><p class="eyebrow">Qué puede hacer</p><h2>Todo lo de la finca, en un solo lugar</h2><p>Pensado para productores: palabras del campo, letras grandes y cálculos hechos por usted.</p><div class="funciones">${FUNCIONES.map(([i, t, d]) => `<div class="funcion"><span class="chip-ico chip-verde">${ico(i, 20)}</span><h3>${t}</h3><p>${d}</p></div>`).join("")}</div></section>`
  + `<section class="seccion"><p class="eyebrow">Cómo funciona</p><h2>Tres pasos para empezar</h2><ol class="pasos">${PASOS.map(([t, d]) => `<li><h3>${t}</h3><p>${d}</p></li>`).join("")}</ol></section>`
  + `<section class="cta"><div><h2>Empiece hoy con su primera finca</h2><p>Es gratis y toma menos de dos minutos.</p></div><div class="cta-botones"><button class="btn" data-act="cta:p02">Crear cuenta</button><button class="btn btn-borde-claro" data-act="cta:p16">Ver catálogo</button></div></section>`
  + `<button class="linkbtn" data-act="go:p27">Política de datos y ayuda</button>` });
A.cta = (s) => go(s);

/** P-02 Crear cuenta: nombre, ubicación, correo con confirmación, clave y autorización de datos (Ley 1581). */
P.p02 = () => ({ t: "Crear cuenta", h: `<div class="acceso-cabeza"><img src="img/emblema.png" alt="" width="96" height="96"><h2>Cree su cuenta</h2><p>Es gratis. Le enviaremos un código a su correo para activarla.</p></div>${topBanner()}${fld("nombre", "Nombre completo", { ac: "name", max: 80 })}${fld("ubic", "Ubicación (municipio o vereda)", { max: 80 })}${fld("correo", "Correo", { type: "email", ac: "email" })}${fld("correo2", "Confirmar correo", { type: "email" })}${fld("clave", "Clave", { type: "password", ac: "new-password", hint: "De 10 a 64 caracteres con mayúscula, minúscula, número y símbolo (!@#$%^&*()_+-=[]{}|;:,.<>?). Sin espacios ni tildes." })}${chk("auth", 'Autorizo el tratamiento de mis datos personales (Ley 1581 de 2012). <a href="#" data-act="go:p27" style="color:var(--primary)">Ver política</a>')}${err1("auth")}<div style="height:12px"></div>${btn("reg", "Crear cuenta")}` });

/** Segundos que faltan para poder pedir otro código (60 entre reenvíos). */
const espera = () => Math.max(0, Math.ceil(((S.ctx.otp?.esperaHasta || 0) - Date.now()) / 1000));
/** P-04 Verificar código: los 6 dígitos que llegaron al correo, con reenvío y cambio de correo. */
P.p04 = () => {
  const w = espera();
  const left = S.ctx.otp?.restantes ?? 3;
  return { t: "Verifique su correo", back: 0, h: `<h2>Escriba el código</h2><p>Enviamos un código de 6 dígitos a <b>${esc(S.ctx.email || "")}</b>. El código vence en 15 minutos.</p>${topBanner()}${fld("otp", "Código de 6 dígitos", { im: "numeric", max: 8, ac: "one-time-code" })}${btn("otpv", "Activar cuenta")}<p class="muted" id="wait">Reenvíos disponibles: ${left}.${w ? ` Puede pedir otro código en ${Math.floor(w / 60)}:${pad(w % 60)}.` : ""}</p>${btn("otpr", "Reenviar código", "sec")}<button class="linkbtn" data-act="go:p06">Cambiar correo</button>` };
};
/** Texto con los reenvíos disponibles y el tiempo de espera; se actualiza cada segundo. */
export const textoEspera = () => { const w = espera(); const left = S.ctx.otp?.restantes ?? 3; return `Reenvíos disponibles: ${left}.${w ? ` Puede pedir otro código en ${Math.floor(w / 60)}:${pad(w % 60)}.` : ""}`; };

/** P-06 Cambiar correo de una cuenta que aún no se activa (cuenta como un reenvío). */
P.p06 = () => ({ t: "Cambiar correo", h: `<p>La cuenta aún no está activa. Escriba el correo correcto y le enviaremos un código nuevo. Cuenta como un reenvío.</p>${topBanner()}${fld("nmail", "Correo nuevo", { type: "email" })}${fld("nmail2", "Confirmar correo nuevo", { type: "email" })}${btn("chm", "Enviar código nuevo")}${btn("back", "Cancelar", "sec")}` });

/** P-07 Ingresar con correo y clave. */
P.p07 = () => ({ t: "Ingresar", back: 0, h: `<div class="acceso-cabeza"><img src="img/emblema.png" alt="" width="96" height="96"><h2>Bienvenido de nuevo</h2><p>Ingrese con su correo y su clave.</p></div>${topBanner()}${fld("lmail", "Correo", { type: "email", ac: "email" })}${fld("lpass", "Clave", { type: "password", ac: "current-password" })}${btn("login", "Ingresar")}<button class="linkbtn" data-act="go:p02">Crear cuenta</button>` });

/** P-27 Política de tratamiento de datos personales (Ley 1581 de 2012): responsables, finalidad, derechos y contacto. */
P.p27 = () => ({ t: "Política de datos", h: `<div class="legal"><b>Responsables.</b> Mikael Steven Ramos Musse y Kevin Zambrano, estudiantes de Ingeniería de Sistemas de Unicomfacauca.

<b>Datos que se recolectan.</b> Nombre, correo, ubicación, clave (solo como hash con sal) y los datos que usted registra: fincas, ciclos (con sus cultivos), gastos, jornales e ingresos.

<b>Para qué se usan.</b> Crear y proteger su cuenta, enviar el código de verificación, calcular matas por hectárea y utilidad, y sincronizar sus datos. No se usan para publicidad ni se comparten con terceros.

<b>Sus derechos.</b> Conocer, actualizar y rectificar sus datos, pedir prueba de la autorización, presentar quejas ante la Superintendencia de Industria y Comercio, revocar la autorización y pedir la eliminación de sus datos.

<b>Cómo ejercerlos.</b> Escribiendo al correo ${esc(CORREO_CONTACTO)}. Las consultas se responden en máximo 10 días hábiles y los reclamos en máximo 15 días hábiles.

<b>Conservación.</b> Mientras la cuenta esté activa. Una cuenta que no se activa en 24 horas se elimina sola.</div>` });

// ---------------------------------------------------------------- sesión
/** Abre la sesión con la respuesta de A-05. Devuelve false si la cuenta es de administración.
 *  Guarda la hora de ingreso (para el máximo de 12 horas), la de la última actividad (para los 30 minutos sin uso) y el
 *  verificador de la clave, que permite volver a entrar sin conexión. */
export async function abrirSesion(d, clave) {
  if (d.usuario.rol === "ADMIN") {
    S.banner = { k: "warn", m: "Esta cuenta es de administración y no tiene pantallas en la aplicación. Use los comandos de administración del servidor." };
    return false;
  }
  const ahora = Date.now();
  S.usuario = { ...d.usuario, token: d.token, expira_en: d.expira_en, inactividad_min: d.inactividad_min || 30, autenticado_en: ahora, ultima_actividad: ahora };
  await guardarSesion({ ...S.usuario, verificador: clave ? await crearVerificador(clave) : null, fallos_locales: 0 });
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

/** Valida en el teléfono los campos del registro con las mismas reglas del servidor. */
function validarRegistro(nombre, ubic, mail, m2, clave) {
  const reglas = [["nombre", vNombre(nombre)], ["ubic", vUbicacion(ubic)], ["correo", vCorreo(mail)], ["clave", vClave(clave, mail, nombre)]];
  for (const [campo, e] of reglas) if (e) S.e[campo] = e;
  if (correosDistintos(mail, m2)) S.e.correo2 = E("V-04");
  if (!S.f.auth) S.e.auth = E("V-08");
}

/** Crear cuenta (A-01): valida, envía al servidor y pasa a verificar el código. */
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

/** El token de activación ya no sirve: se vuelve a la bienvenida con el aviso correspondiente. */
function sesionDeActivacionVencida() {
  S.pantalla = "p07"; S.pila = []; S.f = {};
  warnB("V-46");
}
/** Pasaron 24 horas sin verificar (V-15): la cuenta se borró y hay que registrarse de nuevo. */
const cuentaVencida = () => { S.pantalla = "p02"; S.pila = []; S.f = {}; badB("V-15"); };

/** Verificar el código (A-02); si es correcto la cuenta queda activa y se ingresa. */
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
      if (i && i.estado === 200 && (await abrirSesion(i.datos, clave))) { okB("Cuenta activada. Bienvenido, " + S.usuario.nombre.split(" ")[0] + "."); return; }
    }
    S.pantalla = "p07"; S.pila = []; S.f = { lmail: correo };
    okB("Cuenta activada. Ingrese con su correo y su clave.");
    return;
  }
  if (r.estado === 410) return cuentaVencida();
  if (r.estado === 401) return sesionDeActivacionVencida();
  mostrarError(r, "otp");
});

/** Pedir otro código (A-03), respetando la espera y el máximo de reenvíos. */
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

/** Interpreta la respuesta de A-04: correo cambiado, errores de campo o correo ya registrado. */
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

/** Cambiar el correo de la cuenta pendiente (A-04). */
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

/** Ingreso sin conexión (RF-03): solo para la última cuenta que ingresó en este teléfono. La clave se compara con el
 *  verificador guardado; tras 5 claves incorrectas seguidas hay que conectarse a internet (V-53). Los registros nuevos
 *  quedan pendientes y, si el token del servidor ya venció, al volver la señal se pide la clave otra vez (V-46). */
async function ingresarSinConexion(correo, clave) {
  const s = await leerSesion();
  if (!s || s.correo !== correo || !s.verificador) { S.banner = { k: "warn", m: MSG_SIN_RED }; return; }
  if ((s.fallos_locales || 0) >= INTENTOS_SIN_CONEXION) return badB("V-53");
  if (!(await claveCoincide(clave, s.verificador))) {
    await guardarSesion({ ...s, fallos_locales: (s.fallos_locales || 0) + 1 });
    return badB("V-17");
  }
  const { k, verificador, fallos_locales, bloqueada, motivo, ...usuario } = s;
  const ahora = Date.now();
  S.usuario = { ...usuario, autenticado_en: ahora, ultima_actividad: ahora };
  await guardarSesion({ ...S.usuario, verificador, fallos_locales: 0 });
  await cargarDatos(S.usuario.id);
  await cargarCatalogo();
  S.sel = { finca: null, ciclo: null };
  raiz(misFincas().length ? "p10" : "p09");
  warnB("V-44");
}

/** Ingresar (A-05): valida, inicia sesión y abre el panel; el administrador no usa la aplicación de agricultores. */
A.login = (el) => ejecutar(el, async () => {
  const m = val("lmail").trim().toLowerCase(), p = val("lpass");
  if (!m || !p) return badB("V-16");
  let r;
  try { r = await llamar("POST", "/auth/ingreso", { cuerpo: { correo: m, clave: p } }); } catch (x) {
    if (x instanceof ErrorRed) return ingresarSinConexion(m, p);
    throw x;
  }
  if (r.estado === 200) { await abrirSesion(r.datos, p); return; }
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
