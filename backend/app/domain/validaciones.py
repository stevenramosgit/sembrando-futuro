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
    """Detecta textos sin sentido: palabras de relleno ('asdf', 'prueba') o secuencias del teclado."""
    bajo = s.lower()
    return bajo in BASURA or any(t in bajo for t in TECLADO)


def _nombre_ok(s, minimo: int, maximo: int, coma: bool) -> bool:
    """Comprueba un nombre de persona o de lugar: largo permitido, empieza con letra, solo letras, espacios, punto y guion
    (y coma si se permite), sin signos repetidos y sin texto basura.
    """
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
    """Nombre completo: de 2 a 60 caracteres con letras (V-01). Devuelve None si es válido o el código del error."""
    return None if _nombre_ok(s, 2, 60, False) else "V-01"


def v_ubicacion(s):
    """Ubicación (municipio o vereda): de 3 a 60 caracteres; admite coma (V-02)."""
    return None if _nombre_ok(s, 3, 60, True) else "V-02"


def v_nombre_lugar(s):
    """Nombre de finca o nombre informativo del lote (V-22)."""
    return None if _nombre_ok(s, 2, 60, False) else "V-22"


def v_correo(s):
    """Correo con formato válido, de hasta 254 caracteres y sin texto basura antes de la arroba (V-03)."""
    if not isinstance(s, str):
        return "V-03"
    s = s.strip()
    if len(s) > 254 or not _CORREO.match(s) or _basura(s.split("@")[0]):
        return "V-03"
    return None


def _secuencia(s: str) -> bool:
    """Detecta 5 caracteres seguidos en orden (abcde, 12345) o al revés, que hacen débil una clave."""
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
    """Observaciones opcionales de un gasto: hasta 150 caracteres con letras, números y puntuación básica (V-38)."""
    if s is None:
        return None
    if not isinstance(s, str):
        return "V-38"
    s = s.strip()
    if len(s) > 150 or (s and not re.match("^[" + LETRAS + "0-9 .,\\-]+$", s)):
        return "V-38"
    return None


def v_codigo_otp(s):
    """El código de verificación debe tener exactamente 6 dígitos (V-09)."""
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
    """Número entero de JSON (5 o 5.0); un booleano, un texto o un número con decimales devuelven None."""
    if isinstance(valor, bool):
        return None
    if isinstance(valor, int):
        return valor
    if isinstance(valor, float) and valor.is_integer():
        return int(valor)
    return None


def v_area_bruta(valor):
    """Área bruta en hectáreas: de 0,0001 a 10.000 con hasta 4 decimales (V-24)."""
    d = decimal_de(valor, 4)
    return None if d is not None and Decimal("0.0001") <= d <= 10000 else "V-24"


def v_pendiente(valor):
    """Pendiente del terreno en porcentaje: de 0 a 100 con hasta 2 decimales (V-25)."""
    d = decimal_de(valor, 2)
    return None if d is not None and 0 <= d <= 100 else "V-25"


def v_no_sembrable(valor, bruta):
    """Área no sembrable: de 0 hasta menos que el área bruta, con hasta 4 decimales (V-26)."""
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
    """Distancia de siembra en metros: de 0,01 a 10 con hasta 2 decimales (V-33)."""
    d = decimal_de(valor, 2)
    return None if d is not None and Decimal("0.01") <= d <= 10 else "V-33"


def v_valor_gasto(valor):
    """V-35 (rango) y V-36 (solo dígitos)."""
    v = entero_de(valor)
    if v is None:
        return "V-36"
    return None if 1 <= v <= 50_000_000 else "V-35"


def v_valor_jornal(valor):
    """Valor de un jornal en pesos: entero de 1 a 50.000.000 (V-40)."""
    v = entero_de(valor)
    return None if v is not None and 1 <= v <= 50_000_000 else "V-40"


def v_jornales(valor):
    """Cantidad de jornales: de 0,5 a 999, en pasos de medio jornal (V-39)."""
    d = decimal_de(valor, 1)
    return None if d is not None and Decimal("0.5") <= d <= 999 and (d * 2) % 1 == 0 else "V-39"


def v_cantidad(valor):
    """Cantidad vendida en la unidad comercial del cultivo: de 0,1 a 10.000 (V-41)."""
    d = decimal_de(valor, 4)
    return None if d is not None and Decimal("0.1") <= d <= 10000 else "V-41"


def v_precio(valor):
    """Precio unitario en pesos: entero de 1 a 50.000.000 (V-42)."""
    v = entero_de(valor)
    return None if v is not None and 1 <= v <= 50_000_000 else "V-42"


# ---------------------------------------------------------------- fechas
def v_siembra(fecha: date, hoy: date):
    """Fecha de siembra: desde el 1 de enero de 2020 hasta un año después de hoy (V-48)."""
    return None if INICIO_SIEMBRAS <= fecha <= un_anio_despues(hoy) else "V-48"


def v_cierre(cierre: date, siembra: date, hoy: date):
    """Fecha de cierre del ciclo: entre la siembra y hoy (V-29)."""
    return None if siembra <= cierre <= hoy else "V-29"


def v_fecha_registro(fecha: date, siembra: date, hoy: date):
    """Fecha de un gasto, jornal o ingreso: entre la siembra del ciclo y hoy (V-47)."""
    return None if siembra <= fecha <= hoy else "V-47"
