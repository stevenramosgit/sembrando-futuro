"""Fórmulas del dominio (RF-13, RF-18, RF-24, RF-25 y RF-28). Funciones puras: sin base de datos ni FastAPI."""
from datetime import date
from decimal import ROUND_HALF_UP, Decimal
from fractions import Fraction
from math import ceil

from app.domain.fechas import sumar_anios, sumar_meses


K_TRESBOLILLO = Decimal("0.866025")
_K = Fraction("0.866025")


def redondear(valor, decimales: int = 0) -> Decimal:
    """Redondeo de la mitad hacia arriba (0,5 sube), como pide RF-18."""
    return Decimal(str(valor)).quantize(Decimal(1).scaleb(-decimales), rounding=ROUND_HALF_UP)


def redondear_arriba(valor, decimales: int = 2) -> Decimal:
    """Redondeo hacia arriba (techo) con a lo sumo 'decimales' decimales: 4.444,441 pasa a 4.444,45. Es exacto (usa fracciones)."""
    f = valor if isinstance(valor, Fraction) else Fraction(str(valor))
    factor = 10 ** decimales
    return Decimal(ceil(f * factor)) / Decimal(factor)


def entero(valor) -> int:
    """Redondea al entero (la mitad sube). Se usa para dejar los valores en pesos enteros."""
    return int(redondear(valor, 0))


def area_efectiva(bruta, no_sembrable) -> Decimal:
    """Área efectiva = área bruta − área no sembrable, en hectáreas con 4 decimales (RF-13)."""
    return redondear(Decimal(str(bruta)) - Decimal(str(no_sembrable)), 4)


def matas_exactas(marco, d1, d2) -> Fraction:
    """Matas por hectárea sin redondear, como fracción exacta (marco en mayúsculas)."""
    a, b = Fraction(str(d1)), Fraction(str(d2 or 0))
    if marco == "RECTANGULAR":
        return Fraction(10000) / (a * b)
    if marco == "CUADRADO":
        return Fraction(10000) / (a * a)
    return Fraction(10000) / (a * a * _K)


def matas_por_hectarea(marco, d1, d2, rango):
    """RF-18, función 1 del documento 22. Devuelve ('error', código) o ('ok', matas por hectárea, advertencia).

    marco: 'CUADRADO', 'RECTANGULAR' o 'TRESBOLILLO' (en mayúsculas o minúsculas); rango: (mínimo, máximo) del cultivo o None.
    El resultado se redondea hacia arriba con dos decimales.
    """
    m = (marco or "").upper() or None
    if m is None:
        return ("error", "V-32")
    if d1 < 0.01:
        return ("error", "V-33")
    if m == "RECTANGULAR" and d2 < 0.01:
        return ("error", "V-33")
    n = matas_exactas(m, d1, d2)
    advertencia = None
    if rango is not None:
        distancias = [d1, d2] if m == "RECTANGULAR" else [d1]
        if any(d < rango[0] or d > rango[1] for d in distancias):
            advertencia = "V-34"
    return ("ok", float(redondear_arriba(n, 2)), advertencia)


def matas_del_ciclo(marco, d1, d2, area_efectiva_ha) -> int:
    """Matas del ciclo: matas por hectárea exactas × área efectiva, hacia arriba (no existe media mata)."""
    return ceil(matas_exactas((marco or "").upper(), d1, d2) * Fraction(str(area_efectiva_ha)))


def matas_por_lote(matas_ha, area_efectiva_ha) -> int:
    """Matas de un lote a partir de matas por hectárea ya calculadas, hacia arriba. Para un resultado exacto use matas_del_ciclo."""
    return ceil(Fraction(str(matas_ha)) * Fraction(str(area_efectiva_ha)))


def costo_jornal(cantidad, valor_diario) -> int:
    """RF-24: costo total = número de jornales × valor diario, redondeado al peso."""
    return entero(Decimal(str(cantidad)) * Decimal(str(valor_diario)))


def total_ingreso(cantidad, precio_unitario) -> int:
    """RF-25: total = cantidad × precio unitario, redondeado al peso."""
    return entero(Decimal(str(cantidad)) * Decimal(str(precio_unitario)))


def calcular_utilidad(gastos, ingresos, area):
    """RF-28, función 4 del documento 22. 'gastos' incluye los jornales.

    Devuelve ('ok', total_gastos, total_ingresos, utilidad, rentabilidad_pct, utilidad_por_hectarea).
    """
    total_gastos = 0
    for g in gastos:
        total_gastos += g
    total_ingresos = 0
    for i in ingresos:
        total_ingresos += i
    utilidad = total_ingresos - total_gastos
    if total_gastos == 0:
        rentabilidad = 0.0
    else:
        rentabilidad = float(redondear(Decimal(utilidad) / Decimal(total_gastos) * 100, 1))
    por_ha = entero(Decimal(utilidad) / Decimal(str(area))) if area else 0
    return ("ok", total_gastos, total_ingresos, utilidad, rentabilidad, por_ha)


# ---------------------------------------------------------------- vigencia del ciclo (modelo simplificado)
def fecha_fin_estimada(siembra: date, vigencia_anios):
    """Fecha de cierre estimada = siembra + vigencia en años; None si el ciclo no tiene vigencia."""
    if vigencia_anios is None:
        return None
    return sumar_anios(siembra, int(vigencia_anios))


def semaforo_vigencia(siembra: date, vigencia_anios, hoy: date):
    """Devuelve (fecha_fin_estimada, años_restantes, semáforo) o (None, None, None) sin vigencia.

    Semáforo: VERDE si falta más del 50 % del tiempo estimado; AMARILLO entre el 20 % y el 50 %;
    ROJO si falta menos del 20 % o ya se cumplió. (Con 7 años, faltando 2 = 28,6 %: AMARILLO.)
    """
    fin = fecha_fin_estimada(siembra, vigencia_anios)
    if fin is None:
        return (None, None, None)
    total = (fin - siembra).days
    faltan = (fin - hoy).days
    restantes = round(max(faltan, 0) / 365.25, 1)
    if faltan <= 0 or faltan < 0.2 * total:
        color = "ROJO"
    elif faltan <= 0.5 * total:
        color = "AMARILLO"
    else:
        color = "VERDE"
    return (fin, restantes, color)


# ---------------------------------------------------------------- ficha técnica (costos aproximados)
def estimar_costos(ficha: dict, matas: int) -> dict:
    """Costos aproximados de sembrar y mantener 'matas' plantas con la ficha técnica del cultivo.

    ficha: base_plantas, costo_hoyado_cop y costo_colino_cop (por planta), insumo_anual_cop (por planta y año),
    jornales_limpieza_anio y jornales_riego_anio (por cada base_plantas plantas y por año).
    Devuelve siembra_inicial_cop, insumos_anuales_cop y jornales_anuales (cantidad, con un decimal).
    """
    n = Decimal(matas)
    siembra = entero(n * (Decimal(ficha["costo_hoyado_cop"]) + Decimal(ficha["costo_colino_cop"])))
    insumos = entero(n * Decimal(ficha["insumo_anual_cop"]))
    jornales = redondear_arriba(Fraction(matas) / Fraction(int(ficha["base_plantas"]))
                                * (Fraction(str(ficha["jornales_limpieza_anio"])) + Fraction(str(ficha["jornales_riego_anio"]))), 2)
    return {"siembra_inicial_cop": siembra, "insumos_anuales_cop": insumos, "jornales_anuales": float(jornales)}


# ---------------------------------------------------------------- proyección de cosecha (ficha técnica)
def proyectar_cosecha(ficha: dict, matas: int, siembra: date):
    """Proyección orientativa de un cultivo del ciclo, o None si la ficha no trae los datos de cosecha.

    ficha: base_plantas, meses_primera_cosecha, meses_cosecha, cosecha_unica, produccion_base (unidades comerciales por
    base_plantas plantas, por año o por cosecha única) y precio_ref_cop con precio_ref_fecha (pesos por unidad comercial).
    Devuelve primera_cosecha (fecha), temporadas (meses 1 a 12), cosecha_unica, produccion_estimada (unidades, hacia arriba con
    dos decimales), precio_ref_cop, precio_ref_fecha e ingreso_estimado_cop (pesos; None si no hay precio).
    """
    meses, produccion_base = ficha.get("meses_primera_cosecha"), ficha.get("produccion_base")
    if meses is None or produccion_base is None:
        return None
    produccion = redondear_arriba(Fraction(matas) / Fraction(int(ficha["base_plantas"])) * Fraction(str(produccion_base)), 2)
    precio = ficha.get("precio_ref_cop")
    return {"primera_cosecha": sumar_meses(siembra, int(meses)), "temporadas": ficha.get("meses_cosecha"),
            "cosecha_unica": bool(ficha.get("cosecha_unica")), "produccion_estimada": float(produccion),
            "precio_ref_cop": precio, "precio_ref_fecha": ficha.get("precio_ref_fecha"),
            "ingreso_estimado_cop": None if precio is None else total_ingreso(produccion, precio)}
