"""Claves con Argon2, tokens con hash, y dependencias de FastAPI para sesión, activación y administrador."""
import hashlib
import hmac
import secrets
from datetime import datetime, timedelta, timezone

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerifyMismatchError
from fastapi import Depends, Header
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import config
from app.core.errores import ErrorApi
from app.database.connection import get_db

_hasher = PasswordHasher()
# Hash de una clave que nadie conoce: se verifica cuando la cuenta no existe para que el tiempo de respuesta sea parecido.
_HASH_FALSO = _hasher.hash(secrets.token_urlsafe(16))


def ahora() -> datetime:
    """Hora UTC sin zona (así se guarda en la base de datos)."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


def hashear_clave(clave: str) -> str:
    """Devuelve el hash Argon2 de la clave (incluye sal aleatoria); la clave nunca se guarda en claro."""
    return _hasher.hash(clave)


def verificar_clave(clave: str, hash_guardado: str | None) -> bool:
    """Compara una clave con su hash. Si la cuenta no existe se verifica contra un hash falso para que el tiempo de
    respuesta no revele si el correo está registrado.
    """
    try:
        return _hasher.verify(hash_guardado or _HASH_FALSO, clave) and hash_guardado is not None
    except (VerifyMismatchError, InvalidHashError):
        return False


def _huella(valor: str) -> str:
    """Hash con la clave interna del servidor mezclada (HMAC-SHA256): los tokens y los OTP no se guardan en claro."""
    return hmac.new(config.clave_secreta.encode(), valor.encode(), hashlib.sha256).hexdigest()


def hash_token(token: str) -> str:
    """Huella del token de sesión o de activación; en la base solo se guarda esta huella, nunca el token."""
    return _huella("token:" + token)


def hash_otp(codigo: str) -> str:
    """Huella del código de verificación de 6 dígitos; en la base solo se guarda esta huella."""
    return _huella("otp:" + codigo)


def generar_token() -> str:
    """Token opaco aleatorio con el prefijo tkn_ (no contiene datos del usuario)."""
    return "tkn_" + secrets.token_urlsafe(32)


def generar_codigo_otp() -> str:
    """Código aleatorio de 6 dígitos (100000 a 999999). Solo en el entorno de pruebas es el código fijo, para automatizarlas."""
    if config.entorno == "pruebas":
        return config.otp_fijo_pruebas
    return f"{secrets.randbelow(900000) + 100000}"


def expira_token(tipo: str) -> datetime:
    """Fecha de vencimiento: la sesión dura como máximo SESION_HORAS horas (12 por defecto) aunque se use todo el tiempo,
    y el token de activación 24 horas (OWASP ASVS 4.0.3, requisito 3.3.2, nivel 2).
    """
    return ahora() + (timedelta(hours=config.sesion_horas) if tipo == "SESION" else timedelta(hours=24))


# Para no escribir en la base en cada petición, la hora del último uso se actualiza como mucho una vez por minuto.
_REFRESCO_USO = timedelta(minutes=1)


def _sesion_inactiva(fila, momento: datetime) -> bool:
    """True si la sesión lleva más de SESION_INACTIVIDAD_MIN minutos (30 por defecto) sin ninguna petición."""
    ultimo = fila.usado_en or fila.creado_en
    return momento - ultimo > timedelta(minutes=config.sesion_inactividad_min)


# ---------------------------------------------------------------- dependencias de FastAPI
def _token_de(authorization: str | None) -> str:
    """Saca el token de la cabecera 'Authorization: Bearer ...'; si falta o está mal formada responde 401 (V-46)."""
    if not authorization or not authorization.lower().startswith("bearer "):
        raise ErrorApi(401, "V-46")
    token = authorization[7:].strip()
    if not token:
        raise ErrorApi(401, "V-46")
    return token


def _buscar_token(db: Session, authorization: str | None, tipo: str):
    """Busca el token por su huella y comprueba que sea del tipo pedido, no esté revocado ni vencido; si no, 401 (V-46)."""
    from app.models.usuario import Token

    token = _token_de(authorization)
    fila = db.scalar(select(Token).where(Token.token_hash == hash_token(token)))
    momento = ahora()
    if fila is None or fila.tipo != tipo or fila.revocado or fila.expira_en <= momento:
        raise ErrorApi(401, "V-46")
    if tipo == "SESION":
        _controlar_inactividad(db, fila, momento)
    return fila


def _controlar_inactividad(db: Session, fila, momento: datetime) -> None:
    """Cierre por inactividad en el servidor: si la sesión pasó 30 minutos sin uso se revoca y responde 401 (V-51);
    si sigue vigente, anota la hora de este uso (como mucho una vez por minuto).
    """
    if _sesion_inactiva(fila, momento):
        fila.revocado = True
        db.commit()
        raise ErrorApi(401, "V-51")
    if fila.usado_en is None or momento - fila.usado_en >= _REFRESCO_USO:
        fila.usado_en = momento
        db.commit()


def token_actual(authorization: str | None = Header(default=None), db: Session = Depends(get_db)):
    """Fila TOKEN de la sesión (la usa A-06 para revocarla)."""
    return _buscar_token(db, authorization, "SESION")


def usuario_actual(authorization: str | None = Header(default=None), db: Session = Depends(get_db)):
    """Dependencia de FastAPI: el usuario dueño de la sesión. La usan todos los servicios que exigen ingresar."""
    return _buscar_token(db, authorization, "SESION").usuario


def exigir_admin(usuario=Depends(usuario_actual)):
    """Dependencia de FastAPI: deja pasar solo al rol ADMIN; un agricultor recibe 403 (E-06)."""
    if usuario.rol != "ADMIN":
        raise ErrorApi(403, "E-06")
    return usuario


def usuario_pendiente(authorization: str | None = Header(default=None), db: Session = Depends(get_db)):
    """Usuario de una cuenta PENDIENTE que presenta su token de activación (A-02, A-03 y A-04)."""
    fila = _buscar_token(db, authorization, "ACTIVACION")
    usuario = fila.usuario
    if usuario.estado != "PENDIENTE":
        raise ErrorApi(401, "V-46")
    if ahora() - usuario.creado_en > timedelta(hours=24):
        db.delete(usuario)  # cascada: se van sus OTP y tokens; el correo queda libre
        db.commit()
        raise ErrorApi(410, "V-15")
    return usuario
