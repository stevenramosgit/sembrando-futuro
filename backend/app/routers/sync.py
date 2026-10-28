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
    return sync_service.push(db, usuario, entrada)


@router.get("/pull", response_model=PullOut, summary="S-02 Recibir cambios",
            dependencies=[Depends(limitar("S-02", "LIMITE_GENERAL"))])
def pull(desde: str | None = None, limite: int = Query(500), usuario=Depends(usuario_actual),
         db: Session = Depends(get_db)):
    return sync_service.pull(db, usuario, desde, limite)
