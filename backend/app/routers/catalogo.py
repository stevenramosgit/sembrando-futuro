from fastapi import APIRouter, Depends
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app.core.limites import limitar
from app.database.connection import get_db
from app.schemas.catalogo import CatalogoOut
from app.services import catalogo_service

router = APIRouter(tags=["Catálogo"])


@router.get("/catalogo", response_model=CatalogoOut, summary="C-01 Catálogo de cultivos",
            responses={304: {"description": "El catálogo no cambió"}},
            dependencies=[Depends(limitar("C-01", "LIMITE_GENERAL"))])
def catalogo(desde: str | None = None, db: Session = Depends(get_db)):
    resultado = catalogo_service.consultar(db, desde)
    if resultado is None:
        return Response(status_code=304)
    return resultado
