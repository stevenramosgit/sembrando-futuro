"""Límite de peticiones por dirección IP (E-10). Ventana deslizante en memoria; un contador por servicio.

Funciona con un solo proceso de Uvicorn (documento 20): si se usan varios procesos, cada uno cuenta aparte.
"""
import time
from collections import defaultdict, deque

from fastapi import Request

from app.core import config as cfg
from app.core.errores import ErrorApi

_ventanas: dict[tuple[str, str], deque] = defaultdict(deque)


def ip_de(request: Request) -> str:
    if cfg.config.proxy_confiable:
        reenviada = request.headers.get("x-forwarded-for")
        if reenviada:
            return reenviada.split(",")[0].strip()
    return request.client.host if request.client else "desconocida"


def reiniciar() -> None:
    """Borra todos los contadores (lo usan las pruebas)."""
    _ventanas.clear()


def limitar(nombre_servicio: str, variable: str):
    """Fábrica de dependencias: limitar('A-01', 'LIMITE_REGISTRO') cuenta las peticiones de cada IP a A-01."""

    def dependencia(request: Request) -> None:
        maximo, ventana = cfg.leer_limite(cfg.config.limites[variable])
        ahora = time.monotonic()
        cola = _ventanas[(nombre_servicio, ip_de(request))]
        while cola and ahora - cola[0] >= ventana:
            cola.popleft()
        if len(cola) >= maximo:
            espera = max(1, int(ventana - (ahora - cola[0])) + 1)
            raise ErrorApi(429, "E-10", cabeceras={"Retry-After": str(espera)}, extra={"espera_segundos": espera})
        cola.append(ahora)

    return dependencia
