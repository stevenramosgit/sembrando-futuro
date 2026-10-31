"""Servicios de sincronización (S-01 y S-02) entre la base del teléfono (IndexedDB) y MySQL."""
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.limites import limitar
from app.core.seguridad import usuario_actual
from app.database.connection import get_db
from app.schemas.sync import PullOut, PushIn, PushOut
from app.services import sync_service

router = APIRouter(prefix="/sync", tags=["Sincronización"])


@router.post("/push", response_model=PushOut, response_model_exclude_none=True, summary="S-01 Enviar registros",
             dependencies=[Depends(limitar("S-01", "LIMITE_GENERAL"))])
def push(entrada: PushIn, usuario=Depends(usuario_actual), db: Session = Depends(get_db)):
    """S-01: recibe hasta 500 registros creados o cambiados sin conexión y devuelve, para cada uno, si se aceptó o por qué no."""
    return sync_service.push(db, usuario, entrada)


@router.get("/pull", response_model=PullOut, summary="S-02 Recibir cambios",
            dependencies=[Depends(limitar("S-02", "LIMITE_GENERAL"))])
def pull(desde: str | None = None, limite: int = Query(500), usuario=Depends(usuario_actual),
         db: Session = Depends(get_db)):
    """S-02: entrega los registros del usuario que cambiaron después de 'desde', en páginas, para actualizar el teléfono."""
    return sync_service.pull(db, usuario, desde, limite)
