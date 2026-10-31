"""Esquemas de A-01 a A-06 (documento 18). Los campos de entrada son opcionales a propósito: las reglas V-xx
las aplica el servidor campo por campo para poder devolver todos los errores a la vez."""
from pydantic import BaseModel, ConfigDict


class RegistroIn(BaseModel):
    """Cuerpo de A-01. Los campos son opcionales en el esquema para que el servicio devuelva los mensajes propios (V-xx)
    en lugar del error genérico de FastAPI.
    """
    model_config = ConfigDict(extra="ignore")
    nombre: str | None = None
    ubicacion: str | None = None
    correo: str | None = None
    correo_confirmacion: str | None = None
    clave: str | None = None
    autoriza_datos: bool | None = None


class OtpIn(BaseModel):
    """Cuerpo de A-02: el código de 6 dígitos."""
    codigo: str | None = None


class CambiarCorreoIn(BaseModel):
    """Cuerpo de A-04: correo nuevo y su confirmación."""
    correo_nuevo: str | None = None
    correo_nuevo_confirmacion: str | None = None


class IngresoIn(BaseModel):
    """Cuerpo de A-05: correo y clave."""
    correo: str | None = None
    clave: str | None = None


class RegistroOut(BaseModel):
    """Respuesta de A-01: estado, vencimiento del código, reenvíos y token de activación."""
    estado: str
    correo: str
    otp_expira_en: str
    reenvios_restantes: int
    espera_segundos: int
    token_activacion: str


class ActivacionOut(BaseModel):
    """Respuesta de A-02: la cuenta quedó ACTIVA."""
    estado: str


class ReenvioOut(BaseModel):
    """Respuesta de A-03 y A-04: reenvíos restantes, espera y nuevo vencimiento."""
    reenvios_restantes: int
    espera_segundos: int
    otp_expira_en: str
    correo: str | None = None


class UsuarioOut(BaseModel):
    """Datos públicos del usuario que recibe la PWA al ingresar."""
    id: str
    nombre: str
    ubicacion: str
    correo: str
    rol: str


class IngresoOut(BaseModel):
    """Respuesta de A-05: token de sesión, vencimiento (12 horas), minutos sin uso que cierran la sesión (30) y usuario."""
    token: str
    expira_en: str
    inactividad_min: int
    usuario: UsuarioOut
