"""Comandos de administración por consola (documento 20): listar_cuentas, resumen_cuenta, cambiar_clave y eliminar_cuenta."""
import json

import pytest
from sqlalchemy import func, select

from app import cli
from app.models import Finca, Usuario
from tests.conftest import API, CLAVE, autorizar, ingresar, registrar_y_activar
from tests.test_sync import estructura


def correr(*argumentos):
    return cli.main(list(argumentos))


def test_listar_cuentas_muestra_solo_agricultores(cliente, db, capsys):
    registrar_y_activar(cliente)
    cli.crear_admin(db, "admin.proyecto@correo.com", "Cafe#Cauca2026")
    assert correr("listar_cuentas") == 0
    salida = capsys.readouterr().out
    assert "maria.perez@correo.com" in salida and "admin.proyecto@correo.com" not in salida
    assert "1 cuentas." in salida
    correr("listar_cuentas", "--estado", "PENDIENTE")
    assert "0 cuentas." in capsys.readouterr().out


def test_resumen_cuenta_cuenta_las_fincas(cliente, capsys):
    cab = autorizar(registrar_y_activar(cliente))
    estructura(cliente, cab)
    correr("resumen_cuenta", "--correo", "maria.perez@correo.com")
    datos = json.loads(capsys.readouterr().out)
    assert datos["totales"]["fincas"] == 1 and datos["totales"]["ciclos"] == 1


def test_cambiar_clave_cierra_las_sesiones(cliente, monkeypatch):
    registrar_y_activar(cliente)
    monkeypatch.setenv("CLAVE_NUEVA", "Cacao#Nueva2027")
    assert correr("cambiar_clave", "--correo", "maria.perez@correo.com") == 0
    assert cliente.post(f"{API}/auth/ingreso", json={"correo": "maria.perez@correo.com", "clave": CLAVE}).status_code == 401
    assert ingresar(cliente, "maria.perez@correo.com", "Cacao#Nueva2027")


def test_cambiar_clave_rechaza_una_clave_debil(cliente, monkeypatch):
    registrar_y_activar(cliente)
    monkeypatch.setenv("CLAVE_NUEVA", "abc")
    with pytest.raises(SystemExit):
        correr("cambiar_clave", "--correo", "maria.perez@correo.com")
    assert ingresar(cliente, "maria.perez@correo.com", CLAVE)


def test_eliminar_cuenta_borra_sus_datos(cliente, db):
    cab = autorizar(registrar_y_activar(cliente))
    estructura(cliente, cab)
    assert correr("eliminar_cuenta", "--correo", "maria.perez@correo.com") == 0
    db.expire_all()
    assert db.scalar(select(func.count()).select_from(Usuario)) == 0
    assert db.scalar(select(func.count()).select_from(Finca)) == 0


def test_no_se_elimina_al_administrador_ni_a_una_cuenta_inexistente(db):
    cli.crear_admin(db, "admin.proyecto@correo.com", "Cafe#Cauca2026")
    with pytest.raises(SystemExit):
        correr("eliminar_cuenta", "--correo", "admin.proyecto@correo.com")
    with pytest.raises(SystemExit):
        correr("eliminar_cuenta", "--correo", "nadie@correo.com")
    assert db.scalar(select(func.count()).select_from(Usuario)) == 1
