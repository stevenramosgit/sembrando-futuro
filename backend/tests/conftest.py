"""Preparación de las pruebas: base SQLite en memoria, entorno 'pruebas' (código fijo 482915) y contadores de límite en cero."""
import json
import os
import re

os.environ["DATABASE_URL"] = "sqlite://"
os.environ["ENTORNO"] = "pruebas"
os.environ["BREVO_API_KEY"] = ""
os.environ["CLAVE_SECRETA"] = "clave-de-pruebas"

import pytest
from fastapi.testclient import TestClient

from app import cli
from app.core import limites
from app.database import connection
from app.main import app as aplicacion
from app.models import *  # noqa: F401,F403
from app.database.connection import Base, SessionLocal, engine

API = "/api/v1"
CLAVE = "Siembra#2026a"


@pytest.fixture(autouse=True)
def base_limpia():
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    limites.reiniciar()
    with SessionLocal() as db:
        cli.cargar_semilla(db)
    yield


@pytest.fixture
def db():
    with SessionLocal() as sesion:
        yield sesion


@pytest.fixture
def cliente():
    with TestClient(aplicacion) as c:
        yield c


def autorizar(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def registrar_y_activar(cliente, correo="maria.perez@correo.com", nombre="María Pérez", clave=CLAVE):
    r = cliente.post(f"{API}/auth/registro", json={
        "nombre": nombre, "ubicacion": "Caloto, Cauca", "correo": correo, "correo_confirmacion": correo,
        "clave": clave, "autoriza_datos": True})
    assert r.status_code == 201, r.text
    t = r.json()["token_activacion"]
    r = cliente.post(f"{API}/auth/otp/verificar", json={"codigo": "482915"}, headers=autorizar(t))
    assert r.status_code == 200, r.text
    return ingresar(cliente, correo, clave)


def ingresar(cliente, correo, clave):
    r = cliente.post(f"{API}/auth/ingreso", json={"correo": correo, "clave": clave})
    assert r.status_code == 200, r.text
    return r.json()["token"]


@pytest.fixture
def token(cliente):
    return registrar_y_activar(cliente)


@pytest.fixture
def cabecera(token):
    return autorizar(token)


@pytest.fixture
def admin(cliente, db):
    cli.crear_admin(db, "admin.proyecto@correo.com", "Cafe#Cauca2026")
    return autorizar(ingresar(cliente, "admin.proyecto@correo.com", "Cafe#Cauca2026"))


# ------------------------------------------------------------------------------------------------------------
# Registro de la ejecución del plan de pruebas (documento 14, hoja Plan_Pruebas): cada prueba cuyo nombre es
# test_CP_<identificador> guarda su estado y lo que observó en tests/resultados_plan.json.
_ACTUAL = {"obs": ""}
_PLAN: dict[str, dict] = {}
RESULTADOS_PLAN = os.path.join(os.path.dirname(__file__), "resultados_plan.json")


def obs(texto: str) -> None:
    """Anota lo que la prueba observó (valores reales), para la columna «Resultado obtenido» del plan."""
    _ACTUAL["obs"] = texto


@pytest.fixture(autouse=True)
def _reiniciar_observacion():
    _ACTUAL["obs"] = ""
    yield


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item, call):
    salida = yield
    informe = salida.get_result()
    m = re.match(r"test_((?:CP|CB)_[A-Z0-9_]+)$", item.name)
    if m and informe.when == "call":
        if informe.passed:
            _PLAN[m.group(1).replace("_", "-")] = {"estado": "Aprobado", "obtenido": _ACTUAL["obs"]}
        else:
            motivo = str(call.excinfo.value).strip().splitlines()[0][:300] if call.excinfo else "falló"
            _PLAN[m.group(1).replace("_", "-")] = {"estado": "Falló", "obtenido": f"{_ACTUAL['obs']} | {motivo}".strip(" |")}


def pytest_sessionfinish(session, exitstatus):
    if _PLAN:
        existentes = {}
        if os.path.exists(RESULTADOS_PLAN):
            with open(RESULTADOS_PLAN, encoding="utf-8") as f:
                existentes = json.load(f)
        existentes.update(_PLAN)
        with open(RESULTADOS_PLAN, "w", encoding="utf-8") as f:
            json.dump(dict(sorted(existentes.items())), f, ensure_ascii=False, indent=1)
