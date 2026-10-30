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
    """IP del visitante, que se usa para contar las peticiones.

    Sin proxy, es la IP de la conexión. Detrás de Render (PROXY_CONFIABLE=si), la conexión llega desde el proxy y la IP
    real viene en la cabecera X-Forwarded-For, que es una lista: "ip_que_escribio_el_cliente, ..., ip_real, proxy1, proxy2".
    Cada proxy agrega una dirección AL FINAL, y el cliente puede inventar las del principio para saltarse el límite.
    Por eso se cuenta desde la derecha: PROXY_SALTOS=N toma la N-ésima dirección desde el final (la que escribió
    el primer proxy de confianza). El valor correcto para Render se comprueba después de desplegar (documento 20).
    """
    if cfg.config.proxy_confiable:
        direcciones = [x.strip() for x in request.headers.get("x-forwarded-for", "").split(",") if x.strip()]
        if direcciones:
            return direcciones[-min(cfg.config.proxy_saltos, len(direcciones))]
    return request.client.host if request.client else "desconocida"


def reiniciar() -> None:
    """Borra todos los contadores (lo usan las pruebas)."""
    _ventanas.clear()


def limitar(nombre_servicio: str, variable: str):
    """Fábrica de dependencias: limitar('A-01', 'LIMITE_REGISTRO') cuenta las peticiones de cada IP a A-01."""

    def dependencia(request: Request) -> None:
        """Cuenta la petición en la ventana de la IP para este servicio y responde 429 (E-10) con Retry-After si se pasó del máximo."""
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
