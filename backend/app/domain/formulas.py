"""Fórmulas del dominio (RF-13, RF-18, RF-24, RF-25 y RF-28). Funciones puras: sin base de datos ni FastAPI."""
from datetime import date
from decimal import ROUND_HALF_UP, Decimal

from app.domain.fechas import sumar_anios


K_TRESBOLILLO = Decimal("0.866025")


def redondear(valor, decimales: int = 0) -> Decimal:
    """Redondeo de la mitad hacia arriba (0,5 sube), como pide RF-18."""
    return Decimal(str(valor)).quantize(Decimal(1).scaleb(-decimales), rounding=ROUND_HALF_UP)


def entero(valor) -> int:
    return int(redondear(valor, 0))


def area_efectiva(bruta, no_sembrable) -> Decimal:
    return redondear(Decimal(str(bruta)) - Decimal(str(no_sembrable)), 4)


def matas_por_hectarea(marco, d1, d2, rango):
    """RF-18, función 1 del documento 22. Devuelve ('error', código) o ('ok', matas por hectárea, advertencia).

    marco: 'CUADRADO', 'RECTANGULAR' o 'TRESBOLILLO' (en mayúsculas o minúsculas); rango: (mínimo, máximo) del cultivo o None.
    """
    m = (marco or "").upper() or None
    if m is None:
        return ("error", "V-32")
    if d1 < 0.01:
        return ("error", "V-33")
    if m == "RECTANGULAR":
        if d2 < 0.01:
            return ("error", "V-33")
        n = 10000 / (d1 * d2)
    elif m == "CUADRADO":
        n = 10000 / (d1 ** 2)
    else:
        n = 10000 / (d1 ** 2 * float(K_TRESBOLILLO))
    advertencia = None
    if rango is not None:
        distancias = [d1, d2] if m == "RECTANGULAR" else [d1]
        if any(d < rango[0] or d > rango[1] for d in distancias):
            advertencia = "V-34"
    return ("ok", round(n, 2), advertencia)


def matas_por_lote(matas_ha, area_efectiva_ha) -> int:
    return entero(Decimal(str(matas_ha)) * Decimal(str(area_efectiva_ha)))


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
    base = Decimal(ficha["base_plantas"])
    siembra = entero(n * (Decimal(ficha["costo_hoyado_cop"]) + Decimal(ficha["costo_colino_cop"])))
    insumos = entero(n * Decimal(ficha["insumo_anual_cop"]))
    jornales = redondear(n / base * (Decimal(str(ficha["jornales_limpieza_anio"])) + Decimal(str(ficha["jornales_riego_anio"]))), 1)
    return {"siembra_inicial_cop": siembra, "insumos_anuales_cop": insumos, "jornales_anuales": float(jornales)}
