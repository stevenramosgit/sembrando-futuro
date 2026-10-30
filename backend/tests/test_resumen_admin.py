"""C-01, R-01, H-01 y AD-01 a AD-05."""
import pytest
from sqlalchemy import func, select

from app.models import Ciclo, CicloCultivo, Cultivo, Finca, Gasto, Ingreso, Jornal, Otp, Token, Usuario
from app.models.usuario import IntentoIngreso
from tests.conftest import API, CLAVE, autorizar, registrar_y_activar
from tests.test_sync import T0, T1, estructura, gasto, nid, push, reg


def test_salud(cliente):
    r = cliente.get(f"{API}/salud")
    assert r.status_code == 200 and r.json()["estado"] == "ok" and r.json()["hora"].endswith("Z")


def test_catalogo_completo_y_304(cliente):
    r = cliente.get(f"{API}/catalogo")
    assert r.status_code == 200
    c = r.json()
    assert c["version"] == 1 and [x["codigo"] for x in c["cultivos"]] == ["CAFE", "PLATANO", "YUCA"]
    cafe = [x for x in c["cultivos"] if x["codigo"] == "CAFE"][0]
    assert cafe["distancia_min_m"] == 1.0 and cafe["distancia_max_m"] == 2.0 and "tresbolillo" in cafe["marcos_permitidos"]
    ficha = cafe["ficha_tecnica"]
    assert (ficha["base_plantas"], ficha["costo_hoyado_cop"], ficha["costo_colino_cop"], ficha["insumo_anual_cop"]) == (1000, 300, 100, 830)
    assert (ficha["jornales_limpieza_anio"], ficha["jornales_riego_anio"]) == (4.0, 3.0)
    assert all(x["ficha_tecnica"] is not None for x in c["cultivos"])  # las tres fichas vienen precargadas
    assert cliente.get(f"{API}/catalogo", params={"desde": c["actualizado_en"]}).status_code == 304
    assert cliente.get(f"{API}/catalogo", params={"desde": "2000-01-01T00:00:00Z"}).status_code == 200
    assert cliente.get(f"{API}/catalogo", params={"desde": "ayer"}).status_code == 400


def completar_ciclo(cliente, cab):
    f, c, cc = estructura(cliente, cab)
    push(cliente, cab,
         reg("gasto", nid(), gasto(c, 100000)),
         reg("gasto", nid(), gasto(c, 30000)),
         reg("jornal", nid(), {"ciclo_id": c, "fecha": "2026-04-20", "jornales": 0.5, "valor_diario_cop": 40000}),
         reg("ingreso", nid(), {"ciclo_id": c, "fecha": "2026-09-10", "cantidad": 4, "precio_unitario_cop": 125000}))
    return f, c, cc


def test_resumen_calcula_con_las_formulas_del_dominio(cliente, cabecera):
    f, c, cc = completar_ciclo(cliente, cabecera)
    r = cliente.get(f"{API}/ciclos/{c}/resumen", headers=cabecera)
    assert r.status_code == 200
    x = r.json()
    assert x["gastos_cop"] == 130000 and x["jornales_cop"] == 20000 and x["costos_totales_cop"] == 150000
    assert x["ingresos_cop"] == 500000 and x["utilidad_neta_cop"] == 350000
    assert x["rentabilidad_pct"] == 233.3 and x["utilidad_por_ha_cop"] == 388889 and x["total_matas"] == 4000
    assert x["registros"] == {"gastos": 2, "jornales": 1, "ingresos": 1}
    assert x["ciclo"]["nombre_lote"] == "Lote Alto" and x["ciclo"]["area_efectiva_ha"] == 0.9
    assert len(x["cultivos"]) == 1 and x["cultivos"][0]["codigo"] == "CAFE" and x["cultivos"][0]["marco"] == "cuadrado"
    assert x["cultivos"][0]["matas"] == 4000
    # ficha técnica del café: 4.000 matas × ($300 + $100) y 4.000 × $830; (4 + 3) jornales por cada 1.000 matas al año
    assert x["cultivos"][0]["estimado_ficha"] == {"siembra_inicial_cop": 1600000, "insumos_anuales_cop": 3320000, "jornales_anuales": 28.0}
    assert x["ciclo"]["vigencia_anios"] == 7 and x["ciclo"]["fecha_fin_estimada"] == "2033-03-15"
    assert x["ciclo"]["semaforo"] in ("VERDE", "AMARILLO", "ROJO") and x["ciclo"]["anios_restantes"] is not None


def test_resumen_de_un_ciclo_con_dos_cultivos_suma_las_matas(cliente, cabecera):
    f, c, cc = estructura(cliente, cabecera)
    push(cliente, cabecera, reg("ciclo_cultivo", nid(), {"ciclo_id": c, "cultivo_codigo": "PLATANO", "marco": "rectangular",
                                                         "dist_a_m": 3.0, "dist_b_m": 2.0}))
    x = cliente.get(f"{API}/ciclos/{c}/resumen", headers=cabecera).json()
    assert [k["codigo"] for k in x["cultivos"]] == ["CAFE", "PLATANO"]
    assert [k["matas"] for k in x["cultivos"]] == [4000, 1500] and x["total_matas"] == 5500


def test_resumen_sin_vigencia_ni_marco(cliente, cabecera):
    f, c, cc = estructura(cliente, cabecera, ciclo={"vigencia_anios": None})
    push(cliente, cabecera, reg("ciclo_cultivo", nid(), {"ciclo_id": c, "cultivo_codigo": "YUCA"}))
    x = cliente.get(f"{API}/ciclos/{c}/resumen", headers=cabecera).json()
    assert x["ciclo"]["vigencia_anios"] is None and x["ciclo"]["fecha_fin_estimada"] is None and x["ciclo"]["semaforo"] is None
    yuca = [k for k in x["cultivos"] if k["codigo"] == "YUCA"][0]
    assert yuca["matas"] is None and yuca["estimado_ficha"] is None


def test_resumen_sin_movimientos_no_divide_por_cero(cliente, cabecera):
    f, c, cc = estructura(cliente, cabecera)
    x = cliente.get(f"{API}/ciclos/{c}/resumen", headers=cabecera).json()
    assert x["rentabilidad_pct"] == 0.0 and x["costos_totales_cop"] == 0 and x["utilidad_por_ha_cop"] == 0


def test_resumen_ignora_eliminados(cliente, cabecera):
    f, c, cc = estructura(cliente, cabecera)
    g = nid()
    push(cliente, cabecera, reg("gasto", g, gasto(c, 100000), t=T0))
    push(cliente, cabecera, reg("gasto", g, {"ciclo_id": c}, t=T1, eliminado=True))
    assert cliente.get(f"{API}/ciclos/{c}/resumen", headers=cabecera).json()["gastos_cop"] == 0


def test_resumen_errores(cliente, cabecera):
    f, c, cc = estructura(cliente, cabecera)
    assert cliente.get(f"{API}/ciclos/{nid()}/resumen", headers=cabecera).json()["error"]["codigo"] == "E-07"
    otra = autorizar(registrar_y_activar(cliente, "pedro.gomez@correo.com", "Pedro Gómez", "Cultivo#2026b"))
    r = cliente.get(f"{API}/ciclos/{c}/resumen", headers=otra)
    assert r.status_code == 403 and r.json()["error"]["codigo"] == "E-02"
    assert cliente.get(f"{API}/ciclos/{c}/resumen").status_code == 401


# ---------------------------------------------------------------------------- administración
def test_admin_exige_token_y_rol(cliente, cabecera, admin):
    for metodo, ruta in (("get", "/admin/usuarios"), ("post", "/admin/usuarios/x/clave"), ("delete", "/admin/usuarios/x"),
                         ("put", "/admin/catalogo/CAFE"), ("get", "/admin/usuarios/x/resumen")):
        assert getattr(cliente, metodo)(API + ruta).status_code == 401
        r = getattr(cliente, metodo)(API + ruta, headers=cabecera)
        assert r.status_code == 403 and r.json()["error"]["codigo"] == "E-06"


def test_crear_admin_solo_uno(db):
    from app import cli
    cli.crear_admin(db, "admin.proyecto@correo.com", "Cafe#Cauca2026")
    with pytest.raises(SystemExit) as e:
        cli.crear_admin(db, "otro.admin@correo.com", "Cafe#Cauca2026")
    assert "administrador" in str(e.value)


def test_ad01_listar_con_filtro_y_paginacion(cliente, cabecera, admin):
    registrar_y_activar(cliente, "pedro.gomez@correo.com", "Pedro Gómez", "Cultivo#2026b")
    cliente.post(f"{API}/auth/registro", json={"nombre": "Luz Mena", "ubicacion": "Betulia, Cauca", "correo": "luz.mena@correo.com",
                                               "correo_confirmacion": "luz.mena@correo.com", "clave": "Cosecha#2026c", "autoriza_datos": True})
    todos = cliente.get(f"{API}/admin/usuarios", headers=admin).json()
    assert todos["total"] == 3 and todos["pagina"] == 1 and all(u["rol"] == "AGRICULTOR" for u in todos["usuarios"])
    assert "admin.proyecto@correo.com" not in str(todos)
    assert cliente.get(f"{API}/admin/usuarios", headers=admin, params={"estado": "PENDIENTE"}).json()["total"] == 1
    p = cliente.get(f"{API}/admin/usuarios", headers=admin, params={"limite": 2, "pagina": 2}).json()
    assert len(p["usuarios"]) == 1 and p["total"] == 3
    for mal in ({"estado": "X"}, {"pagina": 0}, {"limite": 101}, {"limite": 0}):
        assert cliente.get(f"{API}/admin/usuarios", headers=admin, params=mal).json()["error"]["codigo"] == "E-03"


def id_de(cliente, admin, correo):
    return [u["id"] for u in cliente.get(f"{API}/admin/usuarios", headers=admin).json()["usuarios"] if u["correo"] == correo][0]


def test_ad02_cambiar_clave_revoca_sesiones_y_desbloquea(cliente, cabecera, admin, token, db):
    uid = id_de(cliente, admin, "maria.perez@correo.com")
    for _ in range(5):
        cliente.post(f"{API}/auth/ingreso", json={"correo": "maria.perez@correo.com", "clave": "Mala#Clave2026"})
    assert cliente.post(f"{API}/auth/ingreso", json={"correo": "maria.perez@correo.com", "clave": CLAVE}).status_code == 423
    r = cliente.post(f"{API}/admin/usuarios/{uid}/clave", headers=admin, json={"clave_nueva": "123"})
    assert r.status_code == 400 and r.json()["error"]["campos"]["clave_nueva"]["codigo"] == "V-07"
    assert cliente.post(f"{API}/admin/usuarios/{uid}/clave", headers=admin, json={"clave_nueva": "Nueva#Siembra88"}).status_code == 204
    assert cliente.get(f"{API}/sync/pull", headers=cabecera).status_code == 401  # su sesión anterior quedó revocada
    assert cliente.post(f"{API}/auth/ingreso", json={"correo": "maria.perez@correo.com", "clave": CLAVE}).status_code == 401
    assert cliente.post(f"{API}/auth/ingreso", json={"correo": "maria.perez@correo.com", "clave": "Nueva#Siembra88"}).status_code == 200


def test_ad02_no_aplica_al_administrador_ni_a_desconocidos(cliente, admin, db):
    aid = db.scalar(select(Usuario.id_usuario).where(Usuario.rol == "ADMIN"))
    assert cliente.post(f"{API}/admin/usuarios/{aid}/clave", headers=admin, json={"clave_nueva": "Nueva#Siembra88"}).status_code == 404
    assert cliente.post(f"{API}/admin/usuarios/{nid()}/clave", headers=admin, json={"clave_nueva": "Nueva#Siembra88"}).status_code == 404


def test_ad03_elimina_todo_lo_de_la_cuenta(cliente, cabecera, admin, db):
    completar_ciclo(cliente, cabecera)
    otra = autorizar(registrar_y_activar(cliente, "pedro.gomez@correo.com", "Pedro Gómez", "Cultivo#2026b"))
    completar_ciclo(cliente, otra)
    uid = id_de(cliente, admin, "maria.perez@correo.com")
    cliente.post(f"{API}/auth/ingreso", json={"correo": "nadie@correo.com", "clave": "x"})
    db.add(IntentoIngreso(correo="maria.perez@correo.com", intentos_fallidos=2, actualizado_en=__import__("app.core.seguridad", fromlist=["ahora"]).ahora()))
    db.commit()
    assert cliente.delete(f"{API}/admin/usuarios/{uid}", headers=admin).status_code == 204
    db.expire_all()
    cuentas = {u.correo for u in db.scalars(select(Usuario))}
    assert cuentas == {"pedro.gomez@correo.com", "admin.proyecto@correo.com"}
    for modelo, esperado in ((Finca, 1), (Ciclo, 1), (CicloCultivo, 1), (Gasto, 2), (Jornal, 1), (Ingreso, 1)):
        assert db.scalar(select(func.count()).select_from(modelo)) == esperado, modelo
    assert db.get(IntentoIngreso, "maria.perez@correo.com") is None
    assert db.scalar(select(func.count()).select_from(Token).where(Token.id_usuario == uid)) == 0
    assert db.scalar(select(func.count()).select_from(Otp).where(Otp.id_usuario == uid)) == 0
    assert cliente.get(f"{API}/sync/pull", headers=cabecera).status_code == 401
    assert registrar_y_activar(cliente, "maria.perez@correo.com")  # el correo quedó libre


def test_ad03_errores(cliente, admin, db):
    aid = db.scalar(select(Usuario.id_usuario).where(Usuario.rol == "ADMIN"))
    r = cliente.delete(f"{API}/admin/usuarios/{aid}", headers=admin)
    assert r.status_code == 409 and r.json()["error"]["codigo"] == "E-09"
    assert cliente.delete(f"{API}/admin/usuarios/{nid()}", headers=admin).status_code == 404


def test_ad04_actualizar_ficha(cliente, admin, db):
    from datetime import datetime
    for c in db.scalars(select(Cultivo)):
        c.actualizado_en = datetime(2026, 1, 1)  # la semilla es anterior a la edición
    db.commit()
    ficha = {"nombre": "Café", "unidad_comercial": "carga (125 kg de café pergamino seco)", "distancia_min_m": 1.2,
             "distancia_max_m": 2.2, "marcos_permitidos": ["cuadrado", "tresbolillo"], "fuente_tecnica": "Cenicafé, guía técnica"}
    antes = cliente.get(f"{API}/catalogo").json()["actualizado_en"]
    r = cliente.put(f"{API}/admin/catalogo/CAFE", headers=admin, json=ficha)
    assert r.status_code == 200 and r.json()["distancia_min_m"] == 1.2 and r.json()["actualizado_en"].endswith("Z")
    cambiados = cliente.get(f"{API}/catalogo", params={"desde": antes}).json()["cultivos"]
    assert [c["codigo"] for c in cambiados] == ["CAFE"] and cambiados[0]["marcos_permitidos"] == ["cuadrado", "tresbolillo"]
    assert cliente.put(f"{API}/admin/catalogo/NOEXISTE", headers=admin, json=ficha).json()["error"]["codigo"] == "E-07"
    for mal in ({"nombre": "x"}, {"unidad_comercial": "ab"}, {"distancia_min_m": 0}, {"distancia_max_m": 1.0},
                {"distancia_max_m": 11}, {"marcos_permitidos": []}, {"marcos_permitidos": ["cuadrado", "cuadrado"]},
                {"marcos_permitidos": ["hexagonal"]}, {"fuente_tecnica": "cort"}):
        r = cliente.put(f"{API}/admin/catalogo/CAFE", headers=admin, json={**ficha, **mal})
        assert r.status_code == 400 and r.json()["error"]["codigo"] == "E-08" and r.json()["error"]["campos"], mal


def test_ad04_actualizar_la_ficha_tecnica_de_un_cultivo(cliente, admin, db):
    from datetime import datetime
    for c in db.scalars(select(Cultivo)):
        c.actualizado_en = datetime(2026, 1, 1)
    db.commit()
    base = {"nombre": "Café", "unidad_comercial": "carga (125 kg de café pergamino seco)", "distancia_min_m": 1.0,
            "distancia_max_m": 2.0, "marcos_permitidos": ["cuadrado"], "fuente_tecnica": "Cenicafé, guía técnica"}
    ficha = {"base_plantas": 1000, "costo_hoyado_cop": 350, "costo_colino_cop": 120, "insumo_anual_cop": 900,
             "jornales_limpieza_anio": 4, "jornales_riego_anio": 3.5, "datos_extra": {"sombrio": "plátano"}}
    antes = cliente.get(f"{API}/catalogo").json()["actualizado_en"]
    r = cliente.put(f"{API}/admin/catalogo/CAFE", headers=admin, json={**base, "ficha_tecnica": ficha})
    assert r.status_code == 200
    assert r.json()["ficha_tecnica"]["costo_hoyado_cop"] == 350 and r.json()["ficha_tecnica"]["datos_extra"] == {"sombrio": "plátano"}
    assert [c["codigo"] for c in cliente.get(f"{API}/catalogo", params={"desde": antes}).json()["cultivos"]] == ["CAFE"]
    # sin 'ficha_tecnica' en la petición, la ficha existente no se modifica
    r = cliente.put(f"{API}/admin/catalogo/CAFE", headers=admin, json=base)
    assert r.status_code == 200 and r.json()["ficha_tecnica"]["costo_hoyado_cop"] == 350
    for mal in ({"base_plantas": 0}, {"costo_hoyado_cop": -1}, {"costo_colino_cop": "100"}, {"insumo_anual_cop": 60_000_000},
                {"jornales_limpieza_anio": 1000}, {"jornales_riego_anio": 1.25}, {"datos_extra": "texto"}):
        r = cliente.put(f"{API}/admin/catalogo/CAFE", headers=admin, json={**base, "ficha_tecnica": {**ficha, **mal}})
        assert r.status_code == 400 and r.json()["error"]["codigo"] == "E-08", mal
        assert any(k.startswith("ficha_tecnica.") for k in r.json()["error"]["campos"]), mal
    assert cliente.put(f"{API}/admin/catalogo/CAFE", headers=admin, json={**base, "ficha_tecnica": "x"}).status_code == 400


def test_ad05_resumen_de_cuenta(cliente, cabecera, admin):
    completar_ciclo(cliente, cabecera)
    uid = id_de(cliente, admin, "maria.perez@correo.com")
    x = cliente.get(f"{API}/admin/usuarios/{uid}/resumen", headers=admin).json()
    assert x["totales"] == {"fincas": 1, "ciclos": 1, "gastos": 2, "jornales": 1, "ingresos": 1}
    assert x["fincas"][0]["ciclos_activos"] == 1 and "lotes" not in x["fincas"][0] and x["usuario"]["estado"] == "ACTIVA"
    assert cliente.get(f"{API}/admin/usuarios/{nid()}/resumen", headers=admin).status_code == 404
