from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.limites import limitar
from app.core.seguridad import usuario_actual
from app.database.connection import get_db
from app.schemas.resumen import ResumenCiclo
from app.services import resumen_service

router = APIRouter(prefix="/ciclos", tags=["Ciclo"])


@router.get("/{id}/resumen", response_model=ResumenCiclo, summary="R-01 Resumen de un ciclo",
            dependencies=[Depends(limitar("R-01", "LIMITE_GENERAL"))])
def resumen(id: str, usuario=Depends(usuario_actual), db: Session = Depends(get_db)):
    return resumen_service.resumen_ciclo(db, usuario, id)
