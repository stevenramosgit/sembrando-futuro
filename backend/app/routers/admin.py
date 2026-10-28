from typing import Literal

from fastapi import APIRouter, Depends, Query
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app.core.limites import limitar
from app.core.seguridad import exigir_admin
from app.database.connection import get_db
from app.schemas.admin import ClaveNuevaIn, ListaUsuarios
from app.schemas.catalogo import CultivoIn, CultivoOut
from app.schemas.resumen import ResumenUsuario
from app.services import admin_service, catalogo_service

router = APIRouter(prefix="/admin", tags=["Administración"],
                   dependencies=[Depends(limitar("AD", "LIMITE_GENERAL")), Depends(exigir_admin)])


@router.get("/usuarios", response_model=ListaUsuarios, summary="AD-01 Listar cuentas")
def listar(estado: Literal["ACTIVA", "PENDIENTE"] | None = None, pagina: int = Query(1, ge=1),
           limite: int = Query(50, ge=1, le=100), db: Session = Depends(get_db)):
    return admin_service.listar(db, estado, pagina, limite)


@router.post("/usuarios/{id}/clave", status_code=204, summary="AD-02 Cambiar la clave de una cuenta")
def cambiar_clave(id: str, datos: ClaveNuevaIn, db: Session = Depends(get_db)):
    admin_service.cambiar_clave(db, id, datos.clave_nueva)
    return Response(status_code=204)


@router.delete("/usuarios/{id}", status_code=204, summary="AD-03 Eliminar una cuenta y sus datos")
def eliminar(id: str, db: Session = Depends(get_db)):
    admin_service.eliminar(db, id)
    return Response(status_code=204)


@router.put("/catalogo/{codigo}", response_model=CultivoOut, summary="AD-04 Actualizar la ficha de un cultivo")
def actualizar_cultivo(codigo: str, datos: CultivoIn, db: Session = Depends(get_db)):
    return catalogo_service.actualizar(db, codigo, datos)


@router.get("/usuarios/{id}/resumen", response_model=ResumenUsuario, summary="AD-05 Resumen de una cuenta")
def resumen(id: str, db: Session = Depends(get_db)):
    return admin_service.resumen(db, id)
