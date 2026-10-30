"""Esquemas de los servicios del administrador."""
from pydantic import BaseModel, ConfigDict


class ClaveNuevaIn(BaseModel):
    """Cuerpo de AD-02: la clave nueva (se valida con las reglas de V-07)."""
    model_config = ConfigDict(extra="ignore")
    clave_nueva: str | None = None


class UsuarioLista(BaseModel):
    """Una cuenta en la lista de AD-01."""
    id: str
    nombre: str
    ubicacion: str
    correo: str
    estado: str
    rol: str
    creado_en: str


class ListaUsuarios(BaseModel):
    """Respuesta de AD-01: total de cuentas, página y la lista."""
    total: int
    pagina: int
    usuarios: list[UsuarioLista]
