"""Esquemas de la sincronización (S-01 y S-02)."""
from typing import Any

from pydantic import BaseModel, ConfigDict


class RegistroSync(BaseModel):
    """Un registro que viene del teléfono: tipo (finca, ciclo, ...), UUID, fecha de modificación, si se eliminó y sus datos."""
    model_config = ConfigDict(extra="ignore")
    tipo: str
    id: str
    updated_at: str
    eliminado: bool = False
    datos: dict[str, Any] = {}


class PushIn(BaseModel):
    """Cuerpo de S-01: los registros pendientes del teléfono."""
    model_config = ConfigDict(extra="ignore")
    dispositivo_id: str | None = None
    enviado_en: str | None = None
    registros: list[RegistroSync]


class ResultadoSync(BaseModel):
    """Resultado de un registro: ACEPTADO, RECHAZADO (con código y mensaje) o ACTUALIZADO_POR_SERVIDOR (con la copia del servidor)."""
    id: str
    estado: str
    updated_at: str | None = None
    codigo: str | None = None
    mensaje: str | None = None
    registro: dict[str, Any] | None = None  # copia del servidor cuando el estado es ACTUALIZADO_POR_SERVIDOR


class PushOut(BaseModel):
    """Respuesta de S-01: un resultado por registro, en el mismo orden."""
    resultados: list[ResultadoSync]


class PullOut(BaseModel):
    """Respuesta de S-02: hora del servidor, si hay más páginas y los registros."""
    servidor_ahora: str
    hay_mas: bool
    registros: list[dict[str, Any]]
