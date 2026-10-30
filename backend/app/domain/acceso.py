"""Decisiones puras de acceso: iniciar sesión (RF-03) y verificar el código de activación (RF-02).

Son las funciones 2 y 3 del documento 22. Trabajan sobre un diccionario con el estado de la cuenta o del código para
poder probarse sin base de datos; los servicios copian a ese diccionario las filas de USUARIO y OTP y devuelven los cambios.
"""

MAX_FALLOS = 5
MAX_INTENTOS_OTP = 5
MINUTOS_VIGENCIA_OTP = 15
HORAS_VIGENCIA_CUENTA = 24


def _igual(real, dado):
    """Comparación simple que usan las pruebas sin base de datos; el servidor la reemplaza por la verificación Argon2."""
    return real == dado


def iniciar_sesion(correo, clave, cuenta, ahora, bloqueo=15, verificar=_igual):
    """Devuelve ('error', código) o ('ok',). Cambia 'fallos' y 'bloqueado_hasta' de la cuenta.

    cuenta: None (no existe) o {'clave', 'estado', 'fallos', 'bloqueado_hasta'}; en los servicios 'clave' es el hash guardado.
    ahora y bloqueado_hasta usan la misma unidad (en la prueba, minutos; en el servidor, datetime y timedelta).
    """
    if not correo:
        return ("error", "V-16")
    if not clave:
        return ("error", "V-16")
    if cuenta is None:
        return ("error", "V-17")
    if cuenta["bloqueado_hasta"] is not None:
        if ahora < cuenta["bloqueado_hasta"]:
            return ("error", "V-18")
    if not verificar(cuenta["clave"], clave):
        cuenta["fallos"] = cuenta["fallos"] + 1
        if cuenta["fallos"] == MAX_FALLOS:
            cuenta["bloqueado_hasta"] = ahora + bloqueo
            cuenta["fallos"] = 0
            return ("error", "V-18")
        return ("error", "V-17")
    if cuenta["estado"] == "PENDIENTE":
        return ("error", "V-19")
    cuenta["fallos"] = 0
    cuenta["bloqueado_hasta"] = None
    return ("ok",)


def verificar_codigo(codigo, otp, verificar=_igual):
    """Devuelve ('error', código[, intentos restantes]) o ('ok',).

    otp: {'codigo', 'intentos', 'min_envio', 'h_cuenta'}; en los servicios 'codigo' es el hash guardado.
    """
    if otp["h_cuenta"] > HORAS_VIGENCIA_CUENTA:
        return ("error", "V-15")
    if not (isinstance(codigo, str) and len(codigo) == 6 and codigo.isascii() and codigo.isdigit()):
        return ("error", "V-09")
    if otp["intentos"] >= MAX_INTENTOS_OTP:
        return ("error", "V-12")
    if otp["min_envio"] > MINUTOS_VIGENCIA_OTP:
        return ("error", "V-11")
    if not verificar(otp["codigo"], codigo):
        otp["intentos"] = otp["intentos"] + 1
        if otp["intentos"] == MAX_INTENTOS_OTP:
            return ("error", "V-12")
        return ("error", "V-10", MAX_INTENTOS_OTP - otp["intentos"])
    return ("ok",)
