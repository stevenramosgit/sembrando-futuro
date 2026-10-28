from pydantic import BaseModel, ConfigDict


class ClaveNuevaIn(BaseModel):
    model_config = ConfigDict(extra="ignore")
    clave_nueva: str | None = None


class UsuarioLista(BaseModel):
    id: str
    nombre: str
    ubicacion: str
    correo: str
    estado: str
    rol: str
    creado_en: str


class ListaUsuarios(BaseModel):
    total: int
    pagina: int
    usuarios: list[UsuarioLista]
