"""Esquema del estado del servidor (H-01)."""
from pydantic import BaseModel


class SaludOut(BaseModel):
    """Respuesta de H-01: 'ok' y la hora del servidor en UTC."""
    estado: str
    hora: str
