"""Servicios de cuenta (A-01 a A-06): registro con código por correo, activación, ingreso y salida."""
from fastapi import APIRouter, Depends
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app.core.limites import limitar
from app.core.seguridad import token_actual, usuario_pendiente
from app.database.connection import get_db
from app.schemas import auth as s
from app.services import cuentas_service as svc

router = APIRouter(prefix="/auth", tags=["Autenticación"])


@router.post("/registro", status_code=201, response_model=s.RegistroOut, summary="A-01 Registrar cuenta",
             dependencies=[Depends(limitar("A-01", "LIMITE_REGISTRO"))])
def registro(datos: s.RegistroIn, db: Session = Depends(get_db)):
    """A-01: crea la cuenta en estado PENDIENTE y envía el código de 6 dígitos al correo. Devuelve el token de activación."""
    return svc.registrar(db, datos)


@router.post("/otp/verificar", response_model=s.ActivacionOut, summary="A-02 Verificar código",
             dependencies=[Depends(limitar("A-02", "LIMITE_INGRESO"))])
def verificar(datos: s.OtpIn, usuario=Depends(usuario_pendiente), db: Session = Depends(get_db)):
    """A-02: verifica el código; si es correcto la cuenta queda ACTIVA."""
    return svc.verificar_otp(db, usuario, datos.codigo)


@router.post("/otp/reenviar", response_model=s.ReenvioOut, response_model_exclude_none=True, summary="A-03 Reenviar código",
             dependencies=[Depends(limitar("A-03", "LIMITE_REENVIO"))])
def reenviar(usuario=Depends(usuario_pendiente), db: Session = Depends(get_db)):
    """A-03: envía un código nuevo (máximo 3 reenvíos, con 60 segundos de espera entre uno y otro)."""
    return svc.reenviar_otp(db, usuario)


@router.post("/correo/cambiar", response_model=s.ReenvioOut, summary="A-04 Cambiar correo de una cuenta pendiente",
             dependencies=[Depends(limitar("A-04", "LIMITE_REENVIO"))])
def cambiar_correo(datos: s.CambiarCorreoIn, usuario=Depends(usuario_pendiente), db: Session = Depends(get_db)):
    """A-04: corrige el correo de una cuenta que aún no se activa y envía el código al correo nuevo."""
    return svc.cambiar_correo(db, usuario, datos)


@router.post("/ingreso", response_model=s.IngresoOut, summary="A-05 Ingresar",
             dependencies=[Depends(limitar("A-05", "LIMITE_INGRESO"))])
def ingreso(datos: s.IngresoIn, db: Session = Depends(get_db)):
    """A-05: inicia sesión con correo y clave; tras 5 fallos seguidos la cuenta se bloquea 15 minutos."""
    return svc.iniciar_sesion(db, datos)


@router.post("/salida", status_code=204, summary="A-06 Cerrar sesión",
             dependencies=[Depends(limitar("A-06", "LIMITE_GENERAL"))])
def salida(token=Depends(token_actual), db: Session = Depends(get_db)):
    """A-06: cierra la sesión revocando su token."""
    svc.cerrar_sesion(db, token)
    return Response(status_code=204)
