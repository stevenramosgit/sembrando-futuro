"""Datos de prueba del documento 19 y comandos de mantenimiento (limpiar_*)."""
from datetime import timedelta

from sqlalchemy import select

from app import cli
from app.core.seguridad import ahora
from app.models import Usuario
from app.models.usuario import IntentoIngreso, Otp, Token
from app.services import limpieza_service
from tests.conftest import API, autorizar


def cargar(db):
    cli.cargar_prueba(db)


def test_maria_ingresa_y_ve_sus_datos(cliente, db):
    cargar(db)
    r = cliente.post(f"{API}/auth/ingreso", json={"correo": "maria.perez@correo.com", "clave": "Siembra#2026a"})
    assert r.status_code == 200
    registros = cliente.get(f"{API}/sync/pull", headers=autorizar(r.json()["token"])).json()["registros"]
    assert {t: sum(1 for x in registros if x["tipo"] == t) for t in ("finca", "ciclo", "ciclo_cultivo", "gasto", "jornal", "ingreso")} == {
        "finca": 2, "ciclo": 3, "ciclo_cultivo": 3, "gasto": 2, "jornal": 1, "ingreso": 2}
    ciclos = {x["datos"]["nombre_lote"] + str(x["datos"]["vigencia_anios"]) for x in registros if x["tipo"] == "ciclo"}
    assert ciclos == {"Lote Alto7", "Lote Bajo2", "Lote Alto1"}


def test_pedro_pendiente_activa_con_el_codigo_482915(cliente, db):
    cargar(db)
    r = cliente.post(f"{API}/auth/ingreso", json={"correo": "pedro.gomez@correo.com", "clave": "Cultivo#2026b"})
    assert r.status_code == 403 and r.json()["error"]["codigo"] == "V-19"
    r = cliente.post(f"{API}/auth/otp/verificar", json={"codigo": "482915"}, headers=autorizar(r.json()["error"]["token_activacion"]))
    assert r.status_code == 200


def test_ana_ya_uso_los_3_reenvios(cliente, db):
    cargar(db)
    r = cliente.post(f"{API}/auth/ingreso", json={"correo": "ana.torres@correo.com", "clave": "Semilla#2026e"})
    t = autorizar(r.json()["error"]["token_activacion"])
    for o in db.scalars(select(Otp)):
        o.enviado_en = ahora() - timedelta(seconds=120)
    db.commit()
    r = cliente.post(f"{API}/auth/otp/reenviar", headers=t)
    assert r.status_code == 429 and r.json()["error"]["codigo"] == "V-14"


def test_carlos_esta_bloqueado(cliente, db):
    cargar(db)
    r = cliente.post(f"{API}/auth/ingreso", json={"correo": "carlos.ruiz@correo.com", "clave": "Tierra#2026d"})
    assert r.status_code == 423 and r.json()["error"]["codigo"] == "V-18"


def test_luz_pendiente_de_25_horas_se_elimina_y_libera_el_correo(db):
    cargar(db)
    assert limpieza_service.limpiar_pendientes(db) == 1
    assert db.scalar(select(Usuario).where(Usuario.correo == "luz.mena@correo.com")) is None
    assert db.scalar(select(Usuario).where(Usuario.correo == "pedro.gomez@correo.com")) is not None


def test_limpiar_bloqueos_y_vencidos(db):
    cargar(db)
    carlos = db.scalar(select(Usuario).where(Usuario.correo == "carlos.ruiz@correo.com"))
    carlos.bloqueado_hasta = ahora() - timedelta(minutes=1)
    carlos.intentos_fallidos = 5
    db.add(IntentoIngreso(correo="fantasma@correo.com", intentos_fallidos=2, actualizado_en=ahora() - timedelta(hours=30)))
    db.add(IntentoIngreso(correo="bloqueado@correo.com", intentos_fallidos=0, bloqueado_hasta=ahora() + timedelta(minutes=10),
                          actualizado_en=ahora() - timedelta(hours=30)))
    maria = db.scalar(select(Usuario).where(Usuario.correo == "maria.perez@correo.com"))
    db.add(Token(id_token="t-viejo", id_usuario=maria.id_usuario, token_hash="a" * 64, tipo="SESION", creado_en=ahora() - timedelta(days=70),
                 expira_en=ahora() - timedelta(days=40), revocado=False))
    db.commit()
    assert limpieza_service.limpiar_bloqueos(db) == 1
    db.refresh(carlos)
    assert carlos.bloqueado_hasta is None and carlos.intentos_fallidos == 0
    assert limpieza_service.limpiar_vencidos(db) >= 2
    assert db.get(IntentoIngreso, "fantasma@correo.com") is None
    assert db.get(IntentoIngreso, "bloqueado@correo.com") is not None  # sigue bloqueado
    assert db.get(Token, "t-viejo") is None


def test_cargar_semilla_actualiza_sin_duplicar(db):
    assert cli.cargar_semilla(db) == 3
    assert cli.cargar_semilla(db) == 3
    from app.models import Cultivo, FichaTecnica
    assert len(list(db.scalars(select(Cultivo)))) == 3 and len(list(db.scalars(select(FichaTecnica)))) == 3


def test_cli_crear_admin_por_linea_de_comandos(db, monkeypatch):
    monkeypatch.setenv("ADMIN_CLAVE", "Cafe#Cauca2026")
    assert cli.main(["crear_admin", "--correo", "admin.proyecto@correo.com"]) == 0
    assert db.scalar(select(Usuario).where(Usuario.rol == "ADMIN")).correo == "admin.proyecto@correo.com"
