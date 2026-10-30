"""Servicio H-01: estado del servidor. Lo usan Render (chequeo de salud) y el monitor externo de disponibilidad (RNF-10)."""
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
    """H-01: responde 'ok' con la hora del servidor si la base de datos contesta; si no, 503 (V-45)."""
    try:
        db.execute(text("SELECT 1"))
    except Exception:
        raise ErrorApi(503, "V-45")
    return {"estado": "ok", "hora": a_iso(datetime.now(timezone.utc).replace(tzinfo=None))}
