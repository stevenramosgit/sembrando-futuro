"""Ejecución del plan de pruebas (documento 14): reglas de validación V-01 a V-50, un caso con dato válido (OK) y otro con
dato inválido (ERR) por regla, contra el servicio real. Cada prueba se llama test_CP_V_<nn>_<OK|ERR> y deja su resultado en
tests/resultados_plan.json. Las reglas que solo existen en el dispositivo (V-20, V-30, V-43 a V-45) se ejecutan en
frontend/pruebas/e2e_plan.cjs."""
from datetime import timedelta

from sqlalchemy import select

from app import cli
from app.core.errores import ErrorApi
from app.core.mensajes import MENSAJES
from app.core.seguridad import ahora
from app.domain import fechas
from app.models.usuario import Otp, Token, Usuario
from tests.conftest import API, CLAVE, autorizar, obs, registrar_y_activar
from tests.test_cuentas import REGISTRO, registrar
from tests.test_sync import DATOS_CAFE, DATOS_CICLO, estructura, gasto, nid, push, reg

HOY = fechas.hoy()


def iso(d):
    return d.isoformat()


# ---------------------------------------------------------------- ayudas de cuentas
def error(r):
    return r.json()["error"]


def campos(r):
    return error(r).get("campos", {})


def pendiente(cliente, **cambios):
    r = registrar(cliente, **cambios)
    assert r.status_code == 201, r.text
    return autorizar(r.json()["token_activacion"])


def verificar(cliente, cab, codigo="482915"):
    return cliente.post(f"{API}/auth/otp/verificar", json={"codigo": codigo}, headers=cab)


def envejecer_otp(db, segundos):
    for o in db.scalars(select(Otp)):
        o.enviado_en = ahora() - timedelta(seconds=segundos)
    db.commit()


def ingreso(cliente, correo, clave):
    return cliente.post(f"{API}/auth/ingreso", json={"correo": correo, "clave": clave})


# ---------------------------------------------------------------- ayudas de sincronización
def finca_ciclo(cliente, cab, **ciclo):
    f, c = nid(), nid()
    res = push(cliente, cab, reg("finca", f, {"nombre": "La Esperanza"}),
               reg("ciclo", c, {"finca_id": f, **DATOS_CICLO, **{"fecha_siembra": "2026-03-15"}, **ciclo}))
    return f, c, res


def rechazo(res, codigo, indice=0):
    assert res[indice]["estado"] == "RECHAZADO" and res[indice]["codigo"] == codigo, res
    return res[indice]["mensaje"]


def aceptado(res, indice=0):
    assert res[indice]["estado"] == "ACEPTADO", res


def mensaje_ok(codigo, texto):
    assert texto == MENSAJES[codigo], (texto, MENSAJES[codigo])
    return texto


# ================================================================ cuenta (RF-02)
def _campo_registro(cliente, campo, bueno, malo, codigo, confirma=False):
    extra = {"correo_confirmacion": bueno} if confirma else {}
    r = registrar(cliente, **{campo: bueno}, **extra)
    assert r.status_code == 201, r.text
    return r, malo, codigo


def test_CP_V_01_OK(cliente):
    r = registrar(cliente, nombre="María Pérez")
    assert r.status_code == 201
    obs("Nombre «María Pérez»: cuenta PENDIENTE creada (201)")


def test_CP_V_01_ERR(cliente):
    r = registrar(cliente, nombre="aaaaa")
    assert r.status_code == 400 and campos(r)["nombre"]["codigo"] == "V-01"
    obs("Nombre «aaaaa»: 400 V-01 «" + mensaje_ok("V-01", campos(r)["nombre"]["mensaje"]) + "»; no se crea la cuenta")


def test_CP_V_02_OK(cliente):
    assert registrar(cliente, ubicacion="Caloto, Cauca").status_code == 201
    obs("Ubicación «Caloto, Cauca»: aceptada (201)")


def test_CP_V_02_ERR(cliente):
    r = registrar(cliente, ubicacion="0")
    assert r.status_code == 400 and campos(r)["ubicacion"]["codigo"] == "V-02"
    obs("Ubicación «0»: 400 V-02 «" + mensaje_ok("V-02", campos(r)["ubicacion"]["mensaje"]) + "»")


def test_CP_V_03_OK(cliente):
    r = registrar(cliente, correo="Maria@Correo.com", correo_confirmacion="maria@correo.com")
    assert r.status_code == 201 and r.json()["correo"] == "maria@correo.com"
    obs("Correo «Maria@Correo.com»: aceptado y guardado en minúsculas (maria@correo.com)")


def test_CP_V_03_ERR(cliente):
    r = registrar(cliente, correo="0@0", correo_confirmacion="0@0")
    assert r.status_code == 400 and campos(r)["correo"]["codigo"] == "V-03"
    obs("Correo «0@0»: 400 V-03 «" + mensaje_ok("V-03", campos(r)["correo"]["mensaje"]) + "»")


def test_CP_V_04_OK(cliente):
    assert registrar(cliente, correo="maria@correo.com", correo_confirmacion="MARIA@correo.com").status_code == 201
    obs("Confirmación idéntica sin distinguir mayúsculas: aceptada (201)")


def test_CP_V_04_ERR(cliente):
    r = registrar(cliente, correo="maria@correo.com", correo_confirmacion="maria@correo.co")
    assert r.status_code == 400 and campos(r)["correo_confirmacion"]["codigo"] == "V-04"
    obs("Confirmación «maria@correo.co»: 400 V-04 «" + mensaje_ok("V-04", campos(r)["correo_confirmacion"]["mensaje"]) + "»")


def test_CP_V_05_OK(cliente):
    registrar_y_activar(cliente)
    assert registrar(cliente, correo="ana@correo.com", correo_confirmacion="ana@correo.com").status_code == 201
    obs("Correo nuevo «ana@correo.com» con otra cuenta activa existente: aceptado (201)")


def test_CP_V_05_ERR(cliente):
    registrar_y_activar(cliente)
    r = registrar(cliente, correo="maria.perez@correo.com", correo_confirmacion="maria.perez@correo.com")
    assert r.status_code == 409 and error(r)["codigo"] == "V-05"
    obs("Correo de cuenta activa: 409 V-05 «" + mensaje_ok("V-05", error(r)["mensaje"]) + "»; no se crea otra cuenta")


def test_CP_V_06_OK(cliente):
    assert registrar(cliente).status_code == 201
    obs("Sin cuenta pendiente previa (el plan indica «—»): registro aceptado (201)")


def test_CP_V_06_ERR(cliente):
    registrar(cliente)
    r = registrar(cliente)
    assert r.status_code == 409 and error(r)["codigo"] == "V-06"
    obs("Correo con cuenta pendiente de menos de 24 h: 409 V-06 «" + mensaje_ok("V-06", error(r)["mensaje"]) + "»")


def test_CP_V_07_OK(cliente):
    assert registrar(cliente, clave="Cafe#Cauca2026").status_code == 201
    obs("Clave «Cafe#Cauca2026»: aceptada (201)")


def test_CP_V_07_ERR(cliente):
    r = registrar(cliente, clave="abcdefghij")
    assert r.status_code == 400 and campos(r)["clave"]["codigo"] == "V-07"
    obs("Clave «abcdefghij»: 400 V-07 «" + mensaje_ok("V-07", campos(r)["clave"]["mensaje"]) + "»")


def test_CP_V_08_OK(cliente):
    assert registrar(cliente, autoriza_datos=True).status_code == 201
    obs("Casilla de la Ley 1581 marcada: cuenta creada (201)")


def test_CP_V_08_ERR(cliente, db):
    r = registrar(cliente, autoriza_datos=False)
    assert r.status_code == 400 and campos(r)["autoriza_datos"]["codigo"] == "V-08"
    assert db.scalar(select(Usuario)) is None
    obs("Casilla sin marcar: 400 V-08 «" + mensaje_ok("V-08", campos(r)["autoriza_datos"]["mensaje"]) + "»; no se crea la cuenta")


# ================================================================ código OTP (RF-02)
def test_CP_V_09_OK(cliente):
    r = verificar(cliente, pendiente(cliente), "482915")
    assert r.status_code == 200 and r.json() == {"estado": "ACTIVA"}
    obs("Código «482915» (6 dígitos): cuenta ACTIVA (200)")


def test_CP_V_09_ERR(cliente):
    r = verificar(cliente, pendiente(cliente), "48A")
    assert r.status_code == 400 and error(r)["codigo"] == "V-09"
    obs("Código «48A»: 400 V-09 «" + mensaje_ok("V-09", error(r)["mensaje"]) + "»")


def test_CP_V_10_OK(cliente):
    r = verificar(cliente, pendiente(cliente))
    assert r.status_code == 200
    obs("Código enviado: cuenta ACTIVA (200)")


def test_CP_V_10_ERR(cliente):
    r = verificar(cliente, pendiente(cliente), "111111")
    assert r.status_code == 400 and error(r)["codigo"] == "V-10" and error(r)["intentos_restantes"] == 4
    obs("Código distinto al enviado: 400 V-10 con intentos_restantes = 4 «" + error(r)["mensaje"] + "»")


def test_CP_V_11_OK(cliente, db):
    cab = pendiente(cliente)
    envejecer_otp(db, 14 * 60 + 59)
    r = verificar(cliente, cab)
    assert r.status_code == 200
    obs("Código usado a los 14 min 59 s: cuenta ACTIVA (200)")


def test_CP_V_11_ERR(cliente, db):
    cab = pendiente(cliente)
    envejecer_otp(db, 15 * 60 + 1)
    r = verificar(cliente, cab)
    assert r.status_code == 400 and error(r)["codigo"] == "V-11"
    obs("Código usado a los 15 min 01 s: 400 V-11 «" + mensaje_ok("V-11", error(r)["mensaje"]) + "»")


def test_CP_V_12_OK(cliente):
    cab = pendiente(cliente)
    for _ in range(4):
        assert verificar(cliente, cab, "111111").status_code == 400
    assert verificar(cliente, cab).status_code == 200
    obs("El plan indica «—»; con 4 fallos el código correcto todavía activa la cuenta (200)")


def test_CP_V_12_ERR(cliente):
    cab = pendiente(cliente)
    for _ in range(4):
        verificar(cliente, cab, "111111")
    quinto = verificar(cliente, cab, "111111")
    sexto = verificar(cliente, cab, "482915")
    assert quinto.status_code == 423 and error(quinto)["codigo"] == "V-12" and sexto.status_code == 423
    obs("5.º fallo: 423 V-12 «" + mensaje_ok("V-12", error(quinto)["mensaje"]) + "»; un 6.º intento, aun con el código correcto, también da 423")


def test_CP_V_13_OK(cliente, db):
    cab = pendiente(cliente)
    envejecer_otp(db, 60)
    r = cliente.post(f"{API}/auth/otp/reenviar", headers=cab)
    assert r.status_code == 200
    obs("Reenvío a los 60 s: 200, código nuevo; reenvios_restantes = " + str(r.json()["reenvios_restantes"]))


def test_CP_V_13_ERR(cliente, db):
    cab = pendiente(cliente)
    envejecer_otp(db, 30)
    r = cliente.post(f"{API}/auth/otp/reenviar", headers=cab)
    assert r.status_code == 429 and error(r)["codigo"] == "V-13" and "retry-after" in r.headers
    obs("Reenvío a los 30 s: 429 V-13, espera restante " + str(error(r)["espera_segundos"]) + " s, cabecera Retry-After presente")


def test_CP_V_14_OK(cliente, db):
    cab = pendiente(cliente)
    for _ in range(3):
        envejecer_otp(db, 61)
        r = cliente.post(f"{API}/auth/otp/reenviar", headers=cab)
        assert r.status_code == 200
    assert r.json()["reenvios_restantes"] == 0
    obs("3.er reenvío: 200; reenvios_restantes = 0")


def test_CP_V_14_ERR(cliente, db):
    cab = pendiente(cliente)
    for _ in range(3):
        envejecer_otp(db, 61)
        cliente.post(f"{API}/auth/otp/reenviar", headers=cab)
    envejecer_otp(db, 61)
    r = cliente.post(f"{API}/auth/otp/reenviar", headers=cab)
    assert r.status_code == 429 and error(r)["codigo"] == "V-14"
    obs("4.º reenvío: 429 V-14 «" + mensaje_ok("V-14", error(r)["mensaje"]) + "»")


def test_CP_V_15_OK(cliente, db):
    cab = pendiente(cliente)
    u = db.scalar(select(Usuario))
    u.creado_en = ahora() - timedelta(hours=23)
    db.commit()
    assert verificar(cliente, cab).status_code == 200
    obs("Activación a las 23 h: cuenta ACTIVA (200)")


def test_CP_V_15_ERR(cliente, db):
    cab = pendiente(cliente)
    u = db.scalar(select(Usuario))
    u.creado_en = ahora() - timedelta(hours=25)
    db.commit()
    r = verificar(cliente, cab)
    assert r.status_code == 410 and error(r)["codigo"] == "V-15"
    db.expire_all()
    assert db.scalar(select(Usuario)) is None
    obs("Activación a las 25 h: 410 V-15 «" + mensaje_ok("V-15", error(r)["mensaje"]) + "»; la cuenta fue eliminada y el correo queda libre")


# ================================================================ ingreso (RF-03)
def test_CP_V_16_OK(cliente):
    registrar_y_activar(cliente)
    assert ingreso(cliente, "maria.perez@correo.com", CLAVE).status_code == 200
    obs("Correo y clave escritos: ingreso aceptado (200)")


def test_CP_V_16_ERR(cliente):
    registrar_y_activar(cliente)
    r = ingreso(cliente, "maria.perez@correo.com", "")
    assert r.status_code == 400 and error(r)["codigo"] == "V-16"
    obs("Clave vacía: 400 V-16 «" + mensaje_ok("V-16", error(r)["mensaje"]) + "»")


def test_CP_V_17_OK(cliente):
    registrar_y_activar(cliente)
    r = ingreso(cliente, "MARIA.PEREZ@correo.com", CLAVE)
    assert r.status_code == 200 and r.json()["usuario"]["rol"] == "AGRICULTOR"
    obs("Correo (sin distinguir mayúsculas) y clave correctos: 200 con token de sesión")


def test_CP_V_17_ERR(cliente):
    registrar_y_activar(cliente)
    r = ingreso(cliente, "maria.perez@correo.com", "Otra#Clave2026")
    assert r.status_code == 401 and error(r)["codigo"] == "V-17"
    obs("Clave equivocada: 401 V-17 «" + mensaje_ok("V-17", error(r)["mensaje"]) + "» (no revela si falló el correo o la clave)")


def test_CP_V_18_OK(cliente):
    registrar_y_activar(cliente)
    estados = [ingreso(cliente, "maria.perez@correo.com", "Otra#Clave2026").status_code for _ in range(4)]
    assert estados == [401] * 4
    assert ingreso(cliente, "maria.perez@correo.com", CLAVE).status_code == 200
    obs("4 fallos seguidos (401) y luego la clave correcta: ingresa (200)")


def test_CP_V_18_ERR(cliente):
    registrar_y_activar(cliente)
    for _ in range(4):
        ingreso(cliente, "maria.perez@correo.com", "Otra#Clave2026")
    r = ingreso(cliente, "maria.perez@correo.com", "Otra#Clave2026")
    assert r.status_code == 423 and error(r)["codigo"] == "V-18" and "bloqueado_hasta" in error(r)
    obs("5.º fallo: 423 V-18, bloqueo de 15 min hasta " + error(r)["bloqueado_hasta"] + " «" + error(r)["mensaje"] + "»")


def test_CP_V_19_OK(cliente):
    registrar_y_activar(cliente)
    assert ingreso(cliente, "maria.perez@correo.com", CLAVE).status_code == 200
    obs("Cuenta ACTIVA: inicia sesión (200)")


def test_CP_V_19_ERR(cliente):
    registrar(cliente)
    r = ingreso(cliente, REGISTRO["correo"].lower(), REGISTRO["clave"])
    assert r.status_code == 403 and error(r)["codigo"] == "V-19" and error(r)["accion"] == "VERIFICAR_OTP"
    obs("Cuenta PENDIENTE: 403 V-19 con accion VERIFICAR_OTP y token de activación «" + mensaje_ok("V-19", error(r)["mensaje"]) + "»")


# ================================================================ administrador (RF-01)
def test_CP_V_21_OK(db):
    cli.crear_admin(db, "admin.proyecto@correo.com", "Cafe#Cauca2026")
    assert db.scalar(select(Usuario).where(Usuario.rol == "ADMIN")) is not None
    obs("Primer administrador creado (rol ADMIN)")


def test_CP_V_21_ERR(db):
    cli.crear_admin(db, "admin.proyecto@correo.com", "Cafe#Cauca2026")
    try:
        cli.crear_admin(db, "otro.admin@correo.com", "Cafe#Cauca2026")
    except (ErrorApi, SystemExit) as e:
        texto = getattr(e, "mensaje", None) or str(e)
    else:
        raise AssertionError("se creó un segundo administrador")
    assert len(list(db.scalars(select(Usuario).where(Usuario.rol == "ADMIN")))) == 1
    obs("Segundo administrador: rechazado («" + texto + "»); sigue habiendo uno solo")


# ================================================================ finca y ciclo (RF-12 a RF-15)
def test_CP_V_22_OK(cliente, cabecera):
    f, c, res = finca_ciclo(cliente, cabecera, nombre_lote="Lote El Mirador")
    assert [r["estado"] for r in res] == ["ACEPTADO", "ACEPTADO"]
    obs("Nombre de lote «Lote El Mirador»: ciclo aceptado")


def test_CP_V_22_ERR(cliente, cabecera):
    f, c, res = finca_ciclo(cliente, cabecera, nombre_lote="0")
    assert res[0]["estado"] == "ACEPTADO"
    obs("Nombre de lote «0»: ciclo RECHAZADO V-22 «" + mensaje_ok("V-22", rechazo(res, "V-22", 1)) + "»")


def test_CP_V_24_OK(cliente, cabecera):
    f, c, res = finca_ciclo(cliente, cabecera, area_bruta_ha=1.0, area_no_sembrable_ha=0, area_efectiva_ha=1.0)
    aceptado(res, 1)
    obs("Área bruta 1,0 ha: aceptada")


def test_CP_V_24_ERR(cliente, cabecera):
    f, c, res = finca_ciclo(cliente, cabecera, area_bruta_ha=10000.0001, area_no_sembrable_ha=0)
    obs("Área bruta 10.000,0001 ha: RECHAZADO V-24 «" + mensaje_ok("V-24", rechazo(res, "V-24", 1)) + "»")


def test_CP_V_25_OK(cliente, cabecera):
    f, c, res = finca_ciclo(cliente, cabecera, pendiente_pct=15)
    aceptado(res, 1)
    obs("Pendiente 15 %: aceptada")


def test_CP_V_25_ERR(cliente, cabecera):
    f, c, res = finca_ciclo(cliente, cabecera, pendiente_pct=101)
    obs("Pendiente 101 %: RECHAZADO V-25 «" + mensaje_ok("V-25", rechazo(res, "V-25", 1)) + "»")


def test_CP_V_26_OK(cliente, cabecera):
    f, c, res = finca_ciclo(cliente, cabecera, area_bruta_ha=1.0, area_no_sembrable_ha=0.1)
    aceptado(res, 1)
    obs("No sembrable 0,1 ha con bruta 1,0 ha: aceptada")


def test_CP_V_26_ERR(cliente, cabecera):
    f, c, res = finca_ciclo(cliente, cabecera, area_bruta_ha=1.0, area_no_sembrable_ha=1.0)
    obs("No sembrable 1,0 ha con bruta 1,0 ha: RECHAZADO V-26 «" + mensaje_ok("V-26", rechazo(res, "V-26", 1)) + "»")


def test_CP_V_27_OK(cliente, cabecera):
    f, c, res = finca_ciclo(cliente, cabecera)
    r = push(cliente, cabecera, reg("ciclo_cultivo", nid(), {"ciclo_id": c, **DATOS_CAFE}))
    aceptado(r)
    obs("Cultivo Café del catálogo: aceptado")


def test_CP_V_27_ERR(cliente, cabecera):
    f, c, res = finca_ciclo(cliente, cabecera)
    r = push(cliente, cabecera, reg("ciclo_cultivo", nid(), {"ciclo_id": c, "marco": "cuadrado", "dist_a_m": 1.5}))
    obs("Ciclo sin cultivo: RECHAZADO V-27 «" + mensaje_ok("V-27", rechazo(r, "V-27")) + "»")


def test_CP_V_28_OK(cliente, cabecera):
    f, c, res = finca_ciclo(cliente, cabecera, fecha_siembra="2026-11-15")
    aceptado(res, 1)
    obs("Fecha 15/11/2026 (2026-11-15) como siembra: aceptada")


def test_CP_V_28_ERR(cliente, cabecera):
    f, c, res = finca_ciclo(cliente, cabecera, fecha_siembra="2026-02-31")
    obs("Fecha 31/02/2026: RECHAZADO V-28 «" + mensaje_ok("V-28", rechazo(res, "V-28", 1)) + "»")


def test_CP_V_29_OK(cliente, cabecera):
    f, c, res = finca_ciclo(cliente, cabecera, estado="CERRADO", fecha_cierre="2026-03-15")
    aceptado(res, 1)
    obs("Cierre igual a la siembra (2026-03-15): aceptado")


def test_CP_V_29_ERR(cliente, cabecera):
    f, c, res = finca_ciclo(cliente, cabecera, estado="CERRADO", fecha_cierre="2026-03-14")
    obs("Cierre un día antes de la siembra: RECHAZADO V-29 «" + mensaje_ok("V-29", rechazo(res, "V-29", 1)) + "»")


def test_CP_V_31_OK(cliente, cabecera):
    f, c, cc = estructura(cliente, cabecera)
    aceptado(push(cliente, cabecera, reg("gasto", nid(), gasto(c))))
    obs("Gasto en un ciclo ACTIVO: aceptado")


def test_CP_V_31_ERR(cliente, cabecera):
    f, c, cc = estructura(cliente, cabecera)
    push(cliente, cabecera, reg("ciclo", c, {"finca_id": f, **DATOS_CICLO, "estado": "CERRADO", "fecha_cierre": "2026-06-01"},
                                t="2026-10-26T13:05:00.000Z"))
    r = push(cliente, cabecera, reg("gasto", nid(), gasto(c), t="2026-10-26T13:10:00.000Z"))
    obs("Gasto en un ciclo CERRADO: RECHAZADO V-31 «" + mensaje_ok("V-31", rechazo(r, "V-31")) + "»")


def test_CP_V_32_OK(cliente, cabecera):
    f, c, res = finca_ciclo(cliente, cabecera)
    aceptado(push(cliente, cabecera, reg("ciclo_cultivo", nid(), {"ciclo_id": c, **DATOS_CAFE})))
    obs("Marco «cuadrado»: aceptado")


def test_CP_V_32_ERR(cliente, cabecera):
    f, c, res = finca_ciclo(cliente, cabecera)
    r = push(cliente, cabecera, reg("ciclo_cultivo", nid(), {"ciclo_id": c, "cultivo_codigo": "CAFE", "marco": "hexagonal", "dist_a_m": 1.5}))
    texto = mensaje_ok("V-32", rechazo(r, "V-32"))
    obs("Marco «hexagonal» (no permitido): RECHAZADO V-32 «" + texto + "». «Sin elegir» en la pantalla se prueba en e2e_plan.cjs")


def test_CP_V_33_OK(cliente, cabecera):
    f, c, res = finca_ciclo(cliente, cabecera)
    aceptado(push(cliente, cabecera, reg("ciclo_cultivo", nid(), {"ciclo_id": c, **DATOS_CAFE, "dist_a_m": 1.5})))
    obs("Distancia 1,5 m: aceptada")


def test_CP_V_33_ERR(cliente, cabecera):
    f, c, res = finca_ciclo(cliente, cabecera)
    r = push(cliente, cabecera, reg("ciclo_cultivo", nid(), {"ciclo_id": c, **DATOS_CAFE, "dist_a_m": 0}))
    obs("Distancia 0 m: RECHAZADO V-33 «" + mensaje_ok("V-33", rechazo(r, "V-33")) + "»")


def test_CP_V_34_OK():
    from app.domain import formulas
    r = formulas.matas_por_hectarea("cuadrado", 1.5, None, (1.0, 2.0))
    assert r == ("ok", 4444.45, None)
    obs("Distancia 1,5 m dentro del rango del café (1,0 a 2,0 m): " + str(r) + ", sin advertencia")


def test_CP_V_34_ERR():
    from app.domain import formulas
    r = formulas.matas_por_hectarea("cuadrado", 0.5, None, (1.0, 2.0))
    assert r[0] == "ok" and r[2] == "V-34"
    obs("Distancia 0,5 m (menor que el mínimo del café): el cálculo no se bloquea; devuelve " + str(r)
        + " (advertencia V-34 «" + MENSAJES["V-34"] + "»)")


# ================================================================ gasto, jornal e ingreso (RF-23 a RF-25)
def uno(cliente, cabecera, tipo, datos, t=None):
    f, c, cc = estructura(cliente, cabecera)
    return push(cliente, cabecera, reg(tipo, nid(), {"ciclo_id": c, **datos}))


def test_CP_V_35_OK(cliente, cabecera):
    aceptado(uno(cliente, cabecera, "gasto", {"fecha": iso(HOY), "categoria": "abonos", "valor_cop": 150000}))
    obs("Valor $150.000: gasto aceptado")


def test_CP_V_35_ERR(cliente, cabecera):
    r = uno(cliente, cabecera, "gasto", {"fecha": iso(HOY), "categoria": "abonos", "valor_cop": 50000001})
    obs("Valor $50.000.001: RECHAZADO V-35 «" + mensaje_ok("V-35", rechazo(r, "V-35")) + "»")


def test_CP_V_36_OK(cliente, cabecera):
    aceptado(uno(cliente, cabecera, "gasto", {"fecha": iso(HOY), "categoria": "abonos", "valor_cop": 150000}))
    obs("Valor 150000 (solo dígitos): aceptado")


def test_CP_V_36_ERR(cliente, cabecera):
    r = uno(cliente, cabecera, "gasto", {"fecha": iso(HOY), "categoria": "abonos", "valor_cop": "1e5"})
    obs("Valor «1e5»: RECHAZADO V-36 «" + mensaje_ok("V-36", rechazo(r, "V-36")) + "»")


def test_CP_V_37_OK(cliente, cabecera):
    aceptado(uno(cliente, cabecera, "gasto", {"fecha": iso(HOY), "categoria": "abonos", "valor_cop": 1000}))
    obs("Categoría «abonos»: aceptada")


def test_CP_V_37_ERR(cliente, cabecera):
    r = uno(cliente, cabecera, "gasto", {"fecha": iso(HOY), "categoria": None, "valor_cop": 1000})
    obs("Categoría sin elegir: RECHAZADO V-37 «" + mensaje_ok("V-37", rechazo(r, "V-37")) + "»")


def test_CP_V_38_OK(cliente, cabecera):
    datos = {"fecha": iso(HOY), "categoria": "abonos", "valor_cop": 1000, "observaciones": "Abono para el ciclo 1"}
    aceptado(uno(cliente, cabecera, "gasto", datos))
    obs("Observaciones «Abono para el ciclo 1»: aceptadas")


def test_CP_V_38_ERR(cliente, cabecera):
    r = uno(cliente, cabecera, "gasto", {"fecha": iso(HOY), "categoria": "abonos", "valor_cop": 1000, "observaciones": "a" * 151})
    obs("Observaciones de 151 caracteres: RECHAZADO V-38 «" + mensaje_ok("V-38", rechazo(r, "V-38")) + "»")


def test_CP_V_39_OK(cliente, cabecera):
    aceptado(uno(cliente, cabecera, "jornal", {"fecha": iso(HOY), "jornales": 1.5, "valor_diario_cop": 60000}))
    obs("Jornales 1,5: aceptado")


def test_CP_V_39_ERR(cliente, cabecera):
    r = uno(cliente, cabecera, "jornal", {"fecha": iso(HOY), "jornales": 1.25, "valor_diario_cop": 60000})
    obs("Jornales 1,25: RECHAZADO V-39 «" + mensaje_ok("V-39", rechazo(r, "V-39")) + "»")


def test_CP_V_40_OK(cliente, cabecera):
    aceptado(uno(cliente, cabecera, "jornal", {"fecha": iso(HOY), "jornales": 1, "valor_diario_cop": 60000}))
    obs("Valor diario $60.000: aceptado")


def test_CP_V_40_ERR(cliente, cabecera):
    r = uno(cliente, cabecera, "jornal", {"fecha": iso(HOY), "jornales": 1, "valor_diario_cop": 0})
    obs("Valor diario $0: RECHAZADO V-40 «" + mensaje_ok("V-40", rechazo(r, "V-40")) + "»")


def _ingreso(cliente, cabecera, **d):
    return uno(cliente, cabecera, "ingreso", {"fecha": iso(HOY), "cultivo_codigo": "CAFE", "cantidad": 25, "precio_unitario_cop": 180000,
                                              "unidad_comercial": "carga (125 kg de café pergamino seco)", **d})


def test_CP_V_41_OK(cliente, cabecera):
    aceptado(_ingreso(cliente, cabecera, cantidad=25))
    obs("Cantidad 25: ingreso aceptado")


def test_CP_V_41_ERR(cliente, cabecera):
    r = _ingreso(cliente, cabecera, cantidad=10001)
    obs("Cantidad 10.001: RECHAZADO V-41 «" + mensaje_ok("V-41", rechazo(r, "V-41")) + "»")


def test_CP_V_42_OK(cliente, cabecera):
    aceptado(_ingreso(cliente, cabecera, precio_unitario_cop=180000))
    obs("Precio $180.000: aceptado")


def test_CP_V_42_ERR(cliente, cabecera):
    r = _ingreso(cliente, cabecera, precio_unitario_cop=0)
    obs("Precio $0: RECHAZADO V-42 «" + mensaje_ok("V-42", rechazo(r, "V-42")) + "»")


def test_CP_V_46_OK(cliente, cabecera):
    assert cliente.get(f"{API}/sync/pull", headers=cabecera).status_code == 200
    obs("Sesión vigente: la sincronización responde 200")


def test_CP_V_46_ERR(cliente, cabecera, db):
    for t in db.scalars(select(Token)):
        t.expira_en = ahora() - timedelta(days=1)
    db.commit()
    r = cliente.get(f"{API}/sync/pull", headers=cabecera)
    assert r.status_code == 401 and error(r)["codigo"] == "V-46"
    obs("Sesión de más de 30 días: 401 V-46 «" + mensaje_ok("V-46", error(r)["mensaje"]) + "». La conservación de datos locales se prueba en e2e_plan.cjs")


def test_CP_V_47_OK(cliente, cabecera):
    aceptado(uno(cliente, cabecera, "gasto", {"fecha": iso(HOY), "categoria": "abonos", "valor_cop": 1000}))
    obs("Fecha de hoy: gasto aceptado")


def test_CP_V_47_ERR(cliente, cabecera):
    r = uno(cliente, cabecera, "gasto", {"fecha": iso(HOY + timedelta(days=1)), "categoria": "abonos", "valor_cop": 1000})
    obs("Fecha de mañana: RECHAZADO V-47 «" + mensaje_ok("V-47", rechazo(r, "V-47")) + "»")


def test_CP_V_48_OK(cliente, cabecera):
    f, c, res = finca_ciclo(cliente, cabecera, fecha_siembra="2026-11-15")
    aceptado(res, 1)
    obs("Siembra 15/11/2026: aceptada")


def test_CP_V_48_ERR(cliente, cabecera):
    f, c, res = finca_ciclo(cliente, cabecera, fecha_siembra="2019-01-01")
    obs("Siembra 01/01/2019: RECHAZADO V-48 «" + mensaje_ok("V-48", rechazo(res, "V-48", 1)) + "»")


def test_CP_V_49_OK(cliente, cabecera):
    f, c, res = finca_ciclo(cliente, cabecera, vigencia_anios=7)
    aceptado(res, 1)
    obs("Vigencia 7 años: aceptada")


def test_CP_V_49_ERR(cliente, cabecera):
    textos = []
    for valor in (51, 2.5):
        f, c, res = finca_ciclo(cliente, cabecera, vigencia_anios=valor)
        textos.append(f"{valor}: " + mensaje_ok("V-49", rechazo(res, "V-49", 1)))
    obs("Vigencia 51 y 2,5: RECHAZADO V-49 en ambos (" + "; ".join(textos) + ")")


def test_CP_V_50_OK(cliente, cabecera):
    f, c, cc = estructura(cliente, cabecera)
    datos = {"ciclo_id": c, "cultivo_codigo": "PLATANO", "marco": "rectangular", "dist_a_m": 3.0, "dist_b_m": 2.0}
    aceptado(push(cliente, cabecera, reg("ciclo_cultivo", nid(), datos)))
    obs("Plátano (nuevo en el ciclo): aceptado")


def test_CP_V_50_ERR(cliente, cabecera):
    f, c, cc = estructura(cliente, cabecera)
    r = push(cliente, cabecera, reg("ciclo_cultivo", nid(), {"ciclo_id": c, **DATOS_CAFE}))
    obs("Café repetido en el mismo ciclo: RECHAZADO V-50 «" + mensaje_ok("V-50", rechazo(r, "V-50")) + "»")
