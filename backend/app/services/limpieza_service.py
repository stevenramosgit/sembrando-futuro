"""Tareas de mantenimiento (documento 20): cuentas pendientes vencidas, bloqueos y datos temporales viejos."""
import time
from datetime import timedelta

from sqlalchemy import delete, or_, select
from sqlalchemy.orm import Session

from app.core.seguridad import ahora
from app.models.usuario import IntentoIngreso, Otp, Token, Usuario


_ultima = 0.0


def limpiar_liviano(db: Session, cada_segundos: int = 60) -> None:
    """Limpieza de cuentas pendientes y bloqueos cumplidos al atender A-01 y A-05 (el plan gratuito no trae programador de tareas).
    Se hace como máximo una vez por minuto para no recargar cada petición."""
    global _ultima
    if time.monotonic() - _ultima < cada_segundos:
        return
    _ultima = time.monotonic()
    limpiar_pendientes(db)
    limpiar_bloqueos(db)


def limpiar_pendientes(db: Session) -> int:
    """Elimina las cuentas PENDIENTE de más de 24 horas (la cascada borra sus códigos y tokens; el correo queda libre)."""
    limite = ahora() - timedelta(hours=24)
    cuentas = list(db.scalars(select(Usuario).where(Usuario.estado == "PENDIENTE", Usuario.creado_en < limite)))
    for c in cuentas:
        db.delete(c)
    db.commit()
    return len(cuentas)


def limpiar_bloqueos(db: Session) -> int:
    """Quita los bloqueos de ingreso ya cumplidos."""
    momento = ahora()
    n = 0
    for u in db.scalars(select(Usuario).where(Usuario.bloqueado_hasta.is_not(None), Usuario.bloqueado_hasta <= momento)):
        u.bloqueado_hasta = None
        u.intentos_fallidos = 0
        n += 1
    r = db.execute(delete(IntentoIngreso).where(IntentoIngreso.bloqueado_hasta.is_not(None),
                                                IntentoIngreso.bloqueado_hasta <= momento))
    db.commit()
    return n + (r.rowcount or 0)


def limpiar_vencidos(db: Session) -> int:
    """Borra códigos usados o vencidos hace más de 24 h, tokens vencidos o revocados hace más de 30 días e intentos viejos."""
    momento = ahora()
    n = 0
    n += db.execute(delete(Otp).where(or_(Otp.usado.is_(True), Otp.expira_en < momento),
                                      Otp.expira_en < momento - timedelta(hours=24))).rowcount or 0
    n += db.execute(delete(Token).where(Token.expira_en < momento - timedelta(days=30))).rowcount or 0
    n += db.execute(delete(Token).where(Token.revocado.is_(True), Token.creado_en < momento - timedelta(days=30))).rowcount or 0
    n += db.execute(delete(IntentoIngreso).where(
        or_(IntentoIngreso.bloqueado_hasta.is_(None), IntentoIngreso.bloqueado_hasta <= momento),
        IntentoIngreso.actualizado_en < momento - timedelta(hours=24))).rowcount or 0
    db.commit()
    return n
