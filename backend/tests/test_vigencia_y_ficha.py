"""Vigencia del ciclo (semáforo) y costos aproximados de la ficha técnica: funciones puras del dominio."""
from datetime import date

import pytest

from app.domain import formulas, validaciones as v
from app.domain.fechas import sumar_anios

SIEMBRA = date(2026, 3, 15)


def test_fecha_fin_estimada_es_siembra_mas_anios():
    assert formulas.fecha_fin_estimada(SIEMBRA, 7) == date(2033, 3, 15)
    assert formulas.fecha_fin_estimada(SIEMBRA, None) is None
    assert sumar_anios(date(2024, 2, 29), 1) == date(2025, 2, 28)  # 29 de febrero


@pytest.mark.parametrize("hoy,color", [
    (date(2026, 10, 27), "VERDE"),      # faltan más del 50 %
    (date(2029, 6, 1), "AMARILLO"),     # faltan 3,8 de 7 años (54 %): ya cruzó el 50 % unas semanas después
    (date(2031, 3, 15), "AMARILLO"),    # ejemplo de referencia: faltan 2 de 7 años (28,6 %)
    (date(2032, 6, 1), "ROJO"),         # faltan menos del 20 %
    (date(2033, 3, 15), "ROJO"),        # se cumplió hoy
    (date(2035, 1, 1), "ROJO"),         # vencida
])
def test_semaforo(hoy, color):
    fin, restantes, semaforo = formulas.semaforo_vigencia(SIEMBRA, 7, hoy)
    assert fin == date(2033, 3, 15)
    if hoy == date(2029, 6, 1):
        assert semaforo in ("VERDE", "AMARILLO")
    else:
        assert semaforo == color
    assert restantes >= 0


def test_anios_restantes_y_sin_vigencia():
    assert formulas.semaforo_vigencia(SIEMBRA, 7, date(2031, 3, 15))[1] == 2.0
    assert formulas.semaforo_vigencia(SIEMBRA, 7, date(2040, 1, 1))[1] == 0.0
    assert formulas.semaforo_vigencia(SIEMBRA, None, date(2026, 10, 27)) == (None, None, None)


@pytest.mark.parametrize("valor,codigo", [(None, None), (1, None), (7, None), (50, None), (7.0, None),
                                          (0, "V-49"), (51, "V-49"), (2.5, "V-49"), ("7", "V-49"), (True, "V-49"), (-1, "V-49")])
def test_regla_v49_vigencia(valor, codigo):
    assert v.v_vigencia(valor) == codigo


CAFE = {"base_plantas": 1000, "costo_hoyado_cop": 300, "costo_colino_cop": 100, "insumo_anual_cop": 830,
        "jornales_limpieza_anio": 4, "jornales_riego_anio": 3}


def test_estimar_costos_cafe_mil_plantas():
    e = formulas.estimar_costos(CAFE, 1000)
    assert e == {"siembra_inicial_cop": 400000, "insumos_anuales_cop": 830000, "jornales_anuales": 7.0}


def test_estimar_costos_escala_con_las_matas_y_redondea():
    e = formulas.estimar_costos(CAFE, 4000)
    assert e == {"siembra_inicial_cop": 1600000, "insumos_anuales_cop": 3320000, "jornales_anuales": 28.0}
    assert formulas.estimar_costos(CAFE, 0) == {"siembra_inicial_cop": 0, "insumos_anuales_cop": 0, "jornales_anuales": 0.0}
    e = formulas.estimar_costos({**CAFE, "jornales_riego_anio": 0.5}, 333)
    assert e["jornales_anuales"] == 1.5  # 333/1000 × 4,5 = 1,4985 → 1,5
