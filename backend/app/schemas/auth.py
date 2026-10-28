"""Esquemas de A-01 a A-06 (documento 18). Los campos de entrada son opcionales a propósito: las reglas V-xx
las aplica el servidor campo por campo para poder devolver todos los errores a la vez."""
from pydantic import BaseModel, ConfigDict


class RegistroIn(BaseModel):
    model_config = ConfigDict(extra="ignore")
    nombre: str | None = None
    ubicacion: str | None = None
    correo: str | None = None
    correo_confirmacion: str | None = None
    clave: str | None = None
    autoriza_datos: bool | None = None


class OtpIn(BaseModel):
    codigo: str | None = None


class CambiarCorreoIn(BaseModel):
    correo_nuevo: str | None = None
    correo_nuevo_confirmacion: str | None = None


class IngresoIn(BaseModel):
    correo: str | None = None
    clave: str | None = None


class RegistroOut(BaseModel):
    estado: str
    correo: str
    otp_expira_en: str
    reenvios_restantes: int
    espera_segundos: int
    token_activacion: str


class ActivacionOut(BaseModel):
    estado: str


class ReenvioOut(BaseModel):
    reenvios_restantes: int
    espera_segundos: int
    otp_expira_en: str
    correo: str | None = None


class UsuarioOut(BaseModel):
    id: str
    nombre: str
    ubicacion: str
    correo: str
    rol: str


class IngresoOut(BaseModel):
    token: str
    expira_en: str
    usuario: UsuarioOut
