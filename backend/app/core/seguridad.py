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
    return _hasher.hash(clave)


def verificar_clave(clave: str, hash_guardado: str | None) -> bool:
    try:
        return _hasher.verify(hash_guardado or _HASH_FALSO, clave) and hash_guardado is not None
    except (VerifyMismatchError, InvalidHashError):
        return False


def _huella(valor: str) -> str:
    """Hash con la clave interna del servidor mezclada (HMAC-SHA256): los tokens y los OTP no se guardan en claro."""
    return hmac.new(config.clave_secreta.encode(), valor.encode(), hashlib.sha256).hexdigest()


def hash_token(token: str) -> str:
    return _huella("token:" + token)


def hash_otp(codigo: str) -> str:
    return _huella("otp:" + codigo)


def generar_token() -> str:
    return "tkn_" + secrets.token_urlsafe(32)


def generar_codigo_otp() -> str:
    if config.entorno == "pruebas":
        return config.otp_fijo_pruebas
    return f"{secrets.randbelow(900000) + 100000}"


def expira_token(tipo: str) -> datetime:
    return ahora() + (timedelta(days=config.token_dias) if tipo == "SESION" else timedelta(hours=24))


# ---------------------------------------------------------------- dependencias de FastAPI
def _token_de(authorization: str | None) -> str:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise ErrorApi(401, "V-46")
    token = authorization[7:].strip()
    if not token:
        raise ErrorApi(401, "V-46")
    return token


def _buscar_token(db: Session, authorization: str | None, tipo: str):
    from app.models.usuario import Token

    token = _token_de(authorization)
    fila = db.scalar(select(Token).where(Token.token_hash == hash_token(token)))
    if fila is None or fila.tipo != tipo or fila.revocado or fila.expira_en <= ahora():
        raise ErrorApi(401, "V-46")
    return fila


def token_actual(authorization: str | None = Header(default=None), db: Session = Depends(get_db)):
    """Fila TOKEN de la sesión (la usa A-06 para revocarla)."""
    return _buscar_token(db, authorization, "SESION")


def usuario_actual(authorization: str | None = Header(default=None), db: Session = Depends(get_db)):
    return _buscar_token(db, authorization, "SESION").usuario


def exigir_admin(usuario=Depends(usuario_actual)):
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
