"""S-01 y S-02: orden, última escritura gana, reglas por tipo, propiedad, eliminación lógica y paginación."""
import uuid

from tests.conftest import API, autorizar, registrar_y_activar

T0 = "2026-10-26T13:00:00.000Z"
T1 = "2026-10-26T13:05:00.000Z"
T2 = "2026-10-26T13:10:00.000Z"


def nid():
    return str(uuid.uuid4())


def reg(tipo, id_, datos, t=T0, eliminado=False):
    return {"tipo": tipo, "id": id_, "updated_at": t, "eliminado": eliminado, "datos": datos}


def push(cliente, cab, *registros):
    r = cliente.post(f"{API}/sync/push", headers=cab, json={"dispositivo_id": "d1", "registros": list(registros)})
    assert r.status_code == 200, r.text
    return r.json()["resultados"]


DATOS_CICLO = {"nombre_lote": "Lote Alto", "pendiente_pct": 12, "area_bruta_ha": 1.0, "area_no_sembrable_ha": 0.1,
               "area_efectiva_ha": 0.9, "fecha_siembra": "2026-03-15", "vigencia_anios": 7, "estado": "ACTIVO"}
DATOS_CAFE = {"cultivo_codigo": "CAFE", "marco": "cuadrado", "dist_a_m": 1.5}


def estructura(cliente, cab, ciclo=None):
    """Crea una finca con un ciclo de 0,9 ha y su cultivo (café, cuadrado 1,5 m) y devuelve (finca, ciclo, ciclo_cultivo)."""
    f, c, cc = nid(), nid(), nid()
    res = push(cliente, cab,
               reg("finca", f, {"nombre": "La Esperanza"}),
               reg("ciclo", c, {"finca_id": f, **DATOS_CICLO, **(ciclo or {})}),
               reg("ciclo_cultivo", cc, {"ciclo_id": c, **DATOS_CAFE}))
    assert [r["estado"] for r in res] == ["ACEPTADO"] * 3, res
    return f, c, cc


def gasto(c, valor=100000, **extra):
    return {"ciclo_id": c, "fecha": "2026-04-12", "categoria": "abonos", "valor_cop": valor, "observaciones": "Abono orgánico", **extra}


def test_orden_se_corrige_y_respeta_el_orden_de_respuesta(cliente, cabecera):
    f, c, cc, g = nid(), nid(), nid(), nid()
    res = push(cliente, cabecera,
               reg("gasto", g, gasto(c)),
               reg("ciclo_cultivo", cc, {"ciclo_id": c, **DATOS_CAFE}),
               reg("ciclo", c, {"finca_id": f, **DATOS_CICLO}),
               reg("finca", f, {"nombre": "Finca Uno"}))
    assert [r["id"] for r in res] == [g, cc, c, f]
    assert all(r["estado"] == "ACEPTADO" for r in res), [(x["estado"], x.get("codigo")) for x in res]


def test_padre_inexistente_E01(cliente, cabecera):
    r = push(cliente, cabecera, reg("gasto", nid(), gasto(nid())))[0]
    assert r["estado"] == "RECHAZADO" and r["codigo"] == "E-01"


def test_tipo_desconocido_E05(cliente, cabecera):
    r = push(cliente, cabecera, reg("semilla", nid(), {}))[0]
    assert r["estado"] == "RECHAZADO" and r["codigo"] == "E-05"


def test_mas_de_500_registros_E04(cliente, cabecera):
    r = cliente.post(f"{API}/sync/push", headers=cabecera,
                     json={"registros": [reg("finca", nid(), {"nombre": "Finca"}) for _ in range(501)]})
    assert r.status_code == 400 and r.json()["error"]["codigo"] == "E-04"
    r = cliente.post(f"{API}/sync/push", headers=cabecera,
                     json={"registros": [reg("finca", nid(), {"nombre": "Finca"}) for _ in range(500)]})
    assert r.status_code == 200


def test_formato_invalido_E03(cliente, cabecera):
    assert cliente.post(f"{API}/sync/push", headers=cabecera, json={"registros": "x"}).json()["error"]["codigo"] == "E-03"
    r = cliente.post(f"{API}/sync/push", headers=cabecera, json={"registros": [reg("finca", nid(), {"nombre": "Finca"}, t="ayer")]})
    assert r.status_code == 400 and r.json()["error"]["codigo"] == "E-03"


def test_eliminar_finca_ciclo_o_cultivo_del_ciclo_E11(cliente, cabecera):
    f, c, cc = estructura(cliente, cabecera)
    for tipo, i in (("finca", f), ("ciclo", c), ("ciclo_cultivo", cc)):
        r = push(cliente, cabecera, reg(tipo, i, {}, t=T2, eliminado=True))[0]
        assert r["estado"] == "RECHAZADO" and r["codigo"] == "E-11"
    pull = cliente.get(f"{API}/sync/pull", headers=cabecera).json()["registros"]
    assert len(pull) == 3 and not any(x["eliminado"] for x in pull)


def test_ciclo_reglas_de_los_datos_del_lote(cliente, cabecera):
    f, c, cc = estructura(cliente, cabecera)
    base = {"finca_id": f, **DATOS_CICLO}
    casos = [({"nombre_lote": "x"}, "V-22"), ({"area_bruta_ha": 0}, "V-24"), ({"pendiente_pct": 101}, "V-25"),
             ({"area_no_sembrable_ha": 1}, "V-26"), ({"fecha_siembra": "15/03/2026"}, "V-28"),
             ({"fecha_siembra": "2019-12-31"}, "V-48"), ({"estado": "CERRADO", "fecha_cierre": "2026-01-01"}, "V-29"),
             ({"estado": "CERRADO", "fecha_cierre": "2999-01-01"}, "V-29"), ({"estado": "CERRADO"}, "V-28"),
             ({"vigencia_anios": 0}, "V-49"), ({"vigencia_anios": 51}, "V-49"), ({"vigencia_anios": 2.5}, "V-49"),
             ({"vigencia_anios": "7"}, "V-49"), ({"estado": "ANULADO"}, "E-03")]
    for cambio, codigo in casos:
        r = push(cliente, cabecera, reg("ciclo", nid(), {**base, **cambio}))[0]
        assert r["estado"] == "RECHAZADO" and r["codigo"] == codigo, (cambio, r)


def test_nombre_del_lote_y_vigencia_son_opcionales_y_el_nombre_puede_repetirse(cliente, cabecera):
    f, c, cc = estructura(cliente, cabecera)
    sin = {k: v for k, v in DATOS_CICLO.items() if k not in ("nombre_lote", "vigencia_anios")}
    otro = nid()
    assert push(cliente, cabecera, reg("ciclo", otro, {"finca_id": f, **sin}))[0]["estado"] == "ACEPTADO"
    repetido = nid()  # ya no hay lotes: el mismo nombre informativo puede repetirse en la misma finca
    assert push(cliente, cabecera, reg("ciclo", repetido, {"finca_id": f, **DATOS_CICLO}))[0]["estado"] == "ACEPTADO"
    datos = {x["id"]: x["datos"] for x in cliente.get(f"{API}/sync/pull", headers=cabecera).json()["registros"]}
    assert datos[otro]["nombre_lote"] is None and datos[otro]["vigencia_anios"] is None
    assert datos[repetido]["nombre_lote"] == "Lote Alto" and datos[repetido]["vigencia_anios"] == 7


def test_servidor_recalcula_area_efectiva(cliente, cabecera):
    f, c, cc = estructura(cliente, cabecera)
    registro = [x for x in cliente.get(f"{API}/sync/pull", headers=cabecera).json()["registros"] if x["id"] == c][0]
    assert registro["datos"]["area_efectiva_ha"] == 0.9
    r = push(cliente, cabecera, reg("ciclo", c, {"finca_id": f, **DATOS_CICLO, "area_bruta_ha": 2, "area_no_sembrable_ha": 0.5,
                                                 "area_efectiva_ha": 99}, t=T1))[0]
    assert r["estado"] == "ACEPTADO"
    registro = [x for x in cliente.get(f"{API}/sync/pull", headers=cabecera).json()["registros"] if x["id"] == c][0]
    assert registro["datos"]["area_efectiva_ha"] == 1.5


def test_ciclo_cultivo_reglas(cliente, cabecera):
    f, c, cc = estructura(cliente, cabecera)
    base = {"ciclo_id": c, "cultivo_codigo": "YUCA", "marco": "cuadrado", "dist_a_m": 1.0}
    casos = [({"cultivo_codigo": "NOEXISTE"}, "V-27"), ({"cultivo_codigo": None}, "V-27"), ({"cultivo_codigo": "CAFE"}, "V-50"),
             ({"dist_a_m": 0}, "V-33"), ({"marco": "rectangular", "dist_b_m": 0}, "V-33"), ({"marco": "hexagonal"}, "V-32")]
    for cambio, codigo in casos:
        r = push(cliente, cabecera, reg("ciclo_cultivo", nid(), {**base, **cambio}))[0]
        assert r["estado"] == "RECHAZADO" and r["codigo"] == codigo, (cambio, r)
    assert push(cliente, cabecera, reg("ciclo_cultivo", nid(), base))[0]["estado"] == "ACEPTADO"
    assert push(cliente, cabecera, reg("ciclo_cultivo", nid(), {**base, "ciclo_id": nid()}))[0]["codigo"] == "E-01"


def test_ciclo_cultivo_se_edita_pero_no_cambia_de_cultivo(cliente, cabecera):
    f, c, cc = estructura(cliente, cabecera)
    r = push(cliente, cabecera, reg("ciclo_cultivo", cc, {"ciclo_id": c, **DATOS_CAFE, "dist_a_m": 1.8}, t=T1))[0]
    assert r["estado"] == "ACEPTADO"
    fila = [x for x in cliente.get(f"{API}/sync/pull", headers=cabecera).json()["registros"] if x["id"] == cc][0]
    assert fila["datos"]["dist_a_m"] == 1.8 and fila["datos"]["cultivo_codigo"] == "CAFE"
    r = push(cliente, cabecera, reg("ciclo_cultivo", cc, {"ciclo_id": c, **DATOS_CAFE, "cultivo_codigo": "YUCA"}, t=T2))[0]
    assert r["estado"] == "RECHAZADO" and r["codigo"] == "E-03"


def test_un_ciclo_con_varios_cultivos_el_ingreso_indica_cual_se_vendio(cliente, cabecera):
    f, c, cc = estructura(cliente, cabecera)
    assert push(cliente, cabecera, reg("ciclo_cultivo", nid(), {"ciclo_id": c, "cultivo_codigo": "PLATANO", "marco": "rectangular",
                                                                "dist_a_m": 3.0, "dist_b_m": 2.0}))[0]["estado"] == "ACEPTADO"
    venta = {"ciclo_id": c, "fecha": "2026-09-10", "cantidad": 4, "precio_unitario_cop": 125000}
    sin_cultivo = push(cliente, cabecera, reg("ingreso", nid(), venta))[0]
    assert sin_cultivo["estado"] == "RECHAZADO" and sin_cultivo["codigo"] == "V-27"
    ajeno = push(cliente, cabecera, reg("ingreso", nid(), {**venta, "cultivo_codigo": "YUCA"}))[0]  # no está en el ciclo
    assert ajeno["estado"] == "RECHAZADO" and ajeno["codigo"] == "V-27"
    i = nid()
    assert push(cliente, cabecera, reg("ingreso", i, {**venta, "cultivo_codigo": "PLATANO"}))[0]["estado"] == "ACEPTADO"
    fila = [x for x in cliente.get(f"{API}/sync/pull", headers=cabecera).json()["registros"] if x["id"] == i][0]
    assert fila["datos"]["cultivo_codigo"] == "PLATANO" and fila["datos"]["unidad_comercial"] == "racimo"


def test_ingreso_sin_codigo_usa_el_unico_cultivo_del_ciclo(cliente, cabecera):
    f, c, cc = estructura(cliente, cabecera)
    i = nid()
    r = push(cliente, cabecera, reg("ingreso", i, {"ciclo_id": c, "fecha": "2026-09-10", "cantidad": 4, "precio_unitario_cop": 125000}))[0]
    assert r["estado"] == "ACEPTADO"
    fila = [x for x in cliente.get(f"{API}/sync/pull", headers=cabecera).json()["registros"] if x["id"] == i][0]
    assert fila["datos"]["cultivo_codigo"] == "CAFE" and fila["datos"]["unidad_comercial"].startswith("carga")


def test_movimientos_reglas(cliente, cabecera):
    f, c, cc = estructura(cliente, cabecera)
    casos = [
        ("gasto", gasto(c, valor=0), "V-35"), ("gasto", gasto(c, valor="100"), "V-36"), ("gasto", gasto(c, categoria="x"), "V-37"),
        ("gasto", gasto(c, observaciones="<script>"), "V-38"), ("gasto", gasto(c, fecha="12-04-2026"), "V-28"),
        ("gasto", gasto(c, fecha="2026-03-14"), "V-47"), ("gasto", gasto(c, fecha="2999-01-01"), "V-47"),
        ("jornal", {"ciclo_id": c, "fecha": "2026-04-20", "jornales": 0.3, "valor_diario_cop": 25000}, "V-39"),
        ("jornal", {"ciclo_id": c, "fecha": "2026-04-20", "jornales": 2, "valor_diario_cop": 0}, "V-40"),
        ("ingreso", {"ciclo_id": c, "fecha": "2026-09-10", "cantidad": 0.01, "precio_unitario_cop": 125000}, "V-41"),
        ("ingreso", {"ciclo_id": c, "fecha": "2026-09-10", "cantidad": 4, "precio_unitario_cop": 0}, "V-42"),
    ]
    for tipo, datos, codigo in casos:
        r = push(cliente, cabecera, reg(tipo, nid(), datos))[0]
        assert r["estado"] == "RECHAZADO" and r["codigo"] == codigo, (tipo, datos, r)


def test_un_registro_rechazado_no_impide_los_demas(cliente, cabecera):
    f, c, cc = estructura(cliente, cabecera)
    a, b = nid(), nid()
    res = push(cliente, cabecera, reg("gasto", a, gasto(c, valor=0)), reg("gasto", b, gasto(c)))
    assert [r["estado"] for r in res] == ["RECHAZADO", "ACEPTADO"]


def test_ultima_escritura_gana(cliente, cabecera):
    f, c, cc = estructura(cliente, cabecera)
    g = nid()
    assert push(cliente, cabecera, reg("gasto", g, gasto(c, 100000), t=T1))[0]["estado"] == "ACEPTADO"
    r = push(cliente, cabecera, reg("gasto", g, gasto(c, 90000), t=T0))[0]
    assert r["estado"] == "ACTUALIZADO_POR_SERVIDOR" and r["registro"]["datos"]["valor_cop"] == 100000
    r = push(cliente, cabecera, reg("gasto", g, gasto(c, 90000), t=T1))[0]  # igual: gana el servidor
    assert r["estado"] == "ACTUALIZADO_POR_SERVIDOR"
    assert push(cliente, cabecera, reg("gasto", g, gasto(c, 120000), t=T2))[0]["estado"] == "ACEPTADO"
    pull = [x for x in cliente.get(f"{API}/sync/pull", headers=cabecera).json()["registros"] if x["id"] == g][0]
    assert pull["datos"]["valor_cop"] == 120000


def test_eliminar_y_deshacer(cliente, cabecera):
    f, c, cc = estructura(cliente, cabecera)
    g = nid()
    push(cliente, cabecera, reg("gasto", g, gasto(c), t=T0))
    assert push(cliente, cabecera, reg("gasto", g, {"ciclo_id": c}, t=T1, eliminado=True))[0]["estado"] == "ACEPTADO"
    pull = [x for x in cliente.get(f"{API}/sync/pull", headers=cabecera).json()["registros"] if x["id"] == g][0]
    assert pull["eliminado"] is True
    assert push(cliente, cabecera, reg("gasto", g, gasto(c), t=T2))[0]["estado"] == "ACEPTADO"
    pull = [x for x in cliente.get(f"{API}/sync/pull", headers=cabecera).json()["registros"] if x["id"] == g][0]
    assert pull["eliminado"] is False


def test_el_padre_de_un_registro_no_cambia(cliente, cabecera):
    f, c, cc = estructura(cliente, cabecera)
    g = nid()
    push(cliente, cabecera, reg("gasto", g, gasto(c), t=T0))
    f2, c2, cc2 = estructura(cliente, cabecera)
    r = push(cliente, cabecera, reg("gasto", g, gasto(c2), t=T1))[0]
    assert r["estado"] == "RECHAZADO" and r["codigo"] == "E-03"


def test_ciclo_cerrado_V31(cliente, cabecera):
    f, c, cc = estructura(cliente, cabecera)
    anterior = nid()
    push(cliente, cabecera, reg("gasto", anterior, gasto(c), t=T0))
    cierre = {"finca_id": f, **DATOS_CICLO, "estado": "CERRADO", "fecha_cierre": "2026-10-20"}
    assert push(cliente, cabecera, reg("ciclo", c, cierre, t=T1))[0]["estado"] == "ACEPTADO"
    nuevo = push(cliente, cabecera, reg("gasto", nid(), gasto(c), t=T2))[0]
    assert nuevo["estado"] == "RECHAZADO" and nuevo["codigo"] == "V-31"
    # un registro hecho sin conexión antes del cierre sí se acepta
    assert push(cliente, cabecera, reg("gasto", nid(), gasto(c), t="2026-10-26T13:01:00.000Z"))[0]["estado"] == "ACEPTADO"
    # y eliminar uno nuevo del ciclo cerrado también se rechaza
    assert push(cliente, cabecera, reg("gasto", anterior, gasto(c), t=T2, eliminado=True))[0]["codigo"] == "V-31"
    # tampoco se agregan cultivos a un ciclo cerrado
    nuevo_cultivo = push(cliente, cabecera, reg("ciclo_cultivo", nid(), {"ciclo_id": c, "cultivo_codigo": "YUCA"}, t=T2))[0]
    assert nuevo_cultivo["estado"] == "RECHAZADO" and nuevo_cultivo["codigo"] == "V-31"


def test_registros_de_otra_cuenta_403(cliente, cabecera):
    f, c, cc = estructura(cliente, cabecera)
    otra = autorizar(registrar_y_activar(cliente, "pedro.gomez@correo.com", "Pedro Gómez", "Cultivo#2026b"))
    r = cliente.post(f"{API}/sync/push", headers=otra, json={"registros": [reg("finca", nid(), {"nombre": "Mía"}),
                                                                           reg("gasto", nid(), gasto(c), t=T2)]})
    assert r.status_code == 403 and r.json()["error"]["codigo"] == "E-02"
    r = cliente.post(f"{API}/sync/push", headers=otra, json={"registros": [reg("finca", f, {"nombre": "Robada"}, t=T2)]})
    assert r.status_code == 403
    assert cliente.get(f"{API}/sync/pull", headers=otra).json()["registros"] == []  # y la petición no guardó nada
    assert cliente.get(f"{API}/sync/pull", headers=cabecera).json()["registros"][0]["datos"]["nombre"] == "La Esperanza"


def test_pull_filtra_ordena_y_pagina(cliente, cabecera):
    f, c, cc = estructura(cliente, cabecera)
    for i in range(5):
        push(cliente, cabecera, reg("gasto", nid(), gasto(c, 1000 + i), t=f"2026-10-26T14:0{i}:00.000Z"))
    todo = cliente.get(f"{API}/sync/pull", headers=cabecera).json()
    assert len(todo["registros"]) == 8 and todo["hay_mas"] is False and todo["servidor_ahora"].endswith("Z")
    tiempos = [x["updated_at"] for x in todo["registros"]]
    assert tiempos == sorted(tiempos)
    pagina = cliente.get(f"{API}/sync/pull", headers=cabecera, params={"limite": 6}).json()
    assert len(pagina["registros"]) == 6 and pagina["hay_mas"] is True
    resto = cliente.get(f"{API}/sync/pull", headers=cabecera, params={"limite": 6, "desde": pagina["registros"][-1]["updated_at"]}).json()
    assert len(resto["registros"]) == 2 and resto["hay_mas"] is False
    ids = {x["id"] for x in pagina["registros"]} | {x["id"] for x in resto["registros"]}
    assert ids == {x["id"] for x in todo["registros"]}
    vacio = cliente.get(f"{API}/sync/pull", headers=cabecera, params={"desde": "2030-01-01T00:00:00Z"}).json()
    assert vacio["registros"] == []


def test_pull_parametros_invalidos(cliente, cabecera):
    assert cliente.get(f"{API}/sync/pull", headers=cabecera, params={"limite": 501}).json()["error"]["codigo"] == "E-03"
    assert cliente.get(f"{API}/sync/pull", headers=cabecera, params={"limite": 0}).status_code == 400
    assert cliente.get(f"{API}/sync/pull", headers=cabecera, params={"desde": "hoy"}).status_code == 400


def test_pull_con_empates_no_pierde_registros(cliente, cabecera):
    f, c, cc = estructura(cliente, cabecera)
    ids = [nid() for _ in range(6)]
    push(cliente, cabecera, *[reg("gasto", i, gasto(c), t=T2) for i in ids])
    pagina = cliente.get(f"{API}/sync/pull", headers=cabecera, params={"limite": 5, "desde": T1}).json()
    assert {x["id"] for x in pagina["registros"]} == set(ids) and pagina["hay_mas"] is False
