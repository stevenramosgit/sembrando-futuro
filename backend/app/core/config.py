"""Configuración: lee las variables del archivo .env (documento 20, tabla de variables de entorno)."""
import os
from dataclasses import dataclass
from dotenv import load_dotenv

load_dotenv()

UNIDADES = {"segundo": 1, "minuto": 60, "hora": 3600, "dia": 86400}


def leer_limite(texto: str) -> tuple[int, int]:
    """Convierte '5/hora' en (5, 3600): máximo de peticiones y tamaño de la ventana en segundos."""
    cantidad, unidad = texto.strip().lower().split("/")
    return int(cantidad), UNIDADES[unidad.strip()]


@dataclass
class Configuracion:
    entorno: str
    clave_secreta: str
    database_url: str | None
    db_host: str
    db_port: int
    db_name: str
    db_user: str
    db_password: str
    db_ssl_ca: str
    dominio: str
    brevo_api_key: str
    correo_remitente: str
    correo_contacto: str
    otp_fijo_pruebas: str
    token_dias: int
    cors_origenes: list[str]
    proxy_confiable: bool
    limites: dict[str, str]
    carpeta_pwa: str


def cargar() -> Configuracion:
    return Configuracion(
        entorno=os.getenv("ENTORNO", "desarrollo"),
        clave_secreta=os.getenv("CLAVE_SECRETA", "cambiar-por-un-texto-largo-y-aleatorio"),
        database_url=os.getenv("DATABASE_URL") or None,
        db_host=os.getenv("DB_HOST", "localhost"),
        db_port=int(os.getenv("DB_PORT", "3306")),
        db_name=os.getenv("DB_NAME", "sembrando_futuro"),
        db_user=os.getenv("DB_USER", "root"),
        db_password=os.getenv("DB_PASSWORD", ""),
        db_ssl_ca=os.getenv("DB_SSL_CA", ""),
        dominio=os.getenv("DOMINIO", ""),
        brevo_api_key=os.getenv("BREVO_API_KEY", ""),
        correo_remitente=os.getenv("CORREO_REMITENTE", "mikaelramos@unicomfacauca.edu.co"),
        correo_contacto=os.getenv("CORREO_CONTACTO", "mikaelramos@unicomfacauca.edu.co"),
        otp_fijo_pruebas=os.getenv("OTP_FIJO_PRUEBAS", "482915"),
        token_dias=int(os.getenv("TOKEN_DIAS", "30")),
        cors_origenes=[o.strip() for o in os.getenv("CORS_ORIGENES", "").split(",") if o.strip()],
        proxy_confiable=os.getenv("PROXY_CONFIABLE", "no").lower() in ("si", "sí", "1", "true"),
        limites={
            "LIMITE_REGISTRO": os.getenv("LIMITE_REGISTRO", "5/hora"),
            "LIMITE_INGRESO": os.getenv("LIMITE_INGRESO", "10/minuto"),
            "LIMITE_REENVIO": os.getenv("LIMITE_REENVIO", "6/hora"),
            "LIMITE_GENERAL": os.getenv("LIMITE_GENERAL", "120/minuto"),
            "LIMITE_SALUD": os.getenv("LIMITE_SALUD", "30/minuto"),
        },
        carpeta_pwa=os.getenv("CARPETA_PWA", ""),
    )


config = cargar()
