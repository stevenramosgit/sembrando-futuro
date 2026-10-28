"""Reglas de validación V-xx del Apéndice J, como funciones puras.

Cada función devuelve None cuando el dato es válido o el código de la regla incumplida (por ejemplo 'V-07').
Los mensajes se obtienen con app.core.errores.texto(código). Los mismos criterios están en frontend/src/calculos/validaciones.js.
"""
import re
from datetime import date
from decimal import Decimal, InvalidOperation

from app.domain.fechas import INICIO_SIEMBRAS, un_anio_despues

LETRAS = "A-Za-zÁÉÍÓÚÜÑáéíóúüñ"
SIMBOLOS = r"!@#$%^&*()_+\-=\[\]{}|;:,.<>?"
BASURA = {"0", "00", "000", "123", "1234", "12345", "test", "prueba", "asdf", "xxx", "null", "undefined", "nada", "ninguno"}
TECLADO = ("qwert", "werty", "asdfg", "sdfgh", "zxcvb", "xcvbn", "12345", "23456", "34567", "abcde", "bcdef")
CATEGORIAS = ("semillas", "abonos", "agroquimicos", "herramientas", "transporte", "otros")
MARCOS = ("cuadrado", "rectangular", "tresbolillo")

_CORREO = re.compile(
    r"^[A-Za-z0-9!#$%&'*+/=?^_`{|}~-]+(\.[A-Za-z0-9!#$%&'*+/=?^_`{|}~-]+)*"
    r"@[A-Za-z0-9]([A-Za-z0-9-]{0,61}[A-Za-z0-9])?(\.[A-Za-z0-9]([A-Za-z0-9-]{0,61}[A-Za-z0-9])?)+$")
_CLAVE = re.compile(r"^[A-Za-z0-9" + SIMBOLOS + r"]+$")
_SIMBOLO = re.compile(r"[" + SIMBOLOS + r"]")


# ---------------------------------------------------------------- texto
def _repetido(s: str) -> bool:
    """Más de 3 caracteres iguales seguidos."""
    return re.search(r"(.)\1{3,}", s, re.IGNORECASE) is not None


def _basura(s: str) -> bool:
    bajo = s.lower()
    return bajo in BASURA or any(t in bajo for t in TECLADO)


def _nombre_ok(s, minimo: int, maximo: int, coma: bool) -> bool:
    if not isinstance(s, str):
        return False
    s = s.strip()
    if not (minimo <= len(s) <= maximo):
        return False
    patron = "^[" + LETRAS + "][" + LETRAS + " .\\-" + ("," if coma else "") + "]*$"
    if not re.match(patron, s):
        return False
    return not (_repetido(s) or _basura(s))


def v_nombre(s):
    return None if _nombre_ok(s, 2, 60, False) else "V-01"


def v_ubicacion(s):
    return None if _nombre_ok(s, 3, 60, True) else "V-02"


def v_nombre_lugar(s):
    """Nombre de finca o nombre informativo del lote (V-22)."""
    return None if _nombre_ok(s, 2, 60, False) else "V-22"


def v_correo(s):
    if not isinstance(s, str):
        return "V-03"
    s = s.strip()
    if len(s) > 254 or not _CORREO.match(s) or _basura(s.split("@")[0]):
        return "V-03"
    return None


def _secuencia(s: str) -> bool:
    bajo = s.lower()
    sube = baja = 1
    for i in range(1, len(bajo)):
        d = ord(bajo[i]) - ord(bajo[i - 1])
        sube = sube + 1 if d == 1 else 1
        baja = baja + 1 if d == -1 else 1
        if sube >= 5 or baja >= 5:
            return True
    return False


def v_clave(clave, correo="", nombre=""):
    """V-07: 10 a 64 caracteres; mayúscula, minúscula, número y símbolo; sin espacios, tildes, repeticiones ni secuencias."""
    if not isinstance(clave, str) or not (10 <= len(clave) <= 64) or not _CLAVE.match(clave):
        return "V-07"
    if not (re.search(r"[A-Z]", clave) and re.search(r"[a-z]", clave) and re.search(r"\d", clave) and _SIMBOLO.search(clave)):
        return "V-07"
    if _repetido(clave) or _secuencia(clave):
        return "V-07"
    bajo = clave.lower()
    local = (correo or "").split("@")[0].lower()
    if len(local) >= 4 and local in bajo:
        return "V-07"
    for parte in (nombre or "").lower().split():
        if len(parte) >= 4 and parte in bajo:
            return "V-07"
    return None


def v_observaciones(s):
    if s is None:
        return None
    if not isinstance(s, str):
        return "V-38"
    s = s.strip()
    if len(s) > 150 or (s and not re.match("^[" + LETRAS + "0-9 .,\\-]+$", s)):
        return "V-38"
    return None


def v_codigo_otp(s):
    return None if isinstance(s, str) and re.fullmatch(r"[0-9]{6}", s) else "V-09"


# ---------------------------------------------------------------- números
def decimal_de(valor, max_decimales: int):
    """Número JSON (no texto ni booleano) como Decimal con a lo sumo 'max_decimales' decimales; si no, None."""
    if isinstance(valor, bool) or not isinstance(valor, (int, float, Decimal)):
        return None
    try:
        d = Decimal(str(valor))
    except InvalidOperation:
        return None
    if not d.is_finite() or -d.as_tuple().exponent > max_decimales:
        return None
    return d


def entero_de(valor):
    if isinstance(valor, bool):
        return None
    if isinstance(valor, int):
        return valor
    if isinstance(valor, float) and valor.is_integer():
        return int(valor)
    return None


def v_area_bruta(valor):
    d = decimal_de(valor, 4)
    return None if d is not None and Decimal("0.0001") <= d <= 10000 else "V-24"


def v_pendiente(valor):
    d = decimal_de(valor, 2)
    return None if d is not None and 0 <= d <= 100 else "V-25"


def v_no_sembrable(valor, bruta):
    d = decimal_de(valor, 4)
    b = decimal_de(bruta, 4)
    return None if d is not None and b is not None and 0 <= d < b else "V-26"


def v_vigencia(valor):
    """V-49: años estimados del ciclo, entero entre 1 y 50 (el campo es opcional: None es válido)."""
    if valor is None:
        return None
    v = entero_de(valor)
    return None if v is not None and 1 <= v <= 50 else "V-49"


def v_distancia(valor):
    d = decimal_de(valor, 2)
    return None if d is not None and Decimal("0.01") <= d <= 10 else "V-33"


def v_valor_gasto(valor):
    """V-35 (rango) y V-36 (solo dígitos)."""
    v = entero_de(valor)
    if v is None:
        return "V-36"
    return None if 1 <= v <= 50_000_000 else "V-35"


def v_valor_jornal(valor):
    v = entero_de(valor)
    return None if v is not None and 1 <= v <= 50_000_000 else "V-40"


def v_jornales(valor):
    d = decimal_de(valor, 1)
    return None if d is not None and Decimal("0.5") <= d <= 999 and (d * 2) % 1 == 0 else "V-39"


def v_cantidad(valor):
    d = decimal_de(valor, 4)
    return None if d is not None and Decimal("0.1") <= d <= 10000 else "V-41"


def v_precio(valor):
    v = entero_de(valor)
    return None if v is not None and 1 <= v <= 50_000_000 else "V-42"


# ---------------------------------------------------------------- fechas
def v_siembra(fecha: date, hoy: date):
    return None if INICIO_SIEMBRAS <= fecha <= un_anio_despues(hoy) else "V-48"


def v_cierre(cierre: date, siembra: date, hoy: date):
    return None if siembra <= cierre <= hoy else "V-29"


def v_fecha_registro(fecha: date, siembra: date, hoy: date):
    return None if siembra <= fecha <= hoy else "V-47"
