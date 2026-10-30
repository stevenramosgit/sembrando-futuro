"""Cuentas: registro, activación con código, reenvío, cambio de correo, ingreso y salida (A-01 a A-06)."""
import hmac
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core import seguridad
from app.core.errores import ErrorApi, ErroresDeCampos, texto
from app.core.seguridad import ahora
from app.domain import acceso, validaciones as v
from app.domain.fechas import COLOMBIA, a_iso
from app.models.usuario import IntentoIngreso, Otp, Token, Usuario
from app.services import correo_service, limpieza_service

ESPERA_REENVIO = 60
MAX_REENVIOS = 3
HORAS_CUENTA = 24


def normalizar_correo(correo) -> str:
    """Correo sin espacios a los lados y en minúsculas (así se guarda y se compara)."""
    return correo.strip().lower() if isinstance(correo, str) else ""


def _nuevo_id() -> str:
    """Identificador UUID nuevo."""
    return str(uuid.uuid4())


def _vencida(usuario: Usuario) -> bool:
    """Una cuenta pendiente vence si pasaron más de 24 horas sin verificar el código."""
    return usuario.estado == "PENDIENTE" and ahora() - usuario.creado_en > timedelta(hours=HORAS_CUENTA)


def _error_campo(codigo: str, **valores) -> tuple[str, str]:
    """Par (código, mensaje) para un error de campo."""
    return codigo, texto(codigo, **valores)


def _crear_token(db: Session, usuario_id: str, tipo: str) -> tuple[str, datetime]:
    """Crea un token (sesión o activación), guarda solo su huella y devuelve el token en claro y su vencimiento."""
    token = seguridad.generar_token()
    expira = seguridad.expira_token(tipo)
    db.add(Token(id_token=_nuevo_id(), id_usuario=usuario_id, token_hash=seguridad.hash_token(token), tipo=tipo,
                 creado_en=ahora(), expira_en=expira, revocado=False))
    return token, expira


def _crear_otp(db: Session, usuario: Usuario, reenvios: int) -> tuple[Otp, str]:
    """Crea un código de 6 dígitos que vence en 15 minutos, guarda su huella y devuelve la fila y el código para enviarlo."""
    codigo = seguridad.generar_codigo_otp()
    momento = ahora()
    otp = Otp(id_otp=_nuevo_id(), id_usuario=usuario.id_usuario, codigo_hash=seguridad.hash_otp(codigo), enviado_en=momento,
              expira_en=momento + timedelta(minutes=acceso.MINUTOS_VIGENCIA_OTP), intentos_fallidos=0, reenvios=reenvios,
              usado=False)
    db.add(otp)
    return otp, codigo


def _otp_vigente(db: Session, usuario_id: str) -> Otp | None:
    """El último código sin usar de la cuenta (o None)."""
    return db.scalar(select(Otp).where(Otp.id_usuario == usuario_id, Otp.usado.is_(False))
                     .order_by(Otp.enviado_en.desc()).limit(1))


def _liberar_si_vencido(db: Session, correo: str) -> Usuario | None:
    """Devuelve el usuario con ese correo; si es una cuenta pendiente vencida la elimina (libera el correo) y devuelve None."""
    usuario = db.scalar(select(Usuario).where(Usuario.correo == correo))
    if usuario is not None and _vencida(usuario):
        db.delete(usuario)
        db.flush()
        return None
    return usuario


def _comprobar_correo_libre(db: Session, correo: str) -> None:
    """Si el correo ya tiene una cuenta responde 409: activa (V-05) o pendiente de verificar (V-06).
    Una cuenta pendiente vencida se borra antes, para liberar el correo.
    """
    usuario = _liberar_si_vencido(db, correo)
    if usuario is not None:
        raise ErrorApi(409, "V-05" if usuario.estado == "ACTIVA" else "V-06")


# ---------------------------------------------------------------------------- A-01
def registrar(db: Session, d) -> dict:
    """A-01: valida todos los campos (y junta sus errores), exige la autorización de datos, guarda la cuenta PENDIENTE
    con la clave en Argon2, envía el código por Brevo y devuelve el token de activación. Si el correo falla, no se guarda nada.
    """
    limpieza_service.limpiar_liviano(db)
    nombre = d.nombre.strip() if isinstance(d.nombre, str) else d.nombre
    ubicacion = d.ubicacion.strip() if isinstance(d.ubicacion, str) else d.ubicacion
    correo = normalizar_correo(d.correo)
    errores: dict[str, tuple[str, str]] = {}
    for campo, codigo in (("nombre", v.v_nombre(nombre)), ("ubicacion", v.v_ubicacion(ubicacion)),
                          ("correo", v.v_correo(d.correo))):
        if codigo:
            errores[campo] = _error_campo(codigo)
    if "correo" not in errores and normalizar_correo(d.correo_confirmacion) != correo:
        errores["correo_confirmacion"] = _error_campo("V-04")
    if v.v_clave(d.clave, correo, nombre if isinstance(nombre, str) else ""):
        errores["clave"] = _error_campo("V-07")
    if d.autoriza_datos is not True:
        errores["autoriza_datos"] = _error_campo("V-08")
    if errores:
        raise ErroresDeCampos(errores)

    _comprobar_correo_libre(db, correo)
    momento = ahora()
    usuario = Usuario(id_usuario=_nuevo_id(), nombre=nombre, ubicacion=ubicacion, correo=correo,
                      hash_clave=seguridad.hashear_clave(d.clave), rol="AGRICULTOR", estado="PENDIENTE",
                      intentos_fallidos=0, consentimiento_ley1581=True, creado_en=momento)
    db.add(usuario)
    db.flush()
    otp, codigo = _crear_otp(db, usuario, 0)
    token, _ = _crear_token(db, usuario.id_usuario, "ACTIVACION")
    try:
        correo_service.enviar_codigo(correo, nombre, codigo)
    except ErrorApi:
        db.rollback()
        raise
    db.commit()
    return {"estado": "PENDIENTE", "correo": correo, "otp_expira_en": a_iso(otp.expira_en),
            "reenvios_restantes": MAX_REENVIOS, "espera_segundos": ESPERA_REENVIO, "token_activacion": token}


# ---------------------------------------------------------------------------- A-02
def _verificar_hash(hash_guardado: str, codigo: str) -> bool:
    """Compara la huella del código escrito con la guardada, en tiempo constante."""
    return hmac.compare_digest(hash_guardado, seguridad.hash_otp(codigo))


def verificar_otp(db: Session, usuario: Usuario, codigo) -> dict:
    """A-02: aplica la regla de verificación (vigencia de 15 minutos, 5 intentos) y, si el código es correcto, activa la cuenta."""
    otp = _otp_vigente(db, usuario.id_usuario)
    if otp is None:
        # El código fue anulado por un reenvío fallido o ya se usó: se pide uno nuevo.
        if not (isinstance(codigo, str) and v.v_codigo_otp(codigo) is None):
            raise ErrorApi(400, "V-09")
        raise ErrorApi(400, "V-11")
    momento = ahora()
    estado = {"codigo": otp.codigo_hash, "intentos": otp.intentos_fallidos,
              "min_envio": (momento - otp.enviado_en).total_seconds() / 60,
              "h_cuenta": (momento - usuario.creado_en).total_seconds() / 3600}
    resultado = acceso.verificar_codigo(codigo, estado, _verificar_hash)
    if resultado[0] == "ok":
        otp.usado = True
        usuario.estado = "ACTIVA"
        for t in db.scalars(select(Token).where(Token.id_usuario == usuario.id_usuario, Token.tipo == "ACTIVACION")):
            t.revocado = True
        db.commit()
        return {"estado": "ACTIVA"}
    otp.intentos_fallidos = estado["intentos"]
    db.commit()
    codigo_error = resultado[1]
    if codigo_error == "V-10":
        raise ErrorApi(400, "V-10", extra={"intentos_restantes": resultado[2]}, n=resultado[2])
    if codigo_error == "V-12":
        raise ErrorApi(423, "V-12")
    if codigo_error == "V-15":
        db.delete(usuario)
        db.commit()
        raise ErrorApi(410, "V-15")
    raise ErrorApi(400, codigo_error)


# ---------------------------------------------------------------------------- A-03 y A-04
def _comprobar_reenvio(otp: Otp | None) -> int:
    """Devuelve cuántos reenvíos lleva la cuenta; lanza V-14 o V-13 si no se puede enviar otro código ahora."""
    usados = otp.reenvios if otp is not None else 0
    if usados >= MAX_REENVIOS:
        raise ErrorApi(429, "V-14")
    if otp is not None:
        pasaron = (ahora() - otp.enviado_en).total_seconds()
        if pasaron < ESPERA_REENVIO:
            falta = int(ESPERA_REENVIO - pasaron) + 1
            raise ErrorApi(429, "V-13", extra={"espera_segundos": falta}, cabeceras={"Retry-After": str(falta)}, n=falta)
    return usados


def _ultimo_otp(db: Session, usuario_id: str) -> Otp | None:
    """El último código enviado a la cuenta, usado o no (para contar los reenvíos)."""
    return db.scalar(select(Otp).where(Otp.id_usuario == usuario_id).order_by(Otp.enviado_en.desc()).limit(1))


def _emitir_nuevo_codigo(db: Session, usuario: Usuario, usados: int) -> dict:
    """Anula los códigos anteriores, crea uno nuevo y lo envía; si Brevo falla se deshace todo y responde 503 (V-45)."""
    for anterior in db.scalars(select(Otp).where(Otp.id_usuario == usuario.id_usuario, Otp.usado.is_(False))):
        anterior.usado = True
    otp, codigo = _crear_otp(db, usuario, usados + 1)
    try:
        correo_service.enviar_codigo(usuario.correo, usuario.nombre, codigo)
    except ErrorApi:
        db.rollback()
        raise
    db.commit()
    return {"reenvios_restantes": MAX_REENVIOS - (usados + 1), "espera_segundos": ESPERA_REENVIO,
            "otp_expira_en": a_iso(otp.expira_en)}


def reenviar_otp(db: Session, usuario: Usuario) -> dict:
    """A-03: comprueba la espera de 60 segundos y el máximo de 3 reenvíos, y envía un código nuevo."""
    usados = _comprobar_reenvio(_ultimo_otp(db, usuario.id_usuario))
    return _emitir_nuevo_codigo(db, usuario, usados)


def cambiar_correo(db: Session, usuario: Usuario, d) -> dict:
    """A-04: valida el correo nuevo y su confirmación, comprueba que esté libre, lo cambia y envía allí un código nuevo."""
    nuevo = normalizar_correo(d.correo_nuevo)
    if v.v_correo(d.correo_nuevo):
        raise ErroresDeCampos({"correo_nuevo": _error_campo("V-03")})
    if normalizar_correo(d.correo_nuevo_confirmacion) != nuevo:
        raise ErroresDeCampos({"correo_nuevo_confirmacion": _error_campo("V-04")})
    if nuevo != usuario.correo:
        _comprobar_correo_libre(db, nuevo)
    else:
        raise ErrorApi(409, "V-06")
    usados = _comprobar_reenvio(_ultimo_otp(db, usuario.id_usuario))
    usuario.correo = nuevo
    respuesta = _emitir_nuevo_codigo(db, usuario, usados)
    respuesta["correo"] = nuevo
    return respuesta


# ---------------------------------------------------------------------------- A-05 y A-06
def _hora_local(momento: datetime) -> str:
    """Hora de Colombia en formato HH:MM, para decir hasta qué hora dura el bloqueo."""
    return momento.replace(tzinfo=timezone.utc).astimezone(COLOMBIA).strftime("%H:%M")


def _verificar_clave_guardada(hash_guardado, clave) -> bool:
    """Adaptador entre la regla de acceso (dominio) y la verificación Argon2."""
    return seguridad.verificar_clave(clave, hash_guardado)


def _datos_de_cuenta(usuario, intento) -> dict:
    """Datos que necesita la regla de acceso: de la cuenta real o, si no existe, del contador de intentos del correo."""
    if usuario is None:
        return {"clave": None, "estado": "ACTIVA", "fallos": intento.intentos_fallidos if intento else 0,
                "bloqueado_hasta": intento.bloqueado_hasta if intento else None}
    return {"clave": usuario.hash_clave, "estado": usuario.estado, "fallos": usuario.intentos_fallidos,
            "bloqueado_hasta": usuario.bloqueado_hasta}


def _guardar_intentos(db: Session, usuario, intento, correo: str, cuenta: dict, momento) -> None:
    """Guarda el contador de fallos y el bloqueo, en la cuenta o, si no existe, en el registro del correo."""
    if usuario is not None:
        usuario.intentos_fallidos = cuenta["fallos"]
        usuario.bloqueado_hasta = cuenta["bloqueado_hasta"]
    elif cuenta["fallos"] or cuenta["bloqueado_hasta"] is not None:
        if intento is None:
            intento = IntentoIngreso(correo=correo)
            db.add(intento)
        intento.intentos_fallidos = cuenta["fallos"]
        intento.bloqueado_hasta = cuenta["bloqueado_hasta"]
        intento.actualizado_en = momento
    db.commit()


def _rechazar_acceso(db: Session, codigo: str, usuario, cuenta: dict) -> None:
    """Responde el error de ingreso que decidió la regla: bloqueo hasta HH:MM (423, V-18), cuenta sin verificar (V-19,
    que se borra si ya venció) o correo o clave incorrectos (401, V-17), sin decir cuál de los dos falló.
    """
    if codigo == "V-18":
        hasta = cuenta["bloqueado_hasta"]
        raise ErrorApi(423, "V-18", extra={"bloqueado_hasta": a_iso(hasta)}, hora=_hora_local(hasta))
    if codigo == "V-19":
        if _vencida(usuario):
            db.delete(usuario)
            db.commit()
            raise ErrorApi(410, "V-15")
        token, _ = _crear_token(db, usuario.id_usuario, "ACTIVACION")
        db.commit()
        raise ErrorApi(403, "V-19", extra={"accion": "VERIFICAR_OTP", "token_activacion": token})
    if codigo == "V-17":
        raise ErrorApi(401, "V-17")
    raise ErrorApi(400, codigo)


def iniciar_sesion(db: Session, d) -> dict:
    """A-05: aplica la regla de acceso (5 fallos bloquean 15 minutos), guarda los intentos y, si todo está bien,
    crea el token de sesión de 30 días.
    """
    limpieza_service.limpiar_liviano(db)
    correo = normalizar_correo(d.correo)
    clave = d.clave
    if not correo or not isinstance(clave, str) or clave == "":
        raise ErrorApi(400, "V-16")
    usuario = db.scalar(select(Usuario).where(Usuario.correo == correo))
    intento = None if usuario else db.get(IntentoIngreso, correo)
    cuenta = _datos_de_cuenta(usuario, intento)
    momento = ahora()
    resultado = acceso.iniciar_sesion(correo, clave, cuenta, momento, timedelta(minutes=15), _verificar_clave_guardada)
    _guardar_intentos(db, usuario, intento, correo, cuenta, momento)

    if resultado[0] == "ok":
        token, expira = _crear_token(db, usuario.id_usuario, "SESION")
        db.commit()
        return {"token": token, "expira_en": a_iso(expira),
                "usuario": {"id": usuario.id_usuario, "nombre": usuario.nombre, "ubicacion": usuario.ubicacion,
                            "correo": usuario.correo, "rol": usuario.rol}}
    _rechazar_acceso(db, resultado[1], usuario, cuenta)


def cerrar_sesion(db: Session, token: Token) -> None:
    """A-06: revoca el token de la sesión actual."""
    token.revocado = True
    db.commit()
