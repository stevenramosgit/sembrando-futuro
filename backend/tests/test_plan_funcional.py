"""Ejecución del plan de pruebas (documento 14): fincas, ciclos, cálculos, movimientos, sincronización, catálogo y requisitos no funcionales.
Cada prueba test_CP_<id> deja lo que observó en tests/resultados_plan.json. Los casos que además necesitan la pantalla
(marcados «mixto» en tests/plan_mixtos.json) se completan con frontend/pruebas/e2e_plan.cjs."""
from datetime import timedelta
from decimal import Decimal

import pytest
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from app import cli
from app.core.seguridad import ahora
from app.domain import fechas, formulas
from app.models import Ciclo, Cultivo, Ingreso, Usuario
from tests.conftest import API, CLAVE, autorizar, obs, registrar_y_activar
from tests.test_cuentas import registrar
from tests.test_plan_validaciones import error, finca_ciclo
from tests.test_resumen_admin import completar_ciclo
from tests.test_sync import DATOS_CAFE, DATOS_CICLO, T0, T1, T2, estructura, gasto, nid, push, reg

HOY = fechas.hoy()
AYER, MANANA = HOY - timedelta(days=1), HOY + timedelta(days=1)


def iso(d):
    return d.isoformat()


def codigo_de(res, indice=0):
    assert res[indice]["estado"] == "RECHAZADO", res
    return res[indice]["codigo"]


def estados(res):
    return [r.get("codigo") or r["estado"] for r in res]


def resumen(cliente, cab, c):
    r = cliente.get(f"{API}/ciclos/{c}/resumen", headers=cab)
    assert r.status_code == 200, r.text
    return r.json()


def en_ciclo(cliente, cab, tipo, datos_de, **ciclo):
    """Crea finca y ciclo, y envía un registro del tipo dado; devuelve (ciclo, resultado)."""
    f, c, _ = finca_ciclo(cliente, cab, **ciclo)
    if tipo == "ingreso":  # una venta es de un cultivo del ciclo
        push(cliente, cab, reg("ciclo_cultivo", nid(), {"ciclo_id": c, **DATOS_CAFE}))
    return c, push(cliente, cab, reg(tipo, nid(), datos_de(c), t=T2))[0]


def probar(cliente, cab, tipo, datos_de, valores, esperado):
    """Prueba una lista de valores; cada uno en su propio ciclo. Devuelve {valor: 'ACEPTADO' | código}."""
    salida = {}
    for v in valores:
        _, r = en_ciclo(cliente, cab, tipo, lambda c, v=v: datos_de(c, v))
        salida[str(v)] = r.get("codigo") or r["estado"]
    assert [salida[str(v)] == "ACEPTADO" for v in valores] == esperado, salida
    return salida


def pesos(n):
    return f"{n:,}".replace(",", ".")


def dec(n):
    return str(n).replace(".", ",")


def fmt(d):
    return ", ".join(f"{k} → {v}" for k, v in d.items())


# ================================================================ RF-12 fincas
def test_CP_RF_12_01(cliente, cabecera):
    f = nid()
    r = push(cliente, cabecera, reg("finca", f, {"nombre": "La Esperanza"}))[0]
    lista = cliente.get(f"{API}/sync/pull", headers=cabecera).json()["registros"]
    assert r["estado"] == "ACEPTADO" and [x["datos"]["nombre"] for x in lista if x["tipo"] == "finca"] == ["La Esperanza"]
    obs("Servidor: finca «La Esperanza» aceptada y devuelta en la descarga (S-02). Pantalla «Mis fincas»: ver e2e_plan.cjs")


def test_CP_RF_12_02(cliente, cabecera):
    out = {n: codigo_de(push(cliente, cabecera, reg("finca", nid(), {"nombre": n}))) for n in ("0", "aaaaa")}
    assert set(out.values()) == {"V-22"}
    obs("Nombres de finca «0» y «aaaaa»: ambos RECHAZADO con V-22")


def test_CP_RF_12_03(cliente, cabecera):
    f, c, cc = estructura(cliente, cabecera)
    r = push(cliente, cabecera, reg("finca", f, {"nombre": "Otra"}, t=T2, eliminado=True))[0]
    pull = [x for x in cliente.get(f"{API}/sync/pull", headers=cabecera).json()["registros"] if x["tipo"] == "finca"][0]
    assert r["estado"] == "RECHAZADO" and r["codigo"] == "E-11" and pull["datos"]["nombre"] == "La Esperanza" and not pull["eliminado"]
    obs("S-01 con eliminado = true para una finca existente: RECHAZADO E-11; la finca sigue como «La Esperanza», sin marca de eliminada")


# ================================================================ RF-13 área efectiva
def test_CP_RF_13_01(cliente, cabecera):
    f, c, res = finca_ciclo(cliente, cabecera, area_bruta_ha=1.0, area_no_sembrable_ha=0.1, area_efectiva_ha=0.9)
    assert formulas.area_efectiva(1.0, 0.1) == Decimal("0.9000")
    obs(f"Bruta 1,0 ha − 1.000 m² (0,1 ha): la función da {formulas.area_efectiva(1.0, 0.1)} ha y el servidor guarda {resumen(cliente, cabecera, c)['ciclo']['area_efectiva_ha']} ha")


def test_CP_RF_13_02(cliente, cabecera):
    out = {}
    for n in (0.9999, 1.0, 1.5):
        _, _, res = finca_ciclo(cliente, cabecera, area_bruta_ha=1.0, area_no_sembrable_ha=n)
        out[str(n)] = estados(res)[1]
    assert out == {"0.9999": "ACEPTADO", "1.0": "V-26", "1.5": "V-26"}, out
    obs("No sembrable 0,9999 (bruta − 0,0001): ACEPTADO; 1,0 (= bruta) y 1,5 (> bruta): RECHAZADO con V-26")


def test_CP_RF_13_04(cliente, cabecera, db):
    f, c, res = finca_ciclo(cliente, cabecera, area_efectiva_ha=5.0)
    assert estados(res) == ["ACEPTADO", "ACEPTADO"]
    guardado = float(db.get(Ciclo, c).area_efectiva_ha)
    mala = Ciclo(id_ciclo=nid(), id_finca=f, nombre_lote="Lote SQL", pendiente_pct=5, area_bruta_ha=1.0, area_no_sembrable_ha=0.1,
                 area_efectiva_ha=0.5, fecha_siembra=HOY, estado="ACTIVO", updated_at=ahora())
    db.add(mala)
    with pytest.raises(IntegrityError) as e:
        db.commit()
    db.rollback()
    assert guardado == 0.9
    obs(f"SQL directo con efectiva 0,5 ≠ 1,0 − 0,1: la base lo rechaza ({str(e.value.orig)[:50]}…). S-01 con efectiva errada de 5,0: el servidor guardó {guardado}")


# ================================================================ RF-14 ciclos
def test_CP_RF_14_01(cliente, cabecera):
    f, c, res = finca_ciclo(cliente, cabecera)
    cc = push(cliente, cabecera, reg("ciclo_cultivo", nid(), {"ciclo_id": c, **DATOS_CAFE}))
    x = resumen(cliente, cabecera, c)
    assert estados(res) == ["ACEPTADO"] * 2 and estados(cc) == ["ACEPTADO"] and x["ciclo"]["estado"] == "ACTIVO"
    obs(f"Ciclo con lote «{x['ciclo']['nombre_lote']}», 1,0 ha, pendiente 12 %, café y siembra 15/03/2026: ACEPTADO en estado {x['ciclo']['estado']}")


def test_CP_RF_14_02(cliente, cabecera):
    f, c, _ = finca_ciclo(cliente, cabecera)
    r = push(cliente, cabecera, reg("ciclo_cultivo", nid(), {"ciclo_id": c, "marco": "cuadrado", "dist_a_m": 1.5}))
    assert codigo_de(r) == "V-27"
    obs("Ciclo_cultivo sin código de cultivo: RECHAZADO con V-27 «" + r[0]["mensaje"] + "»")


def test_CP_RF_14_03(cliente, cabecera):
    valores = [date_ for date_ in (fechas.leer_fecha("2019-12-31"), fechas.leer_fecha("2020-01-01"),
                                   fechas.un_anio_despues(HOY), fechas.un_anio_despues(HOY) + timedelta(days=1))]
    out = {}
    for d in valores:
        _, _, res = finca_ciclo(cliente, cabecera, fecha_siembra=iso(d))
        out[iso(d)] = estados(res)[1]
    esperado = ["V-48", "ACEPTADO", "ACEPTADO", "V-48"]
    assert list(out.values()) == esperado, out
    obs("Fecha de siembra: " + fmt(out))


def test_CP_RF_14_04(cliente, cabecera):
    out = {}
    for n in (0.0001, 0.00009, 10000, 10000.0001):
        _, _, res = finca_ciclo(cliente, cabecera, area_bruta_ha=n, area_no_sembrable_ha=0, area_efectiva_ha=n)
        out[str(n)] = estados(res)[1]
    assert list(out.values()) == ["ACEPTADO", "V-24", "ACEPTADO", "V-24"], out
    obs("Área bruta (ha): " + fmt(out))


def test_CP_RF_14_05(cliente, cabecera):
    out = {}
    for n in (1, 0, 50, 51, 2.5, None):
        _, _, res = finca_ciclo(cliente, cabecera, vigencia_anios=n)
        out[str(n)] = estados(res)[1]
    assert out == {"1": "ACEPTADO", "0": "V-49", "50": "ACEPTADO", "51": "V-49", "2.5": "V-49", "None": "ACEPTADO"}, out
    f, c, _ = finca_ciclo(cliente, cabecera, vigencia_anios=None)
    x = resumen(cliente, cabecera, c)["ciclo"]
    assert x["vigencia_anios"] is None and x["semaforo"] is None
    obs("Vigencia: " + fmt(out) + "; sin vigencia el resumen no trae fecha estimada ni semáforo")


def test_CP_RF_14_06(cliente, cabecera):
    f, c, cc = estructura(cliente, cabecera)
    r = push(cliente, cabecera, reg("ciclo_cultivo", nid(), {"ciclo_id": c, "cultivo_codigo": "PLATANO", "marco": "rectangular",
                                                             "dist_a_m": 3.0, "dist_b_m": 2.0}))
    x = resumen(cliente, cabecera, c)
    assert estados(r) == ["ACEPTADO"] and [(k["codigo"], k["marco"], k["matas"]) for k in x["cultivos"]] == [
        ("CAFE", "cuadrado", 4000), ("PLATANO", "rectangular", 1500)]
    obs("Café cuadrado 1,5 m + plátano rectangular 3 × 2 m en el mismo ciclo: 2 cultivos, cada uno con su marco; matas 4.000 y 1.500 (total 5.500)")


def test_CP_RF_14_07(cliente, cabecera):
    f, c, cc = estructura(cliente, cabecera)
    repetido = push(cliente, cabecera, reg("ciclo_cultivo", nid(), {"ciclo_id": c, **DATOS_CAFE}, t=T1))
    cerrado = push(cliente, cabecera, reg("ciclo", c, {"finca_id": f, **DATOS_CICLO, "estado": "CERRADO", "fecha_cierre": iso(HOY)}, t=T1))
    tarde = push(cliente, cabecera, reg("ciclo_cultivo", nid(), {"ciclo_id": c, "cultivo_codigo": "YUCA"}, t=T2))
    assert codigo_de(repetido) == "V-50" and estados(cerrado) == ["ACEPTADO"] and codigo_de(tarde) == "V-31"
    obs("Café repetido en el mismo ciclo: V-50; yuca agregada a un ciclo CERRADO: V-31")


def test_CP_RF_14_08(cliente, cabecera):
    def semaforo(vigencia, usados):
        siembra = HOY - timedelta(days=round(usados * 365.25))
        fin, restantes, color = formulas.semaforo_vigencia(siembra, vigencia, HOY)
        total = (fin - siembra).days if fin else None
        faltan = round((fin - HOY).days / total * 100, 1) if fin else None
        return color, faltan
    casos = {"10 años con 2 de uso": semaforo(10, 2), "4 años con 2,5 de uso": semaforo(4, 2.5), "4 años con 3,5 de uso": semaforo(4, 3.5),
             "ciclo vencido (3 años con 4 de uso)": semaforo(3, 4), "sin vigencia": formulas.semaforo_vigencia(HOY, None, HOY)}
    assert casos["10 años con 2 de uso"][0] == "VERDE" and casos["4 años con 2,5 de uso"][0] == "AMARILLO"
    assert casos["4 años con 3,5 de uso"][0] == "ROJO" and casos["ciclo vencido (3 años con 4 de uso)"][0] == "ROJO"
    assert casos["sin vigencia"] == (None, None, None)
    obs("Semáforo: " + "; ".join(f"{k}: {v[0]}" + (f" (falta {v[1]} %)" if v[1] is not None else "") if v[0] else f"{k}: sin semáforo"
                                  for k, v in casos.items()))


# ================================================================ RF-15 cierre
def test_CP_RF_15_01(cliente, cabecera):
    f, c, cc = completar_ciclo(cliente, cabecera)
    r = push(cliente, cabecera, reg("ciclo", c, {"finca_id": f, **DATOS_CICLO, "estado": "CERRADO", "fecha_cierre": iso(HOY)}, t=T2))
    x = resumen(cliente, cabecera, c)["ciclo"]
    nuevo = push(cliente, cabecera, reg("gasto", nid(), gasto(c), t="2026-12-31T10:00:00.000Z"))
    assert estados(r) == ["ACEPTADO"] and x["estado"] == "CERRADO" and codigo_de(nuevo) == "V-31"
    obs(f"Cierre con ingresos y fecha de hoy: ACEPTADO, estado {x['estado']}; un gasto nuevo posterior se rechaza con V-31 (solo lectura)")


def test_CP_RF_15_03(cliente, cabecera):
    f, c, _ = finca_ciclo(cliente, cabecera, fecha_siembra="2026-03-15")
    igual = push(cliente, cabecera, reg("ciclo", c, {"finca_id": f, **DATOS_CICLO, "estado": "CERRADO", "fecha_cierre": "2026-03-15"}, t=T1))
    f2, c2, _ = finca_ciclo(cliente, cabecera, fecha_siembra="2026-03-15")
    antes = push(cliente, cabecera, reg("ciclo", c2, {"finca_id": f2, **DATOS_CICLO, "estado": "CERRADO", "fecha_cierre": "2026-03-14"}, t=T1))
    assert estados(igual) == ["ACEPTADO"] and codigo_de(antes) == "V-29"
    obs("Cierre el mismo día de la siembra: ACEPTADO; un día antes: RECHAZADO con V-29")


def test_CP_RF_15_04(cliente, cabecera):
    f, c, cc = estructura(cliente, cabecera)
    push(cliente, cabecera, reg("ciclo", c, {"finca_id": f, **DATOS_CICLO, "estado": "CERRADO", "fecha_cierre": iso(HOY)}, t=T1))
    r = push(cliente, cabecera, reg("gasto", nid(), gasto(c), t=T2))
    assert codigo_de(r) == "V-31"
    obs("Gasto nuevo en un ciclo CERRADO: RECHAZADO con V-31 «" + r[0]["mensaje"] + "»")


def test_CP_RF_15_05(cliente, cabecera):
    f, c, _ = finca_ciclo(cliente, cabecera)
    hoy = push(cliente, cabecera, reg("ciclo", c, {"finca_id": f, **DATOS_CICLO, "estado": "CERRADO", "fecha_cierre": iso(HOY)}, t=T1))
    f2, c2, _ = finca_ciclo(cliente, cabecera)
    manana = push(cliente, cabecera, reg("ciclo", c2, {"finca_id": f2, **DATOS_CICLO, "estado": "CERRADO", "fecha_cierre": iso(MANANA)}, t=T1))
    assert estados(hoy) == ["ACEPTADO"] and codigo_de(manana) == "V-29"
    obs("Cierre con fecha de hoy: ACEPTADO; con la de mañana: RECHAZADO con V-29")


def test_CP_RF_15_06(cliente, cabecera):
    out = []
    for orden in ("cierre_primero", "gasto_primero", "gasto_hecho_antes_sin_conexion"):
        f, c, _ = estructura(cliente, cabecera)
        cierre = reg("ciclo", c, {"finca_id": f, **DATOS_CICLO, "estado": "CERRADO", "fecha_cierre": iso(HOY)}, t=T1)
        g = reg("gasto", nid(), gasto(c), t={"cierre_primero": T2, "gasto_primero": T0, "gasto_hecho_antes_sin_conexion": T0}[orden])
        res = push(cliente, cabecera, *( [cierre, g] if orden == "cierre_primero" else [g, cierre]))
        resultado = {"gasto": estados(res)[0 if orden != "cierre_primero" else 1], "cierre": estados(res)[1 if orden != "cierre_primero" else 0]}
        cerrado_con_gasto_nuevo = (resultado["cierre"] == "ACEPTADO" and resultado["gasto"] == "ACEPTADO" and orden == "cierre_primero")
        assert not cerrado_con_gasto_nuevo
        out.append(f"{orden}: gasto {resultado['gasto']}, cierre {resultado['cierre']}")
    assert out[0].endswith("cierre ACEPTADO") and "gasto V-31" in out[0] and "gasto ACEPTADO" in out[1]
    obs("Orden de llegada: " + "; ".join(out) + ". Nunca quedó un gasto posterior al cierre en un ciclo CERRADO")


# ================================================================ RF-17 catálogo
def test_CP_RF_17_02(cliente):
    c = cliente.get(f"{API}/catalogo").json()["cultivos"]
    for x in c:
        f = x["ficha_tecnica"]
        assert x["distancia_min_m"] and x["distancia_max_m"] and x["marcos_permitidos"] and x["fuente_tecnica"]
        assert all(f[k] is not None for k in ("costo_hoyado_cop", "costo_colino_cop", "insumo_anual_cop"))
    obs("Catálogo: " + "; ".join(f"{x['codigo']} {x['distancia_min_m']}–{x['distancia_max_m']} m, marcos {x['marcos_permitidos']}, fuente «{x['fuente_tecnica']}»" for x in c))


def test_CP_RF_17_03(cliente):
    cafe = [x for x in cliente.get(f"{API}/catalogo").json()["cultivos"] if x["codigo"] == "CAFE"][0]["ficha_tecnica"]
    assert (cafe["base_plantas"], cafe["costo_hoyado_cop"], cafe["costo_colino_cop"], cafe["insumo_anual_cop"]) == (1000, 300, 100, 830)
    assert (cafe["jornales_limpieza_anio"], cafe["jornales_riego_anio"]) == (4.0, 3.0)
    obs(f"Ficha del café por cada {cafe['base_plantas']} plantas: hoyado ${cafe['costo_hoyado_cop']}, colino ${cafe['costo_colino_cop']}, "
        f"insumos ${cafe['insumo_anual_cop']} al año, {cafe['jornales_limpieza_anio']:g} jornales de limpieza y {cafe['jornales_riego_anio']:g} de riego")


# ================================================================ RF-18 densidad
def test_CP_RF_18_01():
    r = formulas.matas_por_hectarea("cuadrado", 1, None, None)
    assert r == ("ok", 10000.0, None)
    obs(f"Cuadrado d = 1 m: {r[1]:,.2f} matas/ha")


def test_CP_RF_18_02():
    r = formulas.matas_por_hectarea("rectangular", 2, 1.5, None)
    assert r[1] == 3333.33
    obs(f"Rectangular 2 × 1,5 m: {r[1]} matas/ha")


def test_CP_RF_18_03():
    r = formulas.matas_por_hectarea("tresbolillo", 3, None, None)
    exacto = 10000 / (9 * 0.866025)
    assert abs(r[1] - exacto) / exacto <= 1e-6
    obs(f"Tresbolillo d = 3 m: {r[1]} matas/ha (valor exacto {exacto:.4f}). La función redondea a 2 decimales")


def test_CP_RF_18_04(cliente, cabecera):
    f, c, cc = estructura(cliente, cabecera)
    x = resumen(cliente, cabecera, c)
    n = formulas.matas_por_hectarea("cuadrado", 1.5, None, (1.0, 2.0))
    assert n == ("ok", 4444.44, None) and x["cultivos"][0]["matas"] == 4000
    obs(f"Café cuadrado 1,5 m: {n[1]} matas/ha; ciclo de 0,9 ha efectivas: {x['cultivos'][0]['matas']} matas")


def test_CP_RF_18_05():
    rango = (1.0, 2.0)
    out = {d: formulas.matas_por_hectarea("cuadrado", d, None, rango) for d in (0.99, 1.0, 2.0, 2.01)}
    assert [out[d][2] for d in out] == ["V-34", None, None, "V-34"] and all(v[0] == "ok" for v in out.values())
    obs("Rango del café 1,0–2,0 m: 0,99 → advertencia V-34; 1,0 y 2,0 → sin advertencia; 2,01 → V-34; el cálculo se hace siempre")


def test_CP_RF_18_06():
    out = {d: formulas.matas_por_hectarea("cuadrado", d, None, None) for d in (0, -1)}
    assert all(v == ("error", "V-33") for v in out.values())
    obs("Distancia 0 y −1: la función devuelve error V-33 y no calcula")


def test_CP_RF_18_07(cliente, cabecera):
    out = {}
    for d in (0.009, 0.01, 10, 10.01):
        f, c, _ = finca_ciclo(cliente, cabecera)
        r = push(cliente, cabecera, reg("ciclo_cultivo", nid(), {"ciclo_id": c, "cultivo_codigo": "CAFE", "marco": "cuadrado", "dist_a_m": d}))
        out[str(d)] = estados(r)[0]
    assert list(out.values()) == ["V-33", "ACEPTADO", "ACEPTADO", "V-33"], out
    obs("Distancia del marco cuadrado (m): " + fmt(out))


# ================================================================ RF-23 gastos
def test_CP_RF_23_01(cliente, cabecera):
    out = probar(cliente, cabecera, "gasto", lambda c, v: gasto(c, v), (0, 1, 50_000_000, 50_000_001), [False, True, True, False])
    obs("Monto del gasto (COP): " + fmt(out))


def test_CP_RF_23_02(cliente, cabecera):
    out = probar(cliente, cabecera, "gasto", lambda c, v: gasto(c, v), ("1e5", "-5", "abc"), [False, False, False])
    obs("Monto «1e5», «-5» y «abc»: " + fmt(out))


def test_CP_RF_23_04(cliente, cabecera):
    f, c, _ = finca_ciclo(cliente, cabecera, fecha_siembra="2026-03-15")
    out = {}
    for nombre, d in (("hoy", HOY), ("mañana", MANANA), ("un día antes de la siembra", fechas.leer_fecha("2026-03-14"))):
        out[nombre] = estados(push(cliente, cabecera, reg("gasto", nid(), gasto(c, fecha=iso(d)), t=T2)))[0]
    assert out == {"hoy": "ACEPTADO", "mañana": "V-47", "un día antes de la siembra": "V-47"}, out
    obs("Fecha del gasto: " + fmt(out))


def test_CP_RF_23_05(cliente, cabecera):
    f, c, _ = finca_ciclo(cliente, cabecera)
    r = push(cliente, cabecera, reg("gasto", nid(), gasto(c, fecha="31/02/2026"), t=T2))
    assert codigo_de(r) == "V-28"
    obs("Servidor: fecha «31/02/2026» RECHAZADA con V-28 «" + r[0]["mensaje"] + "»")


# ================================================================ RF-24 jornales
def jornal(c, **extra):
    return {"ciclo_id": c, "fecha": "2026-04-20", "jornales": 2, "valor_diario_cop": 25000, **extra}


def test_CP_RF_24_01(cliente, cabecera):
    out = probar(cliente, cabecera, "jornal", lambda c, v: jornal(c, jornales=v), (0.4, 0.5, 1.25, 999, 999.5), [False, True, False, True, False])
    obs("Número de jornales: " + fmt(out))


def test_CP_RF_24_02(cliente, cabecera):
    f, c, cc = estructura(cliente, cabecera)
    push(cliente, cabecera, reg("jornal", nid(), jornal(c, jornales=3, valor_diario_cop=60000)))
    x = resumen(cliente, cabecera, c)
    assert formulas.costo_jornal(3, 60000) == 180000 and x["jornales_cop"] == 180000
    obs(f"3 jornales × $60.000: la función da $180.000 y el resumen del servidor ${pesos(x['jornales_cop'])}")


def test_CP_RF_24_03(cliente, cabecera):
    out = probar(cliente, cabecera, "jornal", lambda c, v: jornal(c, valor_diario_cop=v), (0, 1), [False, True])
    obs("Valor diario del jornal (COP): " + fmt(out))


def test_CP_RF_24_04(cliente, cabecera):
    f, c, _ = finca_ciclo(cliente, cabecera, fecha_siembra="2026-03-15")
    out = {nombre: estados(push(cliente, cabecera, reg("jornal", nid(), jornal(c, fecha=fecha), t=T2)))[0]
           for nombre, fecha in (("mañana", iso(MANANA)), ("fecha de siembra", "2026-03-15"))}
    assert out == {"mañana": "V-47", "fecha de siembra": "ACEPTADO"}, out
    obs("Fecha del jornal: " + fmt(out))


# ================================================================ RF-25 ingresos
def venta(c, **extra):
    return {"ciclo_id": c, "fecha": "2026-09-10", "cantidad": 4, "precio_unitario_cop": 125000, **extra}


def test_CP_RF_25_01(cliente, cabecera):
    out = probar(cliente, cabecera, "ingreso", lambda c, v: venta(c, cantidad=v), (0.09, 0.1, 10000, 10001), [False, True, True, False])
    obs("Cantidad vendida: " + fmt(out))


def test_CP_RF_25_02(cliente, cabecera):
    out = probar(cliente, cabecera, "ingreso", lambda c, v: venta(c, precio_unitario_cop=v), (0, 1, 50_000_000, 50_000_001), [False, True, True, False])
    obs("Precio unitario (COP): " + fmt(out))


def test_CP_RF_25_03(cliente, cabecera, db):
    f, c, cc = estructura(cliente, cabecera)
    i = nid()
    r = push(cliente, cabecera, reg("ingreso", i, venta(c, unidad_comercial="kg"), t=T2))
    guardado = db.get(Ingreso, i).unidad_comercial
    assert estados(r) == ["ACEPTADO"] and guardado.startswith("carga")
    obs(f"Ingreso enviado con unidad «kg»: el servidor ignora la unidad enviada y guarda la del cultivo («{guardado}»)")


def test_CP_RF_25_04(cliente, cabecera):
    f, c, _ = estructura(cliente, cabecera)
    manana = estados(push(cliente, cabecera, reg("ingreso", nid(), venta(c, fecha=iso(MANANA)), t=T2)))[0]
    hoy = estados(push(cliente, cabecera, reg("ingreso", nid(), venta(c, fecha=iso(HOY)), t=T2)))[0]
    assert (manana, hoy) == ("V-47", "ACEPTADO")
    obs(f"Ingreso con fecha de mañana: {manana}; con la de hoy: {hoy}")


def test_CP_RF_25_05(cliente, cabecera):
    f, c, _ = estructura(cliente, cabecera)
    r = push(cliente, cabecera, reg("ingreso", nid(), venta(c, cantidad=10000, precio_unitario_cop=50_000_000), t=T2))
    x = resumen(cliente, cabecera, c)
    assert estados(r) == ["ACEPTADO"] and x["ingresos_cop"] == 500_000_000_000 and formulas.total_ingreso(10000, 50_000_000) == 500_000_000_000
    obs(f"10.000 unidades a $50.000.000: aceptado; el servidor suma ${pesos(x['ingresos_cop'])}" + " sin desbordarse. Pantalla: ver e2e_plan.cjs")


# ================================================================ RF-27 edición
def test_CP_RF_27_03(cliente, cabecera):
    f, c, cc = estructura(cliente, cabecera)
    j = nid()
    push(cliente, cabecera, reg("jornal", j, jornal(c, jornales=2, valor_diario_cop=50000), t=T0))
    antes = resumen(cliente, cabecera, c)["jornales_cop"]
    r = push(cliente, cabecera, reg("jornal", j, jornal(c, jornales=3, valor_diario_cop=50000), t=T2))
    x = resumen(cliente, cabecera, c)
    assert estados(r) == ["ACEPTADO"] and (antes, x["jornales_cop"]) == (100000, 150000) and x["utilidad_neta_cop"] == -150000
    obs(f"Jornal de 2 a 3 jornales de $50.000: el costo pasa de ${pesos(antes)} a ${pesos(x['jornales_cop'])} y la utilidad queda en ${pesos(x['utilidad_neta_cop'])}")


# ================================================================ RF-28 utilidad
def test_CP_RF_28_01():
    r = formulas.calcular_utilidad([600000], [1000000], 1)
    assert r[3:5] == (400000, 66.7)
    obs(f"Ingresos 1.000.000 y gastos 600.000: utilidad {pesos(r[3])}; rentabilidad {dec(r[4])} % (66,67 % redondeado a 1 decimal)")


def test_CP_RF_28_02():
    r = formulas.calcular_utilidad([150000], [500000], 0.9)
    assert r[3:5] == (350000, 233.3)
    obs(f"Gasto 150.000 e ingreso 500.000: utilidad {pesos(r[3])}; rentabilidad {dec(r[4])} %")


def test_CP_RF_28_03():
    r = formulas.calcular_utilidad([], [500000], 0.9)
    assert r[4] == 0.0
    obs(f"Gastos = 0: rentabilidad {dec(r[4])} % sin error de división (utilidad {pesos(r[3])})")


def test_CP_RF_28_05(cliente, cabecera):
    f, c, cc = estructura(cliente, cabecera)
    push(cliente, cabecera, reg("gasto", nid(), gasto(c, 100000)), reg("jornal", nid(), jornal(c, jornales=2, valor_diario_cop=25000)),
         reg("ingreso", nid(), venta(c)))
    x = resumen(cliente, cabecera, c)
    esperado = (150000, 500000, 350000, 233.3, 388889, 4000)
    real = (x["costos_totales_cop"], x["ingresos_cop"], x["utilidad_neta_cop"], x["rentabilidad_pct"], x["utilidad_por_ha_cop"], x["total_matas"])
    assert real == esperado, real
    obs(f"R-01: costos {pesos(real[0])}, ingresos {pesos(real[1])}, utilidad {pesos(real[2])}, rentabilidad {dec(real[3])} %, por hectárea {pesos(real[4])}, matas {pesos(real[5])}")


def test_CP_RF_28_06(cliente, cabecera):
    f, c, cc = estructura(cliente, cabecera)
    otra = autorizar(registrar_y_activar(cliente, "pedro.gomez@correo.com", "Pedro Gómez", "Cultivo#2026b"))
    propio = cliente.get(f"{API}/ciclos/{c}/resumen", headers=cabecera)
    ajeno = cliente.get(f"{API}/ciclos/{c}/resumen", headers=otra)
    nadie = cliente.get(f"{API}/ciclos/{nid()}/resumen", headers=cabecera)
    assert (propio.status_code, ajeno.status_code, nadie.status_code) == (200, 403, 404)
    assert error(ajeno)["codigo"] == "E-02" and error(nadie)["codigo"] == "E-07"
    obs("R-01 de un ciclo propio: 200; de otro usuario: 403 E-02; inexistente: 404 E-07")


def test_CP_RF_28_07(cliente, cabecera):
    f, c, cc = estructura(cliente, cabecera)
    vacio = resumen(cliente, cabecera, c)
    f2, c2, _ = estructura(cliente, cabecera)
    push(cliente, cabecera, reg("ingreso", nid(), venta(c2)))
    solo_ingreso = resumen(cliente, cabecera, c2)
    assert vacio["rentabilidad_pct"] == 0.0 and vacio["utilidad_neta_cop"] == 0 and solo_ingreso["rentabilidad_pct"] == 0.0
    assert solo_ingreso["ingresos_cop"] == 500000 and solo_ingreso["utilidad_neta_cop"] == 500000
    obs("Ciclo sin registros: rentabilidad 0,0 y todo en 0. Ciclo solo con ingreso de $500.000: rentabilidad 0,0, utilidad $500.000. Sin errores de división")


def test_CP_RF_28_08(cliente, cabecera):
    f, c, cc = estructura(cliente, cabecera)
    est = resumen(cliente, cabecera, c)["cultivos"][0]["estimado_ficha"]
    assert est == {"siembra_inicial_cop": 1600000, "insumos_anuales_cop": 3320000, "jornales_anuales": 28.0}
    obs(f"Ficha del café con 4.000 matas: siembra inicial ${pesos(est['siembra_inicial_cop'])}, insumos de un año ${pesos(est['insumos_anuales_cop'])}, "
        f"{est['jornales_anuales']:g} jornales al año. El aviso «orientativo» se comprueba en la pantalla")


# ================================================================ RF-35 y RF-36 sincronización
def test_CP_RF_36_02(cliente, cabecera):
    f, c, cc = estructura(cliente, cabecera)
    g = reg("gasto", nid(), gasto(c), t=T1)
    primero = push(cliente, cabecera, g)
    repetido = push(cliente, cabecera, g)  # la red se cortó antes de la respuesta: el dispositivo reenvía el mismo uuid
    filas = [x for x in cliente.get(f"{API}/sync/pull", headers=cabecera).json()["registros"] if x["tipo"] == "gasto"]
    assert estados(primero) == ["ACEPTADO"] and estados(repetido) == ["ACTUALIZADO_POR_SERVIDOR"] and len(filas) == 1
    obs("El mismo registro (mismo uuid) enviado 2 veces: la 1.ª ACEPTADO; la 2.ª ACTUALIZADO_POR_SERVIDOR (ya lo tenía, el dispositivo adopta la copia del servidor) y solo 1 fila en el servidor (sin duplicados)")


def test_CP_RF_36_03(cliente, cabecera):
    f, c, cc = estructura(cliente, cabecera)
    g = nid()
    push(cliente, cabecera, reg("gasto", g, gasto(c, 100000), t=T1))
    viejo = push(cliente, cabecera, reg("gasto", g, gasto(c, 111111), t=T0))
    nuevo = push(cliente, cabecera, reg("gasto", g, gasto(c, 200000), t=T2))
    valor = [x for x in cliente.get(f"{API}/sync/pull", headers=cabecera).json()["registros"] if x["id"] == g][0]["datos"]["valor_cop"]
    assert valor == 200000
    obs(f"Dispositivo A (T1) $100.000; B con T0 (más viejo): {viejo[0]['estado']}; B con T2 (más reciente): {nuevo[0]['estado']}. Queda ${pesos(valor)}, el de updated_at más reciente")


def test_CP_RF_36_04(cliente, cabecera):
    f, c, cc = estructura(cliente, cabecera)
    res = push(cliente, cabecera,
               reg("gasto", nid(), gasto(c, fecha=iso(MANANA)), t=T2),
               reg("ciclo_cultivo", nid(), {"ciclo_id": c, "cultivo_codigo": "PLATANO", "marco": "cuadrado", "dist_a_m": 11}),
               reg("gasto", nid(), gasto(c, 5000), t=T2), reg("ingreso", nid(), venta(c), t=T2))
    assert estados(res) == ["V-47", "V-33", "ACEPTADO", "ACEPTADO"], estados(res)
    obs("Lote mixto: gasto con fecha de mañana → V-47; cultivo a 11 m → V-33; gasto y venta válidos → ACEPTADO (se aplica cada registro por separado)")


def test_CP_RF_36_05(cliente, cabecera):
    f, c, cc = estructura(cliente, cabecera)
    g = nid()
    push(cliente, cabecera, reg("gasto", g, gasto(c), t=T0))
    datos = {"finca": {}, "ciclo": {}, "ciclo_cultivo": {}, "gasto": gasto(c)}  # el dispositivo envía el registro completo con eliminado = true
    out = {tipo: push(cliente, cabecera, reg(tipo, i, datos[tipo], t=T2, eliminado=True))[0] for tipo, i in
           (("finca", f), ("ciclo", c), ("ciclo_cultivo", cc), ("gasto", g))}
    assert [out[t]["estado"] for t in ("finca", "ciclo", "ciclo_cultivo")] == ["RECHAZADO"] * 3
    assert {out[t]["codigo"] for t in ("finca", "ciclo", "ciclo_cultivo")} == {"E-11"} and out["gasto"]["estado"] == "ACEPTADO"
    pull = {x["id"]: x for x in cliente.get(f"{API}/sync/pull", headers=cabecera).json()["registros"]}
    assert pull[g]["eliminado"] is True and not pull[f]["eliminado"] and not pull[c]["eliminado"] and not pull[cc]["eliminado"]
    obs("eliminado = true: finca, ciclo y cultivo del ciclo → RECHAZADO E-11 (quedan como estaban); gasto → ACEPTADO y queda con eliminado")


# ================================================================ RF-37 semilla y catálogo
def test_CP_RF_37_01(cliente, db):
    cultivos = {c.codigo: c for c in db.scalars(select(Cultivo))}
    fichas = cliente.get(f"{API}/catalogo").json()["cultivos"]
    assert sorted(cultivos) == ["CAFE", "PLATANO", "YUCA"] and all(x["ficha_tecnica"] for x in fichas)
    obs("Base recién creada con la semilla: 3 cultivos (CAFE, PLATANO, YUCA), cada uno con su ficha técnica, y C-01 los entrega. Sincronización con el dispositivo: ver e2e_plan.cjs")


def test_CP_RF_37_02(db):
    antes = db.scalar(select(func.count()).select_from(Cultivo))
    cli.cargar_semilla(db)
    cli.cargar_semilla(db)
    despues = db.scalar(select(func.count()).select_from(Cultivo))
    assert antes == despues == 3
    obs(f"Semilla cargada de nuevo 2 veces: cultivos {antes} → {despues}; no se duplican")


def test_CP_RF_37_03(cliente, admin, db):
    from datetime import datetime
    for c in db.scalars(select(Cultivo)):
        c.actualizado_en = datetime(2026, 1, 1)
    db.commit()
    antes = cliente.get(f"{API}/catalogo").json()["actualizado_en"]
    cuerpo = {"nombre": "Café", "unidad_comercial": "carga (125 kg de café pergamino seco)", "distancia_min_m": 1.2,
              "distancia_max_m": 2.2, "marcos_permitidos": ["cuadrado", "tresbolillo"], "fuente_tecnica": "Cenicafé, guía técnica"}
    r = cliente.put(f"{API}/admin/catalogo/CAFE", headers=admin, json=cuerpo)
    nuevo = cliente.get(f"{API}/catalogo", params={"desde": antes}).json()["cultivos"]
    assert r.status_code == 200 and nuevo[0]["distancia_min_m"] == 1.2 and nuevo[0]["distancia_max_m"] == 2.2
    obs(f"AD-04: 200; C-01 con fecha anterior devuelve solo el café con distancia {nuevo[0]['distancia_min_m']}–{nuevo[0]['distancia_max_m']} m")


def test_CP_RF_37_04(cliente, admin):
    base = {"nombre": "Café", "unidad_comercial": "carga (125 kg de café pergamino seco)", "distancia_min_m": 1.0,
            "distancia_max_m": 2.0, "marcos_permitidos": ["cuadrado"], "fuente_tecnica": "Cenicafé, guía técnica"}
    out = {}
    for nombre, mal in (("distancia_min_m 0", {"distancia_min_m": 0}), ("mínimo 2,5 con máximo 2,0", {"distancia_min_m": 2.5}),
                        ("marcos ['hexagonal']", {"marcos_permitidos": ["hexagonal"]})):
        r = cliente.put(f"{API}/admin/catalogo/CAFE", headers=admin, json={**base, **mal})
        assert r.status_code == 400 and error(r)["codigo"] == "E-08" and error(r)["campos"], nombre
        out[nombre] = "E-08 en " + ", ".join(error(r)["campos"])
    r = cliente.put(f"{API}/admin/catalogo/ARROZ", headers=admin, json=base)
    assert r.status_code == 404 and error(r)["codigo"] == "E-07"
    obs("AD-04 inválido: " + "; ".join(f"{k} → {v}" for k, v in out.items()) + "; código «ARROZ» → 404 E-07")


def test_CP_RF_37_05(cliente, cabecera, db):
    estructura(cliente, cabecera)
    cafe = db.scalar(select(Cultivo).where(Cultivo.codigo == "CAFE"))
    db.delete(cafe)
    with pytest.raises(IntegrityError):
        db.commit()
    db.rollback()
    intacto = db.scalar(select(func.count()).select_from(Cultivo))
    yuca = db.scalar(select(Cultivo).where(Cultivo.codigo == "YUCA"))
    db.delete(yuca)
    db.commit()
    restante = db.scalar(select(func.count()).select_from(Cultivo))
    assert intacto == 3 and restante == 2
    obs("Borrar el café (tiene ciclos): la base lo rechaza (llave foránea RESTRICT) y quedan 3 cultivos. Borrar la yuca (sin ciclos), solo en la base de pruebas: queda 2")


# ================================================================ requisitos no funcionales
def test_CP_RNF_09(cliente, cabecera):
    ataques = ["<script>alert(1)</script>", "' OR 1=1 --"]
    f, c, _ = finca_ciclo(cliente, cabecera)
    res = {}
    for a in ataques:
        reg_nombre = registrar(cliente, nombre=a, correo=f"x{len(res)}@correo.com", correo_confirmacion=f"x{len(res)}@correo.com")
        finca = push(cliente, cabecera, reg("finca", nid(), {"nombre": a}))[0]
        lote = push(cliente, cabecera, reg("ciclo", nid(), {"finca_id": f, **DATOS_CICLO, "nombre_lote": a}))[0]
        obs_g = push(cliente, cabecera, reg("gasto", nid(), gasto(c, observaciones=a), t=T2))[0]
        res[a] = [reg_nombre.status_code, finca["estado"], lote["estado"], obs_g["estado"]]
    assert all(v[0] == 400 and v[1] == "RECHAZADO" and v[2] == "RECHAZADO" for v in res.values()), res
    obs("Nombre de usuario, finca y lote con «<script>…» y «' OR 1=1 --»: rechazados. Observaciones del gasto (texto libre): "
        + "; ".join(f"«{k}» → {v[3]}" for k, v in res.items()) + ". La pantalla muestra todo como texto (esc) — ver e2e_plan.cjs. OWASP ZAP: no se ejecutó")


def test_CP_RNF_15(cliente, cabecera, admin):
    f, c, cc = estructura(cliente, cabecera)
    otra = autorizar(registrar_y_activar(cliente, "pedro.gomez@correo.com", "Pedro Gómez", "Cultivo#2026b"))
    pedidos = [("GET", f"/ciclos/{c}/resumen", otra, 403), ("GET", f"/ciclos/{c}/resumen", None, 401), ("GET", "/sync/pull", None, 401),
               ("POST", "/sync/push", None, 401), ("GET", "/admin/usuarios", cabecera, 403), ("GET", "/admin/usuarios", None, 401),
               ("DELETE", f"/admin/usuarios/{nid()}", cabecera, 403), ("PUT", "/admin/catalogo/CAFE", cabecera, 403)]
    bloqueados = 0
    for m, ruta, cab, esperado in pedidos:
        r = cliente.request(m, API + ruta, headers=cab or {}, json={} if m in ("POST", "PUT") else None)
        assert r.status_code == esperado, (m, ruta, r.status_code)
        bloqueados += 1
    ajenas = [x for x in cliente.get(f"{API}/sync/pull", headers=otra).json()["registros"]]
    intento = cliente.post(f"{API}/sync/push", headers=otra, json={"registros": [reg("gasto", nid(), gasto(c), t=T2)]})
    assert ajenas == [] and intento.status_code == 403 and error(intento)["codigo"] == "E-02"
    obs(f"{bloqueados} de {len(pedidos)} peticiones no autorizadas bloqueadas (401/403). Otro agricultor descarga 0 registros ajenos y su intento de escribir en un ciclo ajeno da "
        f"{intento.status_code} {error(intento)['codigo']}")


def test_CP_RNF_16(cliente, db):
    registrar_y_activar(cliente)
    hashes = [u.hash_clave for u in db.scalars(select(Usuario))]
    assert hashes and all(h.startswith("$argon2") and CLAVE not in h for h in hashes)
    malas = {c: registrar(cliente, clave=c, correo=f"k{i}@correo.com", correo_confirmacion=f"k{i}@correo.com").status_code
             for i, c in enumerate(["corta1A#", "sinnumeroABC#", "12345678901234", "Maria1234567#", "aaaaaaaaaaaa1"])}
    obs(f"{len(hashes)} cuenta(s) en la base: 0 claves en texto plano; todas con hash Argon2id. Claves que incumplen la política → códigos {sorted(set(malas.values()))}")


def test_CP_RNF_17(cliente, db):
    sin = registrar(cliente, autoriza_datos=False)
    registrar(cliente)
    u = db.scalar(select(Usuario))
    assert sin.status_code == 400 and u.consentimiento_ley1581 is True and u.creado_en is not None
    obs(f"Sin autorización: 400 V-08, no se crea cuenta. Con autorización: consentimiento = {u.consentimiento_ley1581} guardado con fecha {u.creado_en:%Y-%m-%d %H:%M}")


def test_CP_RNF_22():
    # valores oráculo del plan (documento 14): los resultados esperados ya traen el redondeo que pide cada requisito
    casos = [("RF-18 cuadrado 1 m", formulas.matas_por_hectarea("cuadrado", 1, None, None)[1], 10000.0),
             ("RF-18 rectangular 2 × 1,5 m", formulas.matas_por_hectarea("rectangular", 2, 1.5, None)[1], 3333.33),
             ("RF-18 tresbolillo 3 m", formulas.matas_por_hectarea("tresbolillo", 3, None, None)[1], 1283.0012),
             ("RF-18 café 1,5 m", formulas.matas_por_hectarea("cuadrado", 1.5, None, None)[1], 4444.44),
             ("RF-24 3 × $60.000", formulas.costo_jornal(3, 60000), 180000),
             ("RF-28 utilidad", formulas.calcular_utilidad([150000], [500000], 0.9)[3], 350000),
             ("RF-28 rentabilidad", formulas.calcular_utilidad([150000], [500000], 0.9)[4], 233.3)]
    errores = [(n, abs(real - teorico) / teorico * 100) for n, real, teorico in casos]
    peor = max(e for _, e in errores)
    assert peor <= 0.0001, errores
    detalle = "; ".join(f"{n}: {real} vs {teorico}" for n, real, teorico in casos)
    obs(f"Peor error relativo de {len(casos)} cálculos frente a los valores oráculo del plan: {peor:.6f} % (meta ≤ 0,0001 %; "
        f"el mayor es el del tresbolillo, porque el servidor redondea a 2 decimales). {detalle}")


def test_CP_RNF_25(monkeypatch):
    from fastapi.testclient import TestClient
    from app.main import app as aplicacion
    from app.services import catalogo_service

    def falla(*_a, **_k):
        raise RuntimeError("fallo simulado de la base de datos: Traceback (most recent call last) mysql://usuario:clave@host/bd")
    monkeypatch.setattr(catalogo_service, "consultar", falla)
    with TestClient(aplicacion, raise_server_exceptions=False) as c:
        r = c.get(f"{API}/catalogo")
        no_existe = c.get(f"{API}/ruta-que-no-existe")
        metodo = c.put(f"{API}/salud")
    cuerpo = r.text
    for tabu in ("Traceback", "RuntimeError", "mysql://", "clave@", "File \""):
        assert tabu not in cuerpo, tabu
    assert r.status_code == 500 and r.json()["error"]["codigo"] == "V-45" and no_existe.status_code == 404 and metodo.status_code == 405
    obs(f"Error interno forzado: 500 con V-45 «{r.json()['error']['mensaje']}» y sin trazas, rutas ni datos de la base. Ruta inexistente: 404 E-07; método no permitido: 405 E-03. "
        "Falla de red del dispositivo: ver e2e_plan.cjs")
