"""Caja blanca (documento 22): 28 casos CB-01 a CB-28 que recorren los caminos básicos de las cuatro funciones del dominio.
Cada prueba verifica el resultado esperado y deja lo que observó en tests/resultados_plan.json."""
from app.core.mensajes import MENSAJES
from app.domain import acceso, formulas
from tests.conftest import obs

CAFE = (1.0, 2.0)


def msj(codigo):
    return f"«{MENSAJES[codigo]}»"


# ---------------------------------------------------------------- función 1: matas_por_hectarea (RF-18)
def densidad(marco, d1, d2=None, rango=CAFE):
    return formulas.matas_por_hectarea(marco, d1, d2, rango)


def test_CB_01():
    assert densidad(None, 1.5) == ("error", "V-32")
    obs("Camino 1-X32: marco sin elegir → ('error', 'V-32') " + msj("V-32"))


def test_CB_02():
    assert densidad("cuadrado", 0.0) == ("error", "V-33")
    obs("Camino 1-2-X33: d1 = 0,0 → ('error', 'V-33') " + msj("V-33"))


def test_CB_03():
    assert densidad("rectangular", 1.0, 0.0) == ("error", "V-33")
    obs("Camino 1-2-3-4-X33: rectangular con d2 = 0,0 → ('error', 'V-33') " + msj("V-33"))


def test_CB_04():
    r = densidad("rectangular", 1.0, 1.5, rango=None)
    assert r == ("ok", 6666.67, None)
    obs(f"Camino 1-2-3-4-5-9-10-13: rectangular 1,0 × 1,5 sin rango → {r}: 6.666,67 matas/ha sin advertencia")


def test_CB_05():
    r = densidad("cuadrado", 1.5)
    assert r == ("ok", 4444.45, None)
    obs(f"Camino 1-2-3-6-7-9-10-11-13: cuadrado 1,5 m dentro del rango → {r}: 4.444,45 matas/ha (hacia arriba) sin advertencia")


def test_CB_06():
    r = densidad("tresbolillo", 1.5)
    assert r == ("ok", 5132.01, None)
    obs(f"Camino 1-2-3-6-8-9-10-11-13: tresbolillo 1,5 m → {r}: 5.132,01 matas/ha (hacia arriba) sin advertencia")


def test_CB_07():
    r = densidad("cuadrado", 2.5)
    assert r == ("ok", 1600.0, "V-34")
    obs(f"Camino 1-2-3-6-7-9-10-11-12-13: cuadrado 2,5 m fuera del rango 1,0–2,0 → {r}: 1.600,00 matas/ha y advertencia V-34 (el cálculo no se bloquea)")


def test_CB_08():
    r = densidad("rectangular", 1.0, 1.5)
    assert r == ("ok", 6666.67, None)
    obs(f"Camino 1-2-3-4-5-9-10-11-13: rectangular 1,0 × 1,5 dentro del rango → {r}: 6.666,67 matas/ha sin advertencia")


# ---------------------------------------------------------------- función 2: iniciar_sesion (RF-03)
def cuenta(estado="ACTIVA", fallos=0, bloqueado_hasta=None):
    return {"clave": "Siembra#2026a", "estado": estado, "fallos": fallos, "bloqueado_hasta": bloqueado_hasta}


CORRECTA, MALA = "Siembra#2026a", "otra-clave"
AHORA = 100  # minutos


def test_CB_09():
    r = acceso.iniciar_sesion("", CORRECTA, cuenta(), AHORA)
    assert r == ("error", "V-16")
    obs("Camino 1-X16: correo vacío → ('error', 'V-16') " + msj("V-16"))


def test_CB_10():
    r = acceso.iniciar_sesion("maria@correo.com", "", cuenta(), AHORA)
    assert r == ("error", "V-16")
    obs("Camino 1-2-X16: clave vacía → ('error', 'V-16') " + msj("V-16"))


def test_CB_11():
    r = acceso.iniciar_sesion("nadie@correo.com", MALA, None, AHORA)
    assert r == ("error", "V-17")
    obs("Camino 1-2-3-X17: correo sin cuenta → ('error', 'V-17') " + msj("V-17"))


def test_CB_12():
    c = cuenta(bloqueado_hasta=AHORA + 5)
    r = acceso.iniciar_sesion("maria@correo.com", CORRECTA, c, AHORA)
    assert r == ("error", "V-18") and c["fallos"] == 0
    obs("Camino 1-2-3-4-5-X18: bloqueo vigente (faltan 5 min) con clave correcta → ('error', 'V-18'); no se cuenta el intento " + msj("V-18"))


def test_CB_13():
    c = cuenta(bloqueado_hasta=AHORA)  # el bloqueo de 15 min se registró hace 15 min
    r = acceso.iniciar_sesion("maria@correo.com", CORRECTA, c, AHORA)
    assert r == ("ok",) and c["bloqueado_hasta"] is None and c["fallos"] == 0
    obs("Camino 1-2-3-4-5-6-10-11-OK: bloqueo vencido (pasaron 15 min) con clave correcta → ('ok',); el bloqueo y los fallos quedan en cero")


def test_CB_14():
    c = cuenta(fallos=1)
    r = acceso.iniciar_sesion("maria@correo.com", MALA, c, AHORA)
    assert r == ("error", "V-17") and c["fallos"] == 2
    obs("Camino 1-2-3-4-6-7-8-X17: clave incorrecta con 1 fallo previo → ('error', 'V-17'); los fallos pasan de 1 a 2 " + msj("V-17"))


def test_CB_15():
    c = cuenta(fallos=4)
    r = acceso.iniciar_sesion("maria@correo.com", MALA, c, AHORA)
    assert r == ("error", "V-18") and c["bloqueado_hasta"] == AHORA + 15 and c["fallos"] == 0
    obs(f"Camino 1-2-3-4-6-7-8-9-X18: 5.º fallo → ('error', 'V-18'); bloqueo hasta el minuto {c['bloqueado_hasta']} (15 min) y fallos reiniciados " + msj("V-18"))


def test_CB_16():
    r = acceso.iniciar_sesion("maria@correo.com", CORRECTA, cuenta(estado="PENDIENTE"), AHORA)
    assert r == ("error", "V-19")
    obs("Camino 1-2-3-4-6-10-X19: clave correcta con cuenta PENDIENTE → ('error', 'V-19') " + msj("V-19"))


def test_CB_17():
    r = acceso.iniciar_sesion("maria@correo.com", CORRECTA, cuenta(), AHORA)
    assert r == ("ok",)
    obs("Camino 1-2-3-4-6-10-11-OK: clave correcta con cuenta ACTIVA sin bloqueo → ('ok',) (el servicio emite el token de sesión de 12 horas)")


# ---------------------------------------------------------------- función 3: verificar_codigo (RF-02)
def codigo(intentos=0, min_envio=1, h_cuenta=1):
    return {"codigo": "482915", "intentos": intentos, "min_envio": min_envio, "h_cuenta": h_cuenta}


def test_CB_18():
    r = acceso.verificar_codigo("482915", codigo(h_cuenta=25))
    assert r == ("error", "V-15")
    obs("Camino 1-X15: cuenta pendiente de 25 h → ('error', 'V-15') " + msj("V-15"))


def test_CB_19():
    r = acceso.verificar_codigo("48A", codigo())
    assert r == ("error", "V-09")
    obs("Camino 1-2-X09: código «48A» → ('error', 'V-09') " + msj("V-09"))


def test_CB_20():
    r = acceso.verificar_codigo("482915", codigo(intentos=5))
    assert r == ("error", "V-12")
    obs("Camino 1-2-3-X12: código ya invalidado (5 intentos previos), aunque sea el correcto → ('error', 'V-12') " + msj("V-12"))


def test_CB_21():
    r = acceso.verificar_codigo("482915", codigo(min_envio=15.02))
    assert r == ("error", "V-11")
    obs("Camino 1-2-3-4-X11: código enviado hace 15 min 01 s → ('error', 'V-11') " + msj("V-11"))


def test_CB_22():
    o = codigo(intentos=1)
    r = acceso.verificar_codigo("111111", o)
    assert r == ("error", "V-10", 3) and o["intentos"] == 2
    obs("Camino 1-2-3-4-5-6-7-X10: código incorrecto con 1 intento previo → ('error', 'V-10', 3): quedan 3 intentos " + msj("V-10"))


def test_CB_23():
    o = codigo(intentos=4)
    r = acceso.verificar_codigo("111111", o)
    assert r == ("error", "V-12") and o["intentos"] == 5
    obs("Camino 1-2-3-4-5-6-7-8-X12: 5.º fallo → ('error', 'V-12'); el código queda invalidado " + msj("V-12"))


def test_CB_24():
    r = acceso.verificar_codigo("482915", codigo(min_envio=14.98, h_cuenta=23))
    assert r == ("ok",)
    obs("Camino 1-2-3-4-5-9-OK: código correcto a los 14 min 59 s con la cuenta de 23 h → ('ok',): la cuenta pasa a ACTIVA")


# ---------------------------------------------------------------- función 4: calcular_utilidad (RF-28)
def test_CB_25():
    r = formulas.calcular_utilidad([], [], 0.9)
    assert r == ("ok", 0, 0, 0, 0.0, 0)
    obs(f"Camino 1-3-5-6-7-9-10 (bucles sin vueltas): sin movimientos → {r}: todo en $ 0 y rentabilidad 0,0 %")


def test_CB_26():
    r = formulas.calcular_utilidad([], [500000], 0.9)
    assert r == ("ok", 0, 500000, 500000, 0.0, 555556)
    obs(f"Camino 1-3-4-3-5-6-7-9-10: solo ingresos → {r}: utilidad $ 500.000, rentabilidad 0,0 %, por hectárea $ 555.556")


def test_CB_27():
    r = formulas.calcular_utilidad([100000, 30000, 20000], [500000], 0.9)
    assert r == ("ok", 150000, 500000, 350000, 233.3, 388889)
    obs(f"Camino 1-2-1-2-1-2-1-3-4-3-5-6-8-9-10: ciclo C-01 (3 gastos y 1 ingreso) → {r}: utilidad $ 350.000, rentabilidad 233,3 %, por hectárea $ 388.889")


def test_CB_28():
    r = formulas.calcular_utilidad([120000, 80000], [50000], 0.9)
    assert r == ("ok", 200000, 50000, -150000, -75.0, -166667)
    obs(f"Camino 1-2-1-2-1-3-4-3-5-6-8-9-10: pérdida → {r}: utilidad −$ 150.000, rentabilidad −75,0 %, por hectárea −$ 166.667")
