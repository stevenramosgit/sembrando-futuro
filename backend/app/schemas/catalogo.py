from pydantic import BaseModel


class CultivoOut(BaseModel):
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
    version: int
    actualizado_en: str
    cultivos: list[CultivoOut]


class CultivoIn(BaseModel):
    nombre: str | None = None
    unidad_comercial: str | None = None
    distancia_min_m: float | int | None = None
    distancia_max_m: float | int | None = None
    marcos_permitidos: list[str] | None = None
    fuente_tecnica: str | None = None
    ficha_tecnica: dict | None = None
