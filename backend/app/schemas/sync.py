from typing import Any

from pydantic import BaseModel, ConfigDict


class RegistroSync(BaseModel):
    model_config = ConfigDict(extra="ignore")
    tipo: str
    id: str
    updated_at: str
    eliminado: bool = False
    datos: dict[str, Any] = {}


class PushIn(BaseModel):
    model_config = ConfigDict(extra="ignore")
    dispositivo_id: str | None = None
    enviado_en: str | None = None
    registros: list[RegistroSync]


class ResultadoSync(BaseModel):
    id: str
    estado: str
    updated_at: str | None = None
    codigo: str | None = None
    mensaje: str | None = None
    registro: dict[str, Any] | None = None  # copia del servidor cuando el estado es ACTUALIZADO_POR_SERVIDOR


class PushOut(BaseModel):
    resultados: list[ResultadoSync]


class PullOut(BaseModel):
    servidor_ahora: str
    hay_mas: bool
    registros: list[dict[str, Any]]
