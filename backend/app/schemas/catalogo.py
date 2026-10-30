"""Esquemas del catálogo de cultivos (C-01 y AD-04)."""
from pydantic import BaseModel


class CultivoOut(BaseModel):
    """Un cultivo del catálogo con su ficha técnica."""
    codigo: str
    nombre: str
    unidad_comercial: str
    distancia_min_m: float
    distancia_max_m: float
    marcos_permitidos: list[str]
    fuente_tecnica: str
    ficha_tecnica: dict | None = None
    actualizado_en: str | None = None


class CatalogoOut(BaseModel):
    """Respuesta de C-01: versión, fecha del último cambio y cultivos."""
    version: int
    actualizado_en: str
    cultivos: list[CultivoOut]


class CultivoIn(BaseModel):
    """Cuerpo de AD-04. La validación detallada está en catalogo_service para devolver un mensaje por campo."""
    nombre: str | None = None
    unidad_comercial: str | None = None
    distancia_min_m: float | int | None = None
    distancia_max_m: float | int | None = None
    marcos_permitidos: list[str] | None = None
    fuente_tecnica: str | None = None
    ficha_tecnica: dict | None = None
