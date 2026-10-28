from pydantic import BaseModel


class SaludOut(BaseModel):
    estado: str
    hora: str
