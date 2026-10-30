"""Datos de prueba del documento 19 y comandos de mantenimiento (limpiar_*)."""
import os
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
    # La base de cada prueba ya tiene la semilla: volver a cargarla no duplica ni cambia nada.
    assert cli.cargar_semilla(db) == {"nuevos": 0, "completados": 0, "reemplazados": 0, "sin_cambios": 3}
    assert cli.cargar_semilla(db)["sin_cambios"] == 3
    from app.models import Cultivo, FichaTecnica
    assert len(list(db.scalars(select(Cultivo)))) == 3 and len(list(db.scalars(select(FichaTecnica)))) == 3


def test_cli_crear_admin_por_linea_de_comandos(db, monkeypatch):
    monkeypatch.setenv("ADMIN_CLAVE", "Cafe#Cauca2026")
    assert cli.main(["crear_admin", "--correo", "admin.proyecto@correo.com"]) == 0
    assert db.scalar(select(Usuario).where(Usuario.rol == "ADMIN")).correo == "admin.proyecto@correo.com"


def test_cargar_semilla_respeta_los_cambios_del_administrador(db):
    """Render ejecuta cargar_semilla en cada despliegue: lo que el administrador cambió con AD-04 no se pierde."""
    from app.models import Cultivo
    cafe = db.scalar(select(Cultivo).where(Cultivo.codigo == "CAFE"))
    cafe.distancia_min_m, cafe.ficha.precio_ref_cop = 1.2, 2500000
    fecha = cafe.actualizado_en
    db.commit()
    cli.cargar_semilla(db)
    db.refresh(cafe)
    assert float(cafe.distancia_min_m) == 1.2 and cafe.ficha.precio_ref_cop == 2500000
    assert cafe.actualizado_en == fecha  # sin cambios: los teléfonos no vuelven a descargar el catálogo


def test_cargar_semilla_forzar_vuelve_a_los_valores_del_archivo(db):
    from app.models import Cultivo
    cafe = db.scalar(select(Cultivo).where(Cultivo.codigo == "CAFE"))
    cafe.ficha.precio_ref_cop = 1
    db.commit()
    assert cli.cargar_semilla(db, forzar=True)["reemplazados"] == 3
    db.refresh(cafe)
    assert cafe.ficha.precio_ref_cop == 2220000


def test_cargar_semilla_completa_la_proyeccion_que_falta(db):
    """Una ficha creada antes de la migración 0002 no tiene proyección: la semilla la completa sin tocar los costos."""
    from app.models import Cultivo
    yuca = db.scalar(select(Cultivo).where(Cultivo.codigo == "YUCA"))
    yuca.ficha.meses_primera_cosecha = yuca.ficha.produccion_base = yuca.ficha.precio_ref_cop = None
    yuca.ficha.cosecha_unica = False
    yuca.ficha.costo_colino_cop = 999
    db.commit()
    assert cli.cargar_semilla(db)["completados"] == 1
    db.refresh(yuca)
    assert yuca.ficha.meses_primera_cosecha == 10 and yuca.ficha.cosecha_unica is True
    assert yuca.ficha.precio_ref_cop == 68250 and yuca.ficha.costo_colino_cop == 999


def test_cargar_semilla_inserta_un_cultivo_nuevo(db, tmp_path):
    import json
    from app.models import Cultivo
    ruta = os.path.join(cli.RAIZ, "semilla_catalogo.json")
    with open(ruta, encoding="utf-8") as f:
        datos = json.load(f)
    lista = datos["cultivos"] if isinstance(datos, dict) else datos
    nuevo = dict(lista[0], codigo="CACAO", nombre="Cacao")
    archivo = tmp_path / "semilla.json"
    archivo.write_text(json.dumps({"cultivos": lista + [nuevo]}), encoding="utf-8")
    assert cli.cargar_semilla(db, str(archivo))["nuevos"] == 1
    assert db.scalar(select(Cultivo).where(Cultivo.codigo == "CACAO")).ficha is not None
