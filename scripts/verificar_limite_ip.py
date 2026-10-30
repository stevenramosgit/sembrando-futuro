"""Comprueba en el sitio publicado que el límite de ingresos por IP no se puede saltar inventando la cabecera X-Forwarded-For.

Uso (desde el computador, con el servicio ya desplegado y despierto):
    python scripts/verificar_limite_ip.py https://su-dominio

Qué hace: envía 11 intentos de ingreso con correos inexistentes (no bloquea ninguna cuenta real) y en cada uno
inventa una IP distinta al principio de X-Forwarded-For, como haría un atacante.
- Si el intento 11 responde 429 (E-10), el límite cuenta la IP real: PROXY_SALTOS está bien.
- Si los 11 responden 401, el servidor está creyendo la IP inventada: suba PROXY_SALTOS en 1 en Render y repita.
Después, desde otra red (por ejemplo, los datos del teléfono), abra la aplicación e intente ingresar una vez:
si responde "Demasiados intentos" sin haber intentado nada, PROXY_SALTOS quedó alto (todos comparten la IP del proxy):
bájelo en 1. Espere un minuto entre pruebas para que el contador se vacíe (LIMITE_INGRESO=10/minuto).
Solo usa la biblioteca estándar de Python.
"""
import json
import random
import sys
import urllib.error
import urllib.request


def intentar(base: str, numero: int) -> int:
    """Hace un intento de ingreso con una IP inventada y devuelve el código HTTP de la respuesta."""
    cuerpo = json.dumps({"correo": f"verificacion{numero}@correo-inexistente.com", "clave": "NoEsUnaClave#1"}).encode()
    falsa = ".".join(str(random.randint(1, 254)) for _ in range(4))
    pedido = urllib.request.Request(f"{base}/api/v1/auth/ingreso", data=cuerpo, method="POST",
                                    headers={"Content-Type": "application/json", "X-Forwarded-For": falsa})
    try:
        with urllib.request.urlopen(pedido, timeout=90) as respuesta:
            return respuesta.status
    except urllib.error.HTTPError as error:
        return error.code


def main() -> int:
    if len(sys.argv) != 2:
        print(__doc__)
        return 2
    base = sys.argv[1].rstrip("/")
    estados = [intentar(base, i) for i in range(11)]
    print("Respuestas:", estados)
    if estados[-1] == 429:
        print("Bien: inventar la IP no sirve; el límite cuenta la IP real.")
        return 0
    print("Atención: el servidor cree la IP inventada. Suba PROXY_SALTOS en 1 en Render y repita la prueba.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
