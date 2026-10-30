"""Proyección de cosecha (ficha técnica): redondeo hacia arriba, fecha de la primera cosecha, producción e ingreso estimados."""
from datetime import date
from decimal import Decimal

from app.domain import formulas
from app.domain.fechas import sumar_meses
from tests.conftest import API, obs
from tests.test_plan_funcional import estructura, resumen

CAFE = {"base_plantas": 1000, "meses_primera_cosecha": 20, "meses_cosecha": [4, 5, 6, 10, 11, 12], "cosecha_unica": False,
        "produccion_base": 2.5, "precio_ref_cop": 2220000, "precio_ref_fecha": "2026-04-09"}


def test_redondear_arriba_con_dos_decimales():
    assert formulas.redondear_arriba(4444.4401, 2) == Decimal("4444.45")
    assert formulas.redondear_arriba(10, 2) == Decimal("10.00")
    assert formulas.redondear_arriba("0.011", 2) == Decimal("0.02")
    assert formulas.redondear_arriba(Decimal("3.2"), 0) == Decimal("4")


def test_CP_RF_18_11():
    # 1 ha con 1,5 m: 4.444,44 matas exactas → 4.445 (no existe media mata); 0,9 ha → 4.000 exactas
    assert formulas.matas_del_ciclo("CUADRADO", 1.5, 0, 1) == 4445
    assert formulas.matas_del_ciclo("cuadrado", 1.5, 0, 0.9) == 4000
    assert formulas.matas_por_lote(4444.44, 1) == 4445
    obs('1 ha con 1,5 m: 4.444,44 matas exactas → 4.445 (entera, hacia arriba); 0,9 ha → 4.000; N_ha 4.444,4401 → 4.444,45')


def test_sumar_meses_ajusta_el_fin_de_mes():
    assert sumar_meses(date(2026, 3, 15), 20) == date(2027, 11, 15)
    assert sumar_meses(date(2026, 1, 31), 1) == date(2026, 2, 28)
    assert sumar_meses(date(2026, 10, 31), 12) == date(2027, 10, 31)
    assert sumar_meses(date(2026, 12, 15), 1) == date(2027, 1, 15)


def test_CP_RF_18_08():
    p = formulas.proyectar_cosecha(CAFE, 4000, date(2026, 3, 15))
    assert p["primera_cosecha"] == date(2027, 11, 15)
    assert p["produccion_estimada"] == 10.0                 # 4.000 / 1.000 × 2,5 cargas
    assert p["ingreso_estimado_cop"] == 22_200_000          # 10 × $ 2.220.000
    assert p["temporadas"] == [4, 5, 6, 10, 11, 12] and p["cosecha_unica"] is False
    obs(f"Café, 4.000 matas, siembra 15/03/2026: primera cosecha {p['primera_cosecha']}; "
        f"{p['produccion_estimada']} cargas/año; ingreso ${p['ingreso_estimado_cop']:,} (temporadas abr–jun y oct–dic)")


def test_CP_RF_18_09():
    YUCA = {"base_plantas": 1000, "meses_primera_cosecha": 10, "meses_cosecha": None, "cosecha_unica": True,
            "produccion_base": 28, "precio_ref_cop": 68250, "precio_ref_fecha": "2026-10-26"}
    p = formulas.proyectar_cosecha(YUCA, 3000, date(2026, 1, 20))
    assert p["primera_cosecha"] == date(2026, 11, 20) and p["cosecha_unica"] is True and p["temporadas"] is None
    assert p["produccion_estimada"] == 84.0 and p["ingreso_estimado_cop"] == 5_733_000
    obs(f"Yuca, 3.000 matas, siembra 20/01/2026: cosecha única el {p['primera_cosecha']}; "
        f"{p['produccion_estimada']} bultos; ingreso ${p['ingreso_estimado_cop']:,}; sin temporadas")


def test_la_produccion_se_redondea_hacia_arriba_con_dos_decimales():
    p = formulas.proyectar_cosecha({**CAFE, "produccion_base": 2.5}, 4445, date(2026, 3, 15))
    assert p["produccion_estimada"] == 11.12                # 11,1125 → 11,12


def test_CP_RF_18_10():
    assert formulas.proyectar_cosecha({"base_plantas": 1000}, 100, date(2026, 3, 15)) is None
    assert formulas.proyectar_cosecha({**CAFE, "precio_ref_cop": None}, 1000, date(2026, 1, 1))["ingreso_estimado_cop"] is None
    obs('Ficha sin datos de cosecha → proyección vacía (no se inventa nada); sin precio → producción sí, ingreso vacío')


def test_el_resumen_trae_la_proyeccion(cliente, cabecera):
    f, c, cc = estructura(cliente, cabecera)
    x = resumen(cliente, cabecera, c)["cultivos"][0]
    assert x["matas"] == 4000
    p = x["proyeccion"]
    assert p["produccion_estimada"] == 10.0 and p["ingreso_estimado_cop"] == 22_200_000 and p["primera_cosecha"].count("-") == 2


def test_CP_RF_37_06(cliente):
    cafe = [c for c in cliente.get(f"{API}/catalogo").json()["cultivos"] if c["codigo"] == "CAFE"][0]["ficha_tecnica"]
    assert cafe["meses_primera_cosecha"] == 20 and cafe["produccion_base"] == 2.5 and cafe["precio_ref_cop"] == 2220000
    assert cafe["precio_ref_fecha"] == "2026-04-09" and cafe["cosecha_unica"] is False
    yuca = [c for c in cliente.get(f"{API}/catalogo").json()["cultivos"] if c["codigo"] == "YUCA"][0]["ficha_tecnica"]
    assert yuca["cosecha_unica"] is True and yuca["meses_cosecha"] is None
    obs(f"C-01 publica el café: primera cosecha {cafe['meses_primera_cosecha']} meses, {cafe['produccion_base']} cargas/1.000 plantas, "
        f"${cafe['precio_ref_cop']:,} ({cafe['precio_ref_fecha']}); la yuca es de cosecha única")


BASE = {"nombre": "Café", "unidad_comercial": "carga (125 kg de café pergamino seco)", "distancia_min_m": 1.0,
        "distancia_max_m": 2.0, "marcos_permitidos": ["cuadrado"], "fuente_tecnica": "Cenicafé, guía técnica"}
FICHA = {"base_plantas": 1000, "costo_hoyado_cop": 350, "costo_colino_cop": 120, "insumo_anual_cop": 900,
         "jornales_limpieza_anio": 4, "jornales_riego_anio": 3.5}


def test_CP_RF_37_07(cliente, admin):
    r = cliente.put(f"{API}/admin/catalogo/CAFE", headers=admin, json={**BASE, "ficha_tecnica": {**FICHA, "meses_primera_cosecha": 22,
                    "meses_cosecha": [10, 4, 5], "produccion_base": 3, "precio_ref_cop": 2300000, "precio_ref_fecha": "2026-10-01"}})
    assert r.status_code == 200
    f = r.json()["ficha_tecnica"]
    assert f["meses_primera_cosecha"] == 22 and f["meses_cosecha"] == [4, 5, 10] and f["produccion_base"] == 3.0
    for mal in ({"meses_primera_cosecha": 0}, {"meses_primera_cosecha": 121}, {"meses_cosecha": []}, {"meses_cosecha": [13]},
                {"meses_cosecha": [4, 4]}, {"cosecha_unica": "si"}, {"produccion_base": 0}, {"produccion_base": 1.234},
                {"precio_ref_cop": -1}, {"precio_ref_cop": 60_000_000}, {"precio_ref_fecha": "09/04/2026"}):
        r = cliente.put(f"{API}/admin/catalogo/CAFE", headers=admin, json={**BASE, "ficha_tecnica": {**FICHA, **mal}})
        assert r.status_code == 400 and r.json()["error"]["codigo"] == "E-08", mal
        assert any(k.startswith("ficha_tecnica.") for k in r.json()["error"]["campos"]), mal
    # una ficha sin esos campos no borra los que ya estaban
    r = cliente.put(f"{API}/admin/catalogo/CAFE", headers=admin, json={**BASE, "ficha_tecnica": FICHA})
    assert r.status_code == 200 and r.json()["ficha_tecnica"]["meses_primera_cosecha"] == 22
    obs("AD-04 guarda 22 meses y temporadas ordenadas [4, 5, 10]; rechaza con E-08 meses 0 y 121, lista vacía o con 13 o repetidos, "
        "producción 0 o con 3 decimales, precio negativo o sobre 50.000.000 y fecha dd/mm/aaaa; una ficha sin esos campos no borra los guardados")
