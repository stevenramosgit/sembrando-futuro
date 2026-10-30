"""Reglas V-xx del Apéndice J: un valor válido y uno inválido por regla (los mismos ejemplos de los documentos 14 y 18)."""
from datetime import date

import pytest

from app.core.mensajes import MENSAJES
from app.domain import validaciones as v

HOY = date(2026, 10, 27)

CASOS = [
    ("V-01", v.v_nombre, "María Pérez", "aaaaa"), ("V-01", v.v_nombre, "Ana", "0"), ("V-01", v.v_nombre, "Ana", "A"),
    ("V-02", v.v_ubicacion, "Caloto, Cauca", "0"), ("V-03", v.v_correo, "Maria@Correo.com", "0@0"),
    ("V-03", v.v_correo, "a.b@c.co", "sin-arroba"), ("V-09", v.v_codigo_otp, "482915", "48A"),
    ("V-22", v.v_nombre_lugar, "La Esperanza", "x"), ("V-24", v.v_area_bruta, 1.5, 0), ("V-24", v.v_area_bruta, 10000, 10000.1),
    ("V-25", v.v_pendiente, 12, 101), ("V-25", v.v_pendiente, 0, -1), ("V-33", v.v_distancia, 1.5, 0),
    ("V-33", v.v_distancia, 10, 10.01), ("V-35", v.v_valor_gasto, 50000000, 50000001), ("V-36", v.v_valor_gasto, 100, "100"),
    ("V-38", v.v_observaciones, "Abono orgánico", "Abono <b>"), ("V-39", v.v_jornales, 0.5, 0.3), ("V-39", v.v_jornales, 999, 1000),
    ("V-40", v.v_valor_jornal, 25000, 0), ("V-41", v.v_cantidad, 0.1, 0.09), ("V-42", v.v_precio, 1, 0),
]


@pytest.mark.parametrize("codigo,funcion,bueno,malo", CASOS)
def test_regla(codigo, funcion, bueno, malo):
    assert funcion(bueno) is None
    esperado = funcion(malo)
    assert esperado is not None
    if codigo != "V-36":  # V-35/V-36 comparten función
        assert esperado == codigo


def test_v36_texto_no_numerico():
    assert v.v_valor_gasto("abc") == "V-36" and v.v_valor_gasto(1.5) == "V-36" and v.v_valor_gasto(0) == "V-35"


@pytest.mark.parametrize("clave", ["Siembra#2026a", "Aa1!kLmPq9z", "Cafe#Cauca2026"])
def test_clave_valida(clave):
    assert v.v_clave(clave) is None


@pytest.mark.parametrize("clave", ["corta1A!", "sinmayuscula1!", "SINMINUSCULA1!", "SinNumero!!ab", "SinSimbolo123a",
                                   "Con espacio1A!", "Tildeé1A!!!!", "Aaaaa1!bcdef", "Abcdef1!ghij", "A" * 65 + "a1!"])
def test_clave_invalida(clave):
    assert v.v_clave(clave) == "V-07"


def test_clave_con_correo_o_nombre():
    assert v.v_clave("Maria.perez1!X", "maria.perez@correo.com", "") == "V-07"
    assert v.v_clave("Perez#Sembrar9", "x@y.com", "Luis Perez") == "V-07"


def test_fechas():
    assert v.v_siembra(date(2020, 1, 1), HOY) is None and v.v_siembra(date(2019, 12, 31), HOY) == "V-48"
    assert v.v_siembra(date(2027, 10, 27), HOY) is None and v.v_siembra(date(2027, 10, 28), HOY) == "V-48"
    assert v.v_cierre(HOY, date(2026, 1, 1), HOY) is None and v.v_cierre(date(2026, 10, 28), date(2026, 1, 1), HOY) == "V-29"
    assert v.v_fecha_registro(date(2026, 1, 1), date(2026, 1, 1), HOY) is None
    assert v.v_fecha_registro(date(2025, 12, 31), date(2026, 1, 1), HOY) == "V-47"


def test_todos_los_mensajes_existen():
    for n in range(1, 51):
        if n == 23:  # V-23 (nombre de lote repetido) se retiró al eliminar la tabla LOTE
            assert "V-23" not in MENSAJES
        else:
            assert f"V-{n:02d}" in MENSAJES
    for n in range(1, 12):
        assert f"E-{n:02d}" in MENSAJES
