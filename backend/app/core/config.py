"""Configuración: lee las variables de entorno (archivo .env en el computador; panel de Render en el despliegue).

La tabla completa de variables está en el documento 20. Al arrancar en producción, validar_produccion() revisa que
no falte nada importante (clave secreta propia, clave de Brevo, dominio, certificado de Aiven) y, si falta,
la aplicación no arranca y el registro de Render dice qué corregir. Así un error de configuración se ve en el
despliegue y no cuando un agricultor intenta registrarse.
"""
import os
from dataclasses import dataclass
from dotenv import load_dotenv

load_dotenv()

UNIDADES = {"segundo": 1, "minuto": 60, "hora": 3600, "dia": 86400}
ENTORNOS = ("desarrollo", "pruebas", "produccion")
CLAVE_DE_EJEMPLO = "cambiar-por-un-texto-largo-y-aleatorio"
CARPETA_BACKEND = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))


def leer_limite(texto: str) -> tuple[int, int]:
    """Convierte '5/hora' en (5, 3600): máximo de peticiones y tamaño de la ventana en segundos."""
    cantidad, unidad = texto.strip().lower().split("/")
    return int(cantidad), UNIDADES[unidad.strip()]


@dataclass
class Configuracion:
    """Todos los valores de configuración ya convertidos a su tipo (números, listas, rutas). Se lee una sola vez al arrancar."""
    entorno: str
    clave_secreta: str
    database_url: str | None
    db_host: str
    db_port: int
    db_name: str
    db_user: str
    db_password: str
    db_ssl_ca: str
    dominios: list[str]
    brevo_api_key: str
    correo_remitente: str
    correo_contacto: str
    otp_fijo_pruebas: str
    sesion_horas: int
    sesion_inactividad_min: int
    cors_origenes: list[str]
    proxy_confiable: bool
    proxy_saltos: int
    limites: dict[str, str]
    carpeta_pwa: str


def ruta_certificado(texto: str) -> str:
    """Ruta del certificado de Aiven. Si es relativa (por ejemplo 'ca.pem'), se toma desde la carpeta backend,
    sin importar desde qué carpeta se ejecute el comando."""
    if not texto:
        return ""
    return texto if os.path.isabs(texto) else os.path.join(CARPETA_BACKEND, texto)


def lista(texto: str) -> list[str]:
    """Convierte 'a.com, b.com' en ['a.com', 'b.com'] (sin espacios ni elementos vacíos)."""
    return [x.strip() for x in texto.split(",") if x.strip()]


def cargar() -> Configuracion:
    """Lee cada variable de entorno y aplica el valor por defecto de desarrollo cuando no está definida."""
    return Configuracion(
        entorno=os.getenv("ENTORNO", "desarrollo"),
        clave_secreta=os.getenv("CLAVE_SECRETA", CLAVE_DE_EJEMPLO),
        database_url=os.getenv("DATABASE_URL") or None,
        db_host=os.getenv("DB_HOST", "localhost"),
        db_port=int(os.getenv("DB_PORT", "3306")),
        db_name=os.getenv("DB_NAME", "sembrando_futuro"),
        db_user=os.getenv("DB_USER", "root"),
        db_password=os.getenv("DB_PASSWORD", ""),
        db_ssl_ca=ruta_certificado(os.getenv("DB_SSL_CA", "")),
        dominios=lista(os.getenv("DOMINIO", "")),
        brevo_api_key=os.getenv("BREVO_API_KEY", ""),
        correo_remitente=os.getenv("CORREO_REMITENTE", "mikaelramos@unicomfacauca.edu.co"),
        correo_contacto=os.getenv("CORREO_CONTACTO", "mikaelramos@unicomfacauca.edu.co"),
        otp_fijo_pruebas=os.getenv("OTP_FIJO_PRUEBAS", "482915"),
        sesion_horas=int(os.getenv("SESION_HORAS", "12")),
        sesion_inactividad_min=int(os.getenv("SESION_INACTIVIDAD_MIN", "30")),
        cors_origenes=lista(os.getenv("CORS_ORIGENES", "")),
        proxy_confiable=os.getenv("PROXY_CONFIABLE", "no").lower() in ("si", "sí", "1", "true"),
        proxy_saltos=int(os.getenv("PROXY_SALTOS", "1")),
        limites={
            "LIMITE_REGISTRO": os.getenv("LIMITE_REGISTRO", "5/hora"),
            "LIMITE_INGRESO": os.getenv("LIMITE_INGRESO", "10/minuto"),
            "LIMITE_REENVIO": os.getenv("LIMITE_REENVIO", "6/hora"),
            "LIMITE_GENERAL": os.getenv("LIMITE_GENERAL", "120/minuto"),
            "LIMITE_SALUD": os.getenv("LIMITE_SALUD", "30/minuto"),
        },
        carpeta_pwa=os.getenv("CARPETA_PWA", ""),
    )


def validar_produccion(c: Configuracion) -> list[str]:
    """Devuelve la lista de problemas de configuración (vacía si todo está bien).

    En cualquier entorno: ENTORNO debe ser uno de los tres valores y, si se indicó un certificado, el archivo debe existir.
    Solo en producción: la clave secreta debe ser propia y larga, y deben estar la clave de Brevo, el remitente,
    el dominio publicado y el certificado de Aiven (o una DATABASE_URL completa).
    """
    problemas = []
    if c.entorno not in ENTORNOS:
        problemas.append(f"ENTORNO='{c.entorno}' no es válido; use desarrollo, pruebas o produccion (sin tilde).")
    if c.db_ssl_ca and not os.path.isfile(c.db_ssl_ca):
        problemas.append(f"No existe el certificado {c.db_ssl_ca}: descargue el CA certificate de Aiven y guárdelo como backend/ca.pem.")
    if c.entorno != "produccion":
        return problemas
    if c.clave_secreta == CLAVE_DE_EJEMPLO or len(c.clave_secreta) < 32:
        problemas.append("CLAVE_SECRETA debe ser un texto aleatorio propio de 32 caracteres o más (Render la genera sola).")
    if not c.brevo_api_key:
        problemas.append("Falta BREVO_API_KEY: sin ella no se pueden enviar los códigos de verificación.")
    if not c.correo_remitente:
        problemas.append("Falta CORREO_REMITENTE: debe ser un remitente verificado en Brevo.")
    if not c.dominios:
        problemas.append("Falta DOMINIO: escriba el dominio publicado (por ejemplo sembrando-futuro.onrender.com).")
    if not c.database_url and not c.db_ssl_ca:
        problemas.append("Falta DB_SSL_CA: Aiven exige conexión cifrada (TLS) con su certificado ca.pem.")
    if c.proxy_saltos < 1:
        problemas.append("PROXY_SALTOS debe ser 1 o más.")
    return problemas


config = cargar()
