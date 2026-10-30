"""A-01 a A-06: registro, código de activación, reenvío, cambio de correo, ingreso con bloqueo y salida."""
from datetime import timedelta

from sqlalchemy import select

from app.core.seguridad import ahora
from app.models.usuario import IntentoIngreso, Otp, Token, Usuario
from tests.conftest import API, CLAVE, autorizar, registrar_y_activar

REGISTRO = {"nombre": "Pedro Gómez", "ubicacion": "Morales, Cauca", "correo": "Pedro.Gomez@Correo.com",
            "correo_confirmacion": "pedro.gomez@correo.com", "clave": "Cultivo#2026b", "autoriza_datos": True}


def registrar(cliente, **cambios):
    return cliente.post(f"{API}/auth/registro", json={**REGISTRO, **cambios})


def test_registro_exitoso_guarda_minusculas_y_hash(cliente, db):
    r = registrar(cliente)
    assert r.status_code == 201
    cuerpo = r.json()
    assert cuerpo["estado"] == "PENDIENTE" and cuerpo["correo"] == "pedro.gomez@correo.com"
    assert cuerpo["reenvios_restantes"] == 3 and cuerpo["espera_segundos"] == 60 and cuerpo["token_activacion"].startswith("tkn_")
    u = db.scalar(select(Usuario))
    assert u.hash_clave != "Cultivo#2026b" and u.estado == "PENDIENTE" and u.rol == "AGRICULTOR"
    t = db.scalar(select(Token))
    assert t.token_hash != cuerpo["token_activacion"] and len(t.token_hash) == 64


def test_registro_devuelve_todos_los_campos_con_error(cliente):
    r = registrar(cliente, nombre="0", ubicacion="x", correo="0@0", correo_confirmacion="otro", clave="123", autoriza_datos=False)
    assert r.status_code == 400
    campos = r.json()["error"]["campos"]
    assert {"nombre", "ubicacion", "correo", "clave", "autoriza_datos"} <= set(campos)
    assert campos["nombre"]["codigo"] == "V-01" and campos["autoriza_datos"]["codigo"] == "V-08"


def test_registro_confirmacion_distinta(cliente):
    r = registrar(cliente, correo_confirmacion="otro@correo.com")
    assert r.status_code == 400 and r.json()["error"]["campos"]["correo_confirmacion"]["codigo"] == "V-04"


def test_registro_correo_repetido(cliente):
    assert registrar(cliente).status_code == 201
    r = registrar(cliente)
    assert r.status_code == 409 and r.json()["error"]["codigo"] == "V-06"
    registrar_y_activar(cliente, "luis.mena@correo.com", "Luis Mena")
    r = registrar(cliente, correo="luis.mena@correo.com", correo_confirmacion="luis.mena@correo.com")
    assert r.status_code == 409 and r.json()["error"]["codigo"] == "V-05"


def test_cuenta_pendiente_vencida_libera_el_correo(cliente, db):
    registrar(cliente)
    u = db.scalar(select(Usuario))
    u.creado_en = ahora() - timedelta(hours=25)
    db.commit()
    assert registrar(cliente).status_code == 201
    assert len(list(db.scalars(select(Usuario)))) == 1


def test_error_de_correo_revierte_el_registro(cliente, db, monkeypatch):
    from app.core.errores import ErrorApi
    from app.services import correo_service

    def falla(*a, **k):
        raise ErrorApi(503, "V-45")
    monkeypatch.setattr(correo_service, "enviar_codigo", falla)
    r = registrar(cliente)
    assert r.status_code == 503 and r.json()["error"]["codigo"] == "V-45"
    assert db.scalar(select(Usuario)) is None


def test_otp_incorrecto_descuenta_intentos_y_el_quinto_bloquea(cliente):
    t = autorizar(registrar(cliente).json()["token_activacion"])
    for restantes in (4, 3, 2, 1):
        r = cliente.post(f"{API}/auth/otp/verificar", json={"codigo": "111111"}, headers=t)
        assert r.status_code == 400 and r.json()["error"]["codigo"] == "V-10"
        assert r.json()["error"]["intentos_restantes"] == restantes
    r = cliente.post(f"{API}/auth/otp/verificar", json={"codigo": "111111"}, headers=t)
    assert r.status_code == 423 and r.json()["error"]["codigo"] == "V-12"
    r = cliente.post(f"{API}/auth/otp/verificar", json={"codigo": "482915"}, headers=t)
    assert r.status_code == 423  # aun con el código correcto: está invalidado


def test_otp_formato_y_vencimiento(cliente, db):
    t = autorizar(registrar(cliente).json()["token_activacion"])
    assert cliente.post(f"{API}/auth/otp/verificar", json={"codigo": "48A"}, headers=t).json()["error"]["codigo"] == "V-09"
    otp = db.scalar(select(Otp))
    otp.enviado_en = ahora() - timedelta(minutes=16)
    db.commit()
    r = cliente.post(f"{API}/auth/otp/verificar", json={"codigo": "482915"}, headers=t)
    assert r.status_code == 400 and r.json()["error"]["codigo"] == "V-11"


def test_otp_cuenta_vencida_410(cliente, db):
    t = autorizar(registrar(cliente).json()["token_activacion"])
    u = db.scalar(select(Usuario))
    u.creado_en = ahora() - timedelta(hours=25)
    db.commit()
    r = cliente.post(f"{API}/auth/otp/verificar", json={"codigo": "482915"}, headers=t)
    assert r.status_code == 410 and r.json()["error"]["codigo"] == "V-15"
    db.expire_all()
    assert db.scalar(select(Usuario)) is None


def test_activar_y_el_token_de_activacion_deja_de_servir(cliente):
    t = autorizar(registrar(cliente).json()["token_activacion"])
    assert cliente.post(f"{API}/auth/otp/verificar", json={"codigo": "482915"}, headers=t).json() == {"estado": "ACTIVA"}
    assert cliente.post(f"{API}/auth/otp/reenviar", headers=t).status_code == 401


def test_token_de_sesion_no_sirve_para_activar_ni_el_de_activacion_para_sincronizar(cliente, token):
    assert cliente.post(f"{API}/auth/otp/reenviar", headers=autorizar(token)).status_code == 401
    t = autorizar(registrar(cliente).json()["token_activacion"])
    assert cliente.get(f"{API}/sync/pull", headers=t).status_code == 401


def test_reenvio_espera_60_segundos_y_maximo_3(cliente, db):
    t = autorizar(registrar(cliente).json()["token_activacion"])
    r = cliente.post(f"{API}/auth/otp/reenviar", headers=t)
    assert r.status_code == 429 and r.json()["error"]["codigo"] == "V-13" and "retry-after" in r.headers
    assert 1 <= r.json()["error"]["espera_segundos"] <= 60
    for i in (2, 1, 0):
        for o in db.scalars(select(Otp)):
            o.enviado_en = ahora() - timedelta(seconds=61)
        db.commit()
        r = cliente.post(f"{API}/auth/otp/reenviar", headers=t)
        assert r.status_code == 200 and r.json()["reenvios_restantes"] == i
    for o in db.scalars(select(Otp)):
        o.enviado_en = ahora() - timedelta(seconds=61)
    db.commit()
    r = cliente.post(f"{API}/auth/otp/reenviar", headers=t)
    assert r.status_code == 429 and r.json()["error"]["codigo"] == "V-14"


def test_reenvio_anula_el_codigo_anterior(cliente, db):
    t = autorizar(registrar(cliente).json()["token_activacion"])
    for o in db.scalars(select(Otp)):
        o.enviado_en = ahora() - timedelta(seconds=61)
    db.commit()
    assert cliente.post(f"{API}/auth/otp/reenviar", headers=t).status_code == 200
    assert len(list(db.scalars(select(Otp).where(Otp.usado.is_(False))))) == 1


def test_cambiar_correo_cuenta_como_reenvio(cliente, db):
    t = autorizar(registrar(cliente).json()["token_activacion"])
    for o in db.scalars(select(Otp)):
        o.enviado_en = ahora() - timedelta(seconds=61)
    db.commit()
    r = cliente.post(f"{API}/auth/correo/cambiar", headers=t,
                     json={"correo_nuevo": "nuevo@correo.com", "correo_nuevo_confirmacion": "NUEVO@correo.com"})
    assert r.status_code == 200 and r.json()["correo"] == "nuevo@correo.com" and r.json()["reenvios_restantes"] == 2
    assert db.scalar(select(Usuario)).correo == "nuevo@correo.com"


def test_cambiar_correo_validaciones(cliente):
    registrar_y_activar(cliente, "activa@correo.com", "Ana Torres")
    t = autorizar(registrar(cliente).json()["token_activacion"])
    r = cliente.post(f"{API}/auth/correo/cambiar", headers=t, json={"correo_nuevo": "0@0", "correo_nuevo_confirmacion": "0@0"})
    assert r.status_code == 400 and r.json()["error"]["campos"]["correo_nuevo"]["codigo"] == "V-03"
    r = cliente.post(f"{API}/auth/correo/cambiar", headers=t,
                     json={"correo_nuevo": "a@correo.com", "correo_nuevo_confirmacion": "b@correo.com"})
    assert r.json()["error"]["campos"]["correo_nuevo_confirmacion"]["codigo"] == "V-04"
    r = cliente.post(f"{API}/auth/correo/cambiar", headers=t,
                     json={"correo_nuevo": "activa@correo.com", "correo_nuevo_confirmacion": "activa@correo.com"})
    assert r.status_code == 409 and r.json()["error"]["codigo"] == "V-05"


def test_ingreso_correcto_devuelve_token_de_30_dias_y_rol(cliente):
    registrar_y_activar(cliente)
    r = cliente.post(f"{API}/auth/ingreso", json={"correo": "  MARIA.PEREZ@correo.com ", "clave": CLAVE})
    assert r.status_code == 200
    c = r.json()
    assert c["usuario"]["rol"] == "AGRICULTOR" and c["usuario"]["correo"] == "maria.perez@correo.com"
    assert "hash_clave" not in str(c) and c["expira_en"].endswith("Z")


def test_ingreso_errores(cliente):
    registrar_y_activar(cliente)
    assert cliente.post(f"{API}/auth/ingreso", json={"correo": "", "clave": ""}).json()["error"]["codigo"] == "V-16"
    assert cliente.post(f"{API}/auth/ingreso", json={"correo": "maria.perez@correo.com"}).status_code == 400
    mal = cliente.post(f"{API}/auth/ingreso", json={"correo": "maria.perez@correo.com", "clave": "Otra#Clave2026"})
    no = cliente.post(f"{API}/auth/ingreso", json={"correo": "nadie@correo.com", "clave": "Otra#Clave2026"})
    assert mal.status_code == no.status_code == 401 and mal.json() == no.json()  # no revela si el correo existe
    larga = cliente.post(f"{API}/auth/ingreso", json={"correo": "maria.perez@correo.com", "clave": "A" * 200})
    assert larga.status_code == 401


def test_bloqueo_tras_5_fallos_incluso_con_clave_correcta(cliente, db):
    registrar_y_activar(cliente)
    from app.core import limites
    for i in range(4):
        r = cliente.post(f"{API}/auth/ingreso", json={"correo": "maria.perez@correo.com", "clave": "Otra#Clave2026"})
        assert r.status_code == 401
    r = cliente.post(f"{API}/auth/ingreso", json={"correo": "maria.perez@correo.com", "clave": "Otra#Clave2026"})
    assert r.status_code == 423 and r.json()["error"]["codigo"] == "V-18" and "bloqueado_hasta" in r.json()["error"]
    assert "Intente de nuevo a las" in r.json()["error"]["mensaje"]
    r = cliente.post(f"{API}/auth/ingreso", json={"correo": "maria.perez@correo.com", "clave": CLAVE})
    assert r.status_code == 423
    u = db.scalar(select(Usuario))
    u.bloqueado_hasta = ahora() - timedelta(seconds=1)
    db.commit()
    limites.reiniciar()
    assert cliente.post(f"{API}/auth/ingreso", json={"correo": "maria.perez@correo.com", "clave": CLAVE}).status_code == 200


def test_correo_inexistente_tambien_se_bloquea(cliente, db):
    for _ in range(4):
        assert cliente.post(f"{API}/auth/ingreso", json={"correo": "fantasma@correo.com", "clave": "x1"}).status_code == 401
    r = cliente.post(f"{API}/auth/ingreso", json={"correo": "fantasma@correo.com", "clave": "x1"})
    assert r.status_code == 423
    assert db.get(IntentoIngreso, "fantasma@correo.com") is not None


def test_ingreso_de_cuenta_pendiente_403_con_token_de_activacion(cliente):
    registrar(cliente)
    r = cliente.post(f"{API}/auth/ingreso", json={"correo": "pedro.gomez@correo.com", "clave": "Cultivo#2026b"})
    assert r.status_code == 403
    e = r.json()["error"]
    assert e["codigo"] == "V-19" and e["accion"] == "VERIFICAR_OTP" and e["token_activacion"].startswith("tkn_")
    r = cliente.post(f"{API}/auth/otp/verificar", json={"codigo": "482915"}, headers=autorizar(e["token_activacion"]))
    assert r.status_code == 200


def test_salida_revoca_el_token(cliente, token):
    assert cliente.get(f"{API}/sync/pull", headers=autorizar(token)).status_code == 200
    assert cliente.post(f"{API}/auth/salida", headers=autorizar(token)).status_code == 204
    r = cliente.get(f"{API}/sync/pull", headers=autorizar(token))
    assert r.status_code == 401 and r.json()["error"]["codigo"] == "V-46"


def test_token_ausente_o_falso(cliente):
    assert cliente.get(f"{API}/sync/pull").status_code == 401
    assert cliente.get(f"{API}/sync/pull", headers=autorizar("tkn_falso")).status_code == 401
