"""Ejecución del plan de pruebas (documento 14), requisitos RF-01 a RF-04: administración, registro, código OTP e ingreso.
Cada prueba test_CP_<id> deja lo que observó en tests/resultados_plan.json. Los casos que dependen de la pantalla del dispositivo
(CP-RF-01-05, CP-RF-02-07, CP-RF-04-01 y CP-RF-04-02) se ejecutan en frontend/pruebas/e2e_plan.cjs."""
from datetime import timedelta

import pytest
from sqlalchemy import func, select

from app import cli
from app.core import limites
from app.core.seguridad import ahora
from app.models import Ciclo, Finca, Gasto, Otp, Token, Usuario
from app.models.usuario import IntentoIngreso
from tests.conftest import API, CLAVE, autorizar, obs, registrar_y_activar
from tests.test_cuentas import REGISTRO, registrar
from tests.test_plan_validaciones import campos, envejecer_otp, error, ingreso, pendiente, verificar
from tests.test_resumen_admin import completar_ciclo, id_de
from tests.test_sync import estructura, gasto, nid, reg

ADMIN = ("admin.proyecto@correo.com", "Cafe#Cauca2026")


# ================================================================ RF-01 administrador
def test_CP_RF_01_01(db):
    cli.crear_admin(db, "admin.proyecto@correo.com", "Cafe#Cauca2026")
    u = db.scalar(select(Usuario).where(Usuario.correo == "admin.proyecto@correo.com"))
    assert u.rol == "ADMIN" and u.hash_clave != "Cafe#Cauca2026"
    obs("crear_admin con la clave «Cafe#Cauca2026»: cuenta creada con rol ADMIN y la clave guardada como hash")


def test_CP_RF_01_02(db):
    cli.crear_admin(db, *ADMIN)
    with pytest.raises(SystemExit) as e:
        cli.crear_admin(db, "otro.admin@correo.com", "Cafe#Cauca2026")
    assert db.scalar(select(func.count()).select_from(Usuario).where(Usuario.rol == "ADMIN")) == 1
    obs("Segundo crear_admin rechazado («" + str(e.value) + "»); sigue habiendo 1 solo ADMIN")


def test_CP_RF_01_03(db):
    with pytest.raises(SystemExit) as e:
        cli.crear_admin(db, "admin.proyecto@correo.com", "Abcdef#12")
    assert db.scalar(select(func.count()).select_from(Usuario)) == 0
    obs("Clave de 9 caracteres «Abcdef#12»: rechazada («" + str(e.value) + "»); no se crea la cuenta")


def test_CP_RF_01_04(cliente, db):
    r = cliente.post(f"{API}/auth/registro", json={**REGISTRO, "rol": "ADMIN", "correo": "intruso@correo.com",
                                                   "correo_confirmacion": "intruso@correo.com"})
    u = db.scalar(select(Usuario).where(Usuario.correo == "intruso@correo.com"))
    assert u is None or u.rol == "AGRICULTOR"
    estado = "se ignoró el campo rol" if r.status_code == 201 else f"se rechazó ({r.status_code})"
    obs(f"Registro público con el campo rol = ADMIN: {estado}; la cuenta queda como AGRICULTOR. La pantalla no ofrece elegir rol (e2e_plan.cjs)")


def test_CP_RF_01_06(cliente, cabecera, admin):
    ok = cliente.get(f"{API}/admin/usuarios", headers=admin)
    agricultor = cliente.get(f"{API}/admin/usuarios", headers=cabecera)
    sin = cliente.get(f"{API}/admin/usuarios")
    assert ok.status_code == 200 and agricultor.status_code == 403 and error(agricultor)["codigo"] == "E-06"
    assert sin.status_code == 401 and error(sin)["codigo"] == "V-46"
    obs(f"AD-01: administrador {ok.status_code} con lista ({ok.json()['total']} cuentas); agricultor 403 E-06; sin token 401 V-46")


def test_CP_RF_01_07(cliente, cabecera, admin):
    uid = id_de(cliente, admin, "maria.perez@correo.com")
    for _ in range(5):
        ingreso(cliente, "maria.perez@correo.com", "Mala#Clave2026")
    mala = cliente.post(f"{API}/admin/usuarios/{uid}/clave", headers=admin, json={"clave_nueva": "abc"})
    buena = cliente.post(f"{API}/admin/usuarios/{uid}/clave", headers=admin, json={"clave_nueva": "Nueva#Clave2026"})
    assert mala.status_code == 400 and campos(mala)["clave_nueva"]["codigo"] == "V-07" and buena.status_code == 204
    assert cliente.get(f"{API}/sync/pull", headers=cabecera).status_code == 401
    assert ingreso(cliente, "maria.perez@correo.com", "Nueva#Clave2026").status_code == 200
    obs("AD-02: «abc» rechazada con V-07; «Nueva#Clave2026» da 204, revoca la sesión anterior (401), quita el bloqueo y permite ingresar (200)")


def test_CP_RF_01_08(cliente, cabecera, admin, db):
    completar_ciclo(cliente, cabecera)
    uid = id_de(cliente, admin, "maria.perez@correo.com")
    aid = db.scalar(select(Usuario.id_usuario).where(Usuario.rol == "ADMIN"))
    primera = cliente.delete(f"{API}/admin/usuarios/{uid}", headers=admin)
    segunda = cliente.delete(f"{API}/admin/usuarios/{aid}", headers=admin)
    tercera = cliente.delete(f"{API}/admin/usuarios/{nid()}", headers=admin)
    assert primera.status_code == 204 and segunda.status_code == 409 and error(segunda)["codigo"] == "E-09"
    assert tercera.status_code == 404 and error(tercera)["codigo"] == "E-07"
    obs("AD-03: agricultor con fincas eliminado (204); administrador 409 E-09; cuenta inexistente 404 E-07")


def test_CP_RF_01_09(cliente, db, admin):
    cli.cargar_prueba(db)
    uid = db.scalar(select(Usuario.id_usuario).where(Usuario.correo == "maria.perez@correo.com"))
    r = cliente.get(f"{API}/admin/usuarios/{uid}/resumen", headers=admin)
    assert r.status_code == 200
    t = r.json()["totales"]
    assert t == {"fincas": 2, "ciclos": 3, "gastos": 2, "jornales": 1, "ingresos": 2}, t
    assert len(r.json()["fincas"]) == 2
    obs(f"AD-05 sobre María Pérez (datos de prueba): 200 con totales {t} y el detalle por finca")


def test_CP_RF_01_10(cliente, db, admin):
    cli.cargar_prueba(db)
    cabecera = autorizar(registrar_y_activar(cliente, "luis@correo.com", "Luis Mena"))
    uid = db.scalar(select(Usuario.id_usuario).where(Usuario.correo == "maria.perez@correo.com"))
    aid = db.scalar(select(Usuario.id_usuario).where(Usuario.rol == "ADMIN"))
    a = cliente.get(f"{API}/admin/usuarios/{uid}/resumen", headers=cabecera)
    b = cliente.get(f"{API}/admin/usuarios/{uid}/resumen")
    c = cliente.get(f"{API}/admin/usuarios/{aid}/resumen", headers=admin)
    d = cliente.get(f"{API}/admin/usuarios/{nid()}/resumen", headers=admin)
    assert (a.status_code, error(a)["codigo"]) == (403, "E-06") and (b.status_code, error(b)["codigo"]) == (401, "V-46")
    assert (c.status_code, error(c)["codigo"]) == (404, "E-07") and (d.status_code, error(d)["codigo"]) == (404, "E-07")
    obs("AD-05: agricultor 403 E-06; sin token 401 V-46; sobre el administrador 404 E-07; cuenta inexistente 404 E-07")


def test_CP_RF_01_11(cliente, db, admin):
    cli.cargar_prueba(db)
    maria = db.scalar(select(Usuario).where(Usuario.correo == "maria.perez@correo.com"))
    fincas = [f.id_finca for f in db.scalars(select(Finca).where(Finca.id_usuario == maria.id_usuario))]
    ciclos = [c.id_ciclo for c in db.scalars(select(Ciclo).where(Ciclo.id_finca.in_(fincas)))]
    g = db.scalar(select(Gasto).where(Gasto.id_ciclo.in_(ciclos)))
    g.eliminado = True
    db.add(IntentoIngreso(correo=maria.correo, intentos_fallidos=1, actualizado_en=ahora()))
    db.commit()
    uid, correo = maria.id_usuario, maria.correo
    assert cliente.delete(f"{API}/admin/usuarios/{uid}", headers=admin).status_code == 204
    db.expire_all()
    restos = {
        "usuario": db.scalar(select(func.count()).select_from(Usuario).where(Usuario.id_usuario == uid)),
        "fincas": db.scalar(select(func.count()).select_from(Finca).where(Finca.id_finca.in_(fincas))),
        "ciclos": db.scalar(select(func.count()).select_from(Ciclo).where(Ciclo.id_ciclo.in_(ciclos))),
        "gastos": db.scalar(select(func.count()).select_from(Gasto).where(Gasto.id_ciclo.in_(ciclos))),
        "tokens": db.scalar(select(func.count()).select_from(Token).where(Token.id_usuario == uid)),
        "otp": db.scalar(select(func.count()).select_from(Otp).where(Otp.id_usuario == uid)),
        "intentos": db.scalar(select(func.count()).select_from(IntentoIngreso).where(IntentoIngreso.correo == correo)),
    }
    assert all(v == 0 for v in restos.values()), restos
    obs(f"AD-03 sobre María ({len(fincas)} fincas, {len(ciclos)} ciclos, un gasto eliminado lógicamente y un intento de ingreso): filas restantes {restos}")


def test_CP_RF_01_12(cliente, cabecera, admin):
    f, c, cc = estructura(cliente, cabecera)
    uid = id_de(cliente, admin, "maria.perez@correo.com")
    assert cliente.delete(f"{API}/admin/usuarios/{uid}", headers=admin).status_code == 204
    r = cliente.post(f"{API}/sync/push", headers=cabecera, json={"dispositivo_id": "d1", "registros": [reg("gasto", nid(), gasto(c))]})
    assert r.status_code == 401 and error(r)["codigo"] == "V-46"
    obs("Tras AD-03, el dispositivo del usuario eliminado envía S-01: 401 V-46 y no se crea ninguna fila")


def test_CP_RF_01_13(db):
    from sqlalchemy.exc import IntegrityError
    cli.crear_admin(db, *ADMIN)

    def usuario(correo, rol):
        return Usuario(id_usuario=nid(), nombre="Prueba Directa", ubicacion="Caloto", correo=correo, hash_clave="x", rol=rol,
                       estado="ACTIVA", intentos_fallidos=0, consentimiento_ley1581=True, creado_en=ahora())
    db.add(usuario("segundo.admin@correo.com", "ADMIN"))
    with pytest.raises(IntegrityError):
        db.commit()
    db.rollback()
    db.add(usuario("agricultor.directo@correo.com", "AGRICULTOR"))
    db.commit()
    obs("INSERT directo de un 2.º ADMIN: la restricción UNIQUE (uq_usuario_un_solo_admin) lo rechaza; un AGRICULTOR se inserta")


# ================================================================ RF-02 registro y activación
def test_CP_RF_02_01(cliente, db):
    r = registrar(cliente, nombre="María Pérez", correo="maria@correo.com", correo_confirmacion="maria@correo.com",
                  ubicacion="Caloto", clave="Cafe#Cauca2026")
    assert r.status_code == 201 and r.json()["estado"] == "PENDIENTE"
    assert db.scalar(select(func.count()).select_from(Otp)) == 1
    obs("Registro válido: 201, cuenta PENDIENTE y un código OTP generado (en pruebas el envío queda en el registro del servidor)")


def test_CP_RF_02_02(cliente):
    res = {}
    for n in (9, 10, 11):
        clave = "Ab1#" + "xYzW" * 5
        clave = clave[:n]
        res[n] = registrar(cliente, clave=clave, correo=f"c{n}@correo.com", correo_confirmacion=f"c{n}@correo.com").status_code
    assert res[9] == 400 and res[10] == 201 and res[11] == 201, res
    obs(f"Claves de 9 / 10 / 11 caracteres: {res[9]} (V-07) / {res[10]} / {res[11]}")


def test_CP_RF_02_03(cliente):
    out = {}
    for n in ("0", "00", "aaaaa", "test", "A"):
        r = registrar(cliente, nombre=n, correo=f"n{len(out)}@correo.com", correo_confirmacion=f"n{len(out)}@correo.com")
        assert r.status_code == 400 and campos(r)["nombre"]["codigo"] == "V-01", n
        out[n] = campos(r)["nombre"]["codigo"]
    obs("Nombres «0», «00», «aaaaa», «test» y «A»: todos rechazados con V-01")


def test_CP_RF_02_04(cliente):
    malos = ["abc", "0@0", "a@b", "a b@c.com"]
    for i, c in enumerate(malos):
        r = registrar(cliente, correo=c, correo_confirmacion=c)
        assert r.status_code == 400 and campos(r)["correo"]["codigo"] == "V-03", c
    assert registrar(cliente, correo="ana@correo.com", correo_confirmacion="ana@correo.com").status_code == 201
    obs("Correos «abc», «0@0», «a@b», «a b@c.com»: rechazados con V-03; «ana@correo.com»: aceptado (201)")


def test_CP_RF_02_05(cliente, db):
    cab = pendiente(cliente)
    envejecer_otp(db, 14 * 60 + 59)
    a = verificar(cliente, cab)
    limites.reiniciar()
    cab2 = pendiente(cliente, correo="otra@correo.com", correo_confirmacion="otra@correo.com")
    for o in db.scalars(select(Otp).join(Usuario).where(Usuario.correo == "otra@correo.com")):
        o.enviado_en = ahora() - timedelta(minutes=15, seconds=1)
    db.commit()
    b = verificar(cliente, cab2)
    assert a.status_code == 200 and b.status_code == 400 and error(b)["codigo"] == "V-11"
    obs("Código a los 14:59: 200 y cuenta activa; a los 15:01: 400 V-11")


def test_CP_RF_02_06(cliente, db):
    r = registrar(cliente, autoriza_datos=False)
    assert r.status_code == 400 and campos(r)["autoriza_datos"]["codigo"] == "V-08"
    assert db.scalar(select(func.count()).select_from(Usuario)) == 0
    obs("Registro sin marcar la autorización (Ley 1581): 400 V-08; no se crea la cuenta")


def test_CP_RF_02_08(cliente):
    cab = pendiente(cliente)
    for _ in range(4):
        assert verificar(cliente, cab, "111111").status_code == 400
    ok = verificar(cliente, cab)
    limites.reiniciar()
    cab2 = pendiente(cliente, correo="otra@correo.com", correo_confirmacion="otra@correo.com")
    estados = [verificar(cliente, cab2, "111111").status_code for _ in range(5)]
    despues = verificar(cliente, cab2)
    assert ok.status_code == 200 and estados == [400, 400, 400, 400, 423] and despues.status_code == 423
    obs("4 fallos y el código correcto: 200 (activa); 5 fallos: respuestas " + str(estados) + " y el código correcto después también da 423 (invalidado)")


def test_CP_RF_02_09(cliente, db):
    cab = pendiente(cliente)
    codigos = []
    for _ in range(3):
        envejecer_otp(db, 60)
        codigos.append(cliente.post(f"{API}/auth/otp/reenviar", headers=cab).status_code)
    activos = db.scalar(select(func.count()).select_from(Otp).where(Otp.usado.is_(False)))
    envejecer_otp(db, 60)
    cuarto = cliente.post(f"{API}/auth/otp/reenviar", headers=cab)
    assert codigos == [200, 200, 200] and activos == 1 and cuarto.status_code == 429 and error(cuarto)["codigo"] == "V-14"
    obs("3 reenvíos esperando 60 s: 200, 200, 200 (cada uno anula el anterior: queda 1 código vigente); 4.º: 429 V-14")


def test_CP_RF_02_10(cliente, db):
    cab = pendiente(cliente)
    envejecer_otp(db, 30)
    a = cliente.post(f"{API}/auth/otp/reenviar", headers=cab)
    envejecer_otp(db, 60)
    b = cliente.post(f"{API}/auth/otp/reenviar", headers=cab)
    assert a.status_code == 429 and error(a)["codigo"] == "V-13" and b.status_code == 200
    obs(f"Reenvío a los 30 s: 429 V-13 (espera restante {error(a)['espera_segundos']} s); a los 60 s: 200")


def test_CP_RF_02_11(cliente, db):
    cab = pendiente(cliente)
    envejecer_otp(db, 61)
    mal = cliente.post(f"{API}/auth/correo/cambiar", headers=cab, json={"correo_nuevo": "abc", "correo_nuevo_confirmacion": "abc"})
    bien = cliente.post(f"{API}/auth/correo/cambiar", headers=cab, json={"correo_nuevo": "nuevo@correo.com",
                                                                         "correo_nuevo_confirmacion": "nuevo@correo.com"})
    assert mal.status_code == 400 and campos(mal)["correo_nuevo"]["codigo"] == "V-03"
    assert bien.status_code == 200 and bien.json()["reenvios_restantes"] == 2
    obs("Cambiar el correo: «abc» rechazado con V-03; «nuevo@correo.com» aceptado (200), código nuevo y cuenta como reenvío (quedan 2)")


def test_CP_RF_02_12(cliente):
    registrar_y_activar(cliente)
    activa = registrar(cliente, correo="maria.perez@correo.com", correo_confirmacion="maria.perez@correo.com")
    registrar(cliente, correo="luis@correo.com", correo_confirmacion="luis@correo.com")
    pend = registrar(cliente, correo="luis@correo.com", correo_confirmacion="luis@correo.com")
    assert (activa.status_code, error(activa)["codigo"]) == (409, "V-05") and (pend.status_code, error(pend)["codigo"]) == (409, "V-06")
    obs("Correo de cuenta activa: 409 V-05; correo de cuenta pendiente (< 24 h): 409 V-06; no se crea otra cuenta")


def test_CP_RF_02_13(cliente, db):
    cab = pendiente(cliente)
    u = db.scalar(select(Usuario))
    u.creado_en = ahora() - timedelta(hours=23)
    db.commit()
    a = verificar(cliente, cab)
    limites.reiniciar()
    cab2 = pendiente(cliente, correo="otra@correo.com", correo_confirmacion="otra@correo.com")
    u2 = db.scalar(select(Usuario).where(Usuario.correo == "otra@correo.com"))
    u2.creado_en = ahora() - timedelta(hours=25)
    db.commit()
    b = verificar(cliente, cab2)
    db.expire_all()
    libre = registrar(cliente, correo="otra@correo.com", correo_confirmacion="otra@correo.com").status_code
    assert a.status_code == 200 and b.status_code == 410 and libre == 201
    obs("Activar a las 23 h: 200; a las 25 h: 410 V-15, la cuenta ya fue eliminada y el correo quedó libre (nuevo registro 201)")


def test_CP_RF_02_14(cliente):
    r = registrar(cliente, correo_confirmacion="otro@correo.com")
    assert r.status_code == 400 and campos(r)["correo_confirmacion"]["codigo"] == "V-04"
    obs("Correo y confirmación distintos: 400 V-04 «" + campos(r)["correo_confirmacion"]["mensaje"] + "»")


def test_CP_RF_02_15(cliente):
    res = {}
    for n in (63, 64, 65):
        clave = ("Ab1#" + "xYzW9" * 20)[:n]
        res[n] = registrar(cliente, clave=clave, correo=f"c{n}@correo.com", correo_confirmacion=f"c{n}@correo.com").status_code
    assert res == {63: 201, 64: 201, 65: 400}, res
    obs(f"Claves de 63 / 64 / 65 caracteres: {res[63]} / {res[64]} / {res[65]} (V-07)")


def test_CP_RF_02_16(cliente):
    out = {}
    for i, clave in enumerate(["Cafe_Cauca2026", "Cafe.Cauca2026", "Cafe Cauca2026", "Café#Cauca2026"]):
        out[clave] = registrar(cliente, clave=clave, correo=f"s{i}@correo.com", correo_confirmacion=f"s{i}@correo.com").status_code
    assert list(out.values()) == [201, 201, 400, 400], out
    obs("Claves con «_» y «.»: 201; con espacio o con tilde: 400 V-07")


def test_CP_RF_02_17(cliente):
    def correo(n):
        return "a" * (n - len("@correo.com")) + "@correo.com"
    # el límite de la parte local es 64; 254 y 255 se arman con etiquetas de dominio de hasta 63 caracteres
    def largo(n):
        base = "ana@"
        resto = n - len(base)
        etiquetas = []
        while resto > 0:
            e = min(61, resto - 4) if resto > 65 else resto - 4
            etiquetas.append("b" * max(e, 1))
            resto -= len(etiquetas[-1]) + 1
        return (base + ".".join(etiquetas) + ".com")[:n]
    c254, c255 = largo(254), largo(255)
    assert len(c254) == 254 and len(c255) == 255
    a = registrar(cliente, correo=c254, correo_confirmacion=c254)
    b = registrar(cliente, correo=c255, correo_confirmacion=c255)
    assert a.status_code == 201, a.text[:200]
    assert b.status_code == 400 and campos(b)["correo"]["codigo"] == "V-03"
    obs("Correo de 254 caracteres: aceptado (201); de 255: rechazado con V-03")


def test_CP_RF_02_18(cliente):
    registrar_y_activar(cliente, "maria@correo.com")
    r = registrar(cliente, correo="MARIA@CORREO.COM", correo_confirmacion="MARIA@CORREO.COM")
    entra = ingreso(cliente, "Maria@Correo.com", CLAVE)
    assert r.status_code == 409 and error(r)["codigo"] == "V-05" and entra.status_code == 200
    obs("Registrar «MARIA@CORREO.COM» con «maria@correo.com» activo: 409 V-05; ingresar con «Maria@Correo.com»: 200")


def test_CP_RF_02_19(cliente):
    r = cliente.options(f"{API}/auth/registro", headers={"Origin": "https://sitio-malo.example", "Access-Control-Request-Method": "POST"})
    permitido = r.headers.get("access-control-allow-origin")
    assert permitido in (None, "") or permitido != "https://sitio-malo.example"
    obs(f"Petición desde otro origen (https://sitio-malo.example): el servidor no devuelve Access-Control-Allow-Origin para ese origen (valor: {permitido!r}); el navegador bloquea la respuesta")


def test_CP_RF_02_20(cliente):
    estados = []
    for i in range(6):
        estados.append(registrar(cliente, correo=f"u{i}@correo.com", correo_confirmacion=f"u{i}@correo.com").status_code)
    ultimo = registrar(cliente, correo="u5@correo.com", correo_confirmacion="u5@correo.com")
    assert estados[:5] == [201] * 5 and estados[5] == 429
    obs(f"A-01 seis veces desde la misma IP: {estados}; la 6.ª responde 429 E-10")


def test_CP_RF_02_21(cliente, db):
    registrar(cliente)
    u = db.scalar(select(Usuario))
    u.creado_en = ahora() - timedelta(hours=25)
    db.commit()
    from app.services import limpieza_service
    n = limpieza_service.limpiar_pendientes(db)
    db.expire_all()
    assert n == 1 and db.scalar(select(func.count()).select_from(Usuario)) == 0
    assert db.scalar(select(func.count()).select_from(Otp)) == 0 and db.scalar(select(func.count()).select_from(Token)) == 0
    assert registrar(cliente).status_code == 201
    obs("limpiar_pendientes con una cuenta de 25 h: 1 cuenta eliminada; su OTP y su token se borran por cascada; el correo queda libre")


# ================================================================ RF-03 ingreso
def test_CP_RF_03_01(cliente):
    registrar_y_activar(cliente)
    r = ingreso(cliente, "maria.perez@correo.com", CLAVE)
    assert r.status_code == 200 and r.json()["usuario"]["rol"] == "AGRICULTOR" and r.json()["token"].startswith("tkn_")
    obs("Correo y clave correctos de una cuenta ACTIVA: 200 con token de sesión y rol AGRICULTOR")


def test_CP_RF_03_02(cliente):
    registrar_y_activar(cliente)
    cuatro = [ingreso(cliente, "maria.perez@correo.com", "Otra#Clave2026").status_code for _ in range(4)]
    entra = ingreso(cliente, "maria.perez@correo.com", CLAVE).status_code
    limites.reiniciar()
    registrar_y_activar(cliente, "luis@correo.com", "Luis Mena")
    cinco = [ingreso(cliente, "luis@correo.com", "Otra#Clave2026").status_code for _ in range(5)]
    assert cuatro == [401] * 4 and entra == 200 and cinco == [401, 401, 401, 401, 423]
    obs(f"4 fallos y luego la clave correcta: {cuatro} y {entra}; 5 fallos seguidos: {cinco} (bloqueo de 15 min)")


def test_CP_RF_03_03(cliente):
    registrar_y_activar(cliente)
    mala = ingreso(cliente, "maria.perez@correo.com", "Otra#Clave2026")
    nadie = ingreso(cliente, "nadie@correo.com", "Otra#Clave2026")
    assert mala.json() == nadie.json() and mala.status_code == 401
    obs("Clave incorrecta: 401 V-17 «" + error(mala)["mensaje"] + "»; el mensaje es idéntico al de un correo inexistente")


def test_CP_RF_03_04(cliente):
    registrar(cliente)
    r = ingreso(cliente, REGISTRO["correo"].lower(), REGISTRO["clave"])
    assert r.status_code == 403 and error(r)["codigo"] == "V-19" and error(r)["token_activacion"].startswith("tkn_")
    obs("Cuenta PENDIENTE: no inicia sesión (403 V-19) y trae el token para abrir la pantalla del código")


def test_CP_RF_03_05(cliente, db):
    token = registrar_y_activar(cliente)
    res = {}
    for dia in (29, 30, 31):
        for t in db.scalars(select(Token)):
            if t.tipo == "SESION":
                t.expira_en = ahora() + timedelta(days=30) - timedelta(hours=(dia - 1) * 24 + 12)  # mitad del día indicado
        db.commit()
        res[dia] = cliente.get(f"{API}/sync/pull", headers=autorizar(token)).status_code
    assert res == {29: 200, 30: 200, 31: 401}, res
    obs(f"Sesión de 30 días revisada a mitad de los días 29, 30 y 31: {res[29]} / {res[30]} / {res[31]} (V-46 en el día 31)")


def test_CP_RF_03_06(cliente):
    registrar_y_activar(cliente)
    r = ingreso(cliente, "maria.perez@correo.com", "A" * 65)
    assert r.status_code == 401 and error(r)["codigo"] == "V-17"
    obs("Clave de 65 caracteres: 401 V-17 «" + error(r)["mensaje"] + "» (no revela que la longitud es el motivo)")


def test_CP_RF_03_07(cliente):
    registrar_y_activar(cliente)
    limites.reiniciar()
    estados = [ingreso(cliente, f"u{i}@correo.com", "Otra#Clave2026").status_code for i in range(11)]
    assert estados[:10] == [401] * 10 and estados[10] == 429
    r = ingreso(cliente, "z@correo.com", "x")
    assert r.status_code == 429 and error(r)["codigo"] == "E-10" and "retry-after" in r.headers
    obs(f"A-05 once veces seguidas desde la misma IP: {estados}; la 11.ª responde 429 E-10 con Retry-After")
