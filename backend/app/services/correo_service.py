"""Envío del código de verificación por la API HTTPS de Brevo (documento 20). Un solo método en desarrollo y en producción."""
import logging

import httpx

from app.core.config import config
from app.core.errores import ErrorApi

registro = logging.getLogger("sembrando_futuro.correo")
URL_BREVO = "https://api.brevo.com/v3/smtp/email"


def texto_del_mensaje(nombre: str, codigo: str) -> tuple[str, str]:
    """Asunto y texto del correo con el código: saluda por el primer nombre, dice que vence en 15 minutos y advierte
    que no se comparta.
    """
    primer_nombre = (nombre or "").split()[0] if (nombre or "").strip() else ""
    saludo = f"Hola, {primer_nombre}:" if primer_nombre else "Hola:"
    cuerpo = (f"{saludo}\n\nSu código de verificación es {codigo}. El código vence en 15 minutos.\n\n"
              "Si usted no creó una cuenta, ignore este mensaje.\n"
              "Nunca comparta este código con nadie.")
    return "Su código de Sembrando Futuro", cuerpo


def enviar_codigo(correo: str, nombre: str, codigo: str) -> None:
    """Envía el código. Si Brevo no responde bien, lanza 503 (V-45) y quien llama revierte la operación."""
    asunto, cuerpo = texto_del_mensaje(nombre, codigo)
    if not config.brevo_api_key:
        if config.entorno in ("desarrollo", "pruebas"):
            registro.warning("BREVO_API_KEY vacía: el correo no se envía. Para %s: %s", correo, asunto)
            return
        raise ErrorApi(503, "V-45")
    datos = {
        "sender": {"name": "Sembrando Futuro", "email": config.correo_remitente},
        "to": [{"email": correo, "name": nombre or correo}],
        "subject": asunto,
        "textContent": cuerpo,
    }
    try:
        respuesta = httpx.post(URL_BREVO, json=datos, headers={"api-key": config.brevo_api_key, "accept": "application/json"},
                               timeout=10.0)
    except httpx.HTTPError:
        raise ErrorApi(503, "V-45")
    if respuesta.status_code >= 300:
        registro.error("Brevo respondió %s", respuesta.status_code)  # sin el cuerpo: podría traer datos personales
        raise ErrorApi(503, "V-45")
