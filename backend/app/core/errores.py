"""Códigos de error V-xx (Apéndice J) y E-xx (documento 18) y sus manejadores.

Toda respuesta de error usa el mismo cuerpo:
    {"error": {"codigo": "V-07", "mensaje": "...", "campos": {"clave": {"codigo": "V-07", "mensaje": "..."}}}}
"""
from fastapi import Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.core.mensajes import MENSAJES


def texto(codigo: str, **valores) -> str:
    """Devuelve el mensaje de una regla; reemplaza N, HH:MM y (mín.–máx. m) cuando se entregan."""
    msg = MENSAJES[codigo]
    if "n" in valores:
        msg = msg.replace("N", str(valores["n"]), 1)
    if "hora" in valores:
        msg = msg.replace("HH:MM", valores["hora"])
    if "rango" in valores:
        msg = msg.replace("(mín.–máx. m)", valores["rango"])
    return msg


class ErrorApi(Exception):
    """Error de negocio: el manejador lo convierte en la respuesta JSON estándar."""

    def __init__(self, estado: int, codigo: str, campos: dict | None = None, extra: dict | None = None,
                 cabeceras: dict | None = None, mensaje: str | None = None, **valores):
        """estado: código HTTP; codigo: regla incumplida (V-xx o E-xx); campos: errores por campo; extra: datos adicionales
        (por ejemplo, segundos de espera); cabeceras: cabeceras HTTP (Retry-After); valores: datos para completar el mensaje.
        """
        super().__init__(codigo)
        self.estado = estado
        self.codigo = codigo
        self.mensaje = mensaje or texto(codigo, **valores)
        self.campos = campos
        self.extra = extra or {}
        self.cabeceras = cabeceras or {}


class ErroresDeCampos(Exception):
    """Varios campos incumplen sus reglas a la vez (400): se devuelven todos en 'campos'."""

    def __init__(self, campos: dict[str, tuple[str, str]], estado: int = 400, codigo: str | None = None):
        """campos: {campo: (código, mensaje)}; estado: código HTTP (400 por defecto); codigo: código general opcional."""
        super().__init__("campos")
        self.estado = estado
        self.campos = campos  # {campo: (codigo, mensaje)}
        self.codigo = codigo  # si no se indica, se usa el del primer campo


def cuerpo_error(codigo: str, mensaje: str, campos: dict | None = None, extra: dict | None = None) -> dict:
    """Arma el cuerpo JSON estándar de error: código, mensaje y, si hay, los errores por campo y los datos adicionales."""
    error = {"codigo": codigo, "mensaje": mensaje}
    if campos:
        error["campos"] = {c: {"codigo": v[0], "mensaje": v[1]} for c, v in campos.items()}
    if extra:
        error.update(extra)
    return {"error": error}


async def manejar_error_api(_: Request, exc: ErrorApi) -> JSONResponse:
    """Convierte un ErrorApi (error de negocio) en la respuesta JSON con su código HTTP y sus cabeceras."""
    return JSONResponse(cuerpo_error(exc.codigo, exc.mensaje, exc.campos, exc.extra),
                        status_code=exc.estado, headers=exc.cabeceras)


async def manejar_campos(_: Request, exc: ErroresDeCampos) -> JSONResponse:
    """Convierte varios errores de campos en una sola respuesta 400; el código general es el indicado o el del primer campo."""
    if exc.codigo:
        return JSONResponse(cuerpo_error(exc.codigo, texto(exc.codigo), exc.campos), status_code=exc.estado)
    primero = next(iter(exc.campos.values()))
    return JSONResponse(cuerpo_error(primero[0], primero[1], exc.campos), status_code=exc.estado)


async def manejar_validacion(_: Request, exc: RequestValidationError) -> JSONResponse:
    """Reemplaza el 422 de FastAPI por un 400 con el formato del documento 18 (E-03)."""
    return JSONResponse(cuerpo_error("E-03", texto("E-03")), status_code=400)


async def manejar_http(_: Request, exc: StarletteHTTPException) -> JSONResponse:
    """Traduce los errores HTTP de Starlette al formato propio: 404 (ruta inexistente) es E-07 y 405 (método no permitido) es E-03."""
    if exc.status_code == 404:
        return JSONResponse(cuerpo_error("E-07", texto("E-07")), status_code=404)
    if exc.status_code == 405:
        return JSONResponse(cuerpo_error("E-03", texto("E-03")), status_code=405)
    return JSONResponse(cuerpo_error("V-45", texto("V-45")), status_code=exc.status_code)


async def manejar_inesperado(_: Request, exc: Exception) -> JSONResponse:
    """Cualquier error no previsto responde 500 con el mensaje genérico V-45, sin mostrar detalles internos al usuario."""
    return JSONResponse(cuerpo_error("V-45", texto("V-45")), status_code=500)


def registrar(app) -> None:
    """Conecta los cinco manejadores de error con la aplicación FastAPI."""
    app.add_exception_handler(ErrorApi, manejar_error_api)
    app.add_exception_handler(ErroresDeCampos, manejar_campos)
    app.add_exception_handler(RequestValidationError, manejar_validacion)
    app.add_exception_handler(StarletteHTTPException, manejar_http)
    app.add_exception_handler(Exception, manejar_inesperado)
