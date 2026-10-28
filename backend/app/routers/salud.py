from datetime import datetime, timezone

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.errores import ErrorApi
from app.core.limites import limitar
from app.database.connection import get_db
from app.domain.fechas import a_iso
from app.schemas.salud import SaludOut

router = APIRouter(tags=["Salud"])


@router.get("/salud", response_model=SaludOut, summary="H-01 Estado del servidor",
            dependencies=[Depends(limitar("H-01", "LIMITE_SALUD"))])
def salud(db: Session = Depends(get_db)):
    try:
        db.execute(text("SELECT 1"))
    except Exception:
        raise ErrorApi(503, "V-45")
    return {"estado": "ok", "hora": a_iso(datetime.now(timezone.utc).replace(tzinfo=None))}
