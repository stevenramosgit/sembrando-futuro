"""Aplicación FastAPI de Sembrando Futuro: API en /api/v1 y la PWA en la raíz."""
import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.core import errores
from app.core.config import config, validar_produccion
from app.database import connection
from app.routers import admin, auth, catalogo, ciclos, salud, sync
from app.services import limpieza_service

registro = logging.getLogger("sembrando_futuro")
PREFIJO = "/api/v1"
CSP = ("default-src 'self'; img-src 'self' data:; style-src 'self' 'unsafe-inline'; script-src 'self'; connect-src 'self'; "
       "manifest-src 'self'; worker-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'")


@asynccontextmanager
async def ciclo_de_vida(_: FastAPI):
    """Al arrancar se hace la limpieza liviana (cuentas pendientes vencidas y bloqueos cumplidos)."""
    try:
        with connection.SessionLocal() as db:
            limpieza_service.limpiar_pendientes(db)
            limpieza_service.limpiar_bloqueos(db)
    except Exception:  # la base de datos puede no estar lista (por ejemplo, antes de la migración)
        registro.warning("No se pudo hacer la limpieza inicial", exc_info=True)
    yield


def crear_app() -> FastAPI:
    """Arma la aplicación: revisa la configuración, registra los errores con el formato de la API, agrega la
    seguridad (hosts de confianza, CORS y cabeceras), monta los seis grupos de servicios bajo /api/v1 y sirve la PWA."""
    problemas = validar_produccion(config)
    if problemas:
        raise RuntimeError("Configuración incompleta:\n- " + "\n- ".join(problemas))
    # Sin páginas de documentación automática (/docs, /redoc, /openapi.json): la API es interna de la PWA (documento 18).
    app = FastAPI(title="Sembrando Futuro", version="1.0.0", lifespan=ciclo_de_vida,
                  docs_url=None, redoc_url=None, openapi_url=None)
    errores.registrar(app)

    if config.dominios:
        # Hosts de confianza: solo se atienden los dominios publicados (por ejemplo el propio y el de onrender.com).
        # localhost queda permitido porque Render revisa el puerto con Host: localhost al desplegar.
        from starlette.middleware.trustedhost import TrustedHostMiddleware
        app.add_middleware(TrustedHostMiddleware, allowed_hosts=[*config.dominios, "localhost", "127.0.0.1", "testserver"])

    if config.cors_origenes:
        app.add_middleware(CORSMiddleware, allow_origins=config.cors_origenes, allow_methods=["GET", "POST", "PUT", "DELETE"],
                           allow_headers=["Authorization", "Content-Type"], max_age=600)

    @app.middleware("http")
    async def cabeceras_de_seguridad(request, call_next):
        """Agrega a cada respuesta las cabeceras de seguridad: HTTPS obligatorio (HSTS), sin adivinar tipos de archivo,
        sin enviar la página de origen, política de contenido (CSP) y sin caché para la API. El Service Worker se revisa en cada visita.
        """
        respuesta = await call_next(request)
        respuesta.headers.setdefault("Strict-Transport-Security", "max-age=31536000; includeSubDomains")
        respuesta.headers.setdefault("X-Content-Type-Options", "nosniff")
        respuesta.headers.setdefault("Referrer-Policy", "no-referrer")
        ruta = request.url.path
        if ruta.startswith(PREFIJO):
            respuesta.headers.setdefault("Cache-Control", "no-store")
        if ruta == "/sw.js":
            respuesta.headers["Cache-Control"] = "no-cache"  # el navegador revisa si hay Service Worker nuevo en cada visita
        respuesta.headers.setdefault("Content-Security-Policy", CSP)
        return respuesta

    for r in (auth.router, ciclos.router, catalogo.router, sync.router, salud.router, admin.router):
        app.include_router(r, prefix=PREFIJO)

    carpeta = config.carpeta_pwa or os.path.join(os.path.dirname(__file__), "..", "..", "frontend")
    carpeta = os.path.abspath(carpeta)
    if os.path.isdir(carpeta):
        app.mount("/", StaticFiles(directory=carpeta, html=True), name="pwa")
    return app


app = crear_app()
