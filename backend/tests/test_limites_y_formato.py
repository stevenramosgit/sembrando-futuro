"""Límites por IP (E-10), formato de error, servicios y cabeceras."""

from tests.conftest import API


def test_limite_de_ingreso_E10_con_retry_after(cliente):
    for _ in range(10):
        r = cliente.post(f"{API}/auth/ingreso", json={"correo": f"x{_}@correo.com", "clave": "Mala#Clave2026"})
        assert r.status_code == 401
    r = cliente.post(f"{API}/auth/ingreso", json={"correo": "x@correo.com", "clave": "Mala#Clave2026"})
    assert r.status_code == 429 and r.json()["error"]["codigo"] == "E-10"
    assert int(r.headers["retry-after"]) >= 1 and r.json()["error"]["espera_segundos"] >= 1


def test_limite_de_registro_5_por_hora(cliente):
    for i in range(5):
        assert cliente.post(f"{API}/auth/registro", json={}).status_code == 400
    assert cliente.post(f"{API}/auth/registro", json={}).status_code == 429


def test_cada_servicio_cuenta_aparte(cliente):
    for _ in range(10):
        cliente.post(f"{API}/auth/ingreso", json={"correo": "a@correo.com", "clave": "x"})
    assert cliente.post(f"{API}/auth/ingreso", json={"correo": "a@correo.com", "clave": "x"}).status_code == 429
    assert cliente.get(f"{API}/salud").status_code == 200
    assert cliente.get(f"{API}/catalogo").status_code == 200


def test_limite_de_salud(cliente):
    for _ in range(30):
        assert cliente.get(f"{API}/salud").status_code == 200
    assert cliente.get(f"{API}/salud").status_code == 429


def test_la_ip_reenviada_solo_cuenta_si_se_confia_en_el_proxy(cliente, monkeypatch):
    from app.core import config as cfg
    monkeypatch.setattr(cfg.config, "proxy_confiable", True)
    for i in range(10):
        cliente.post(f"{API}/auth/ingreso", json={"correo": "a@correo.com", "clave": "x"}, headers={"X-Forwarded-For": "1.1.1.1"})
    assert cliente.post(f"{API}/auth/ingreso", json={"correo": "a@correo.com", "clave": "x"}, headers={"X-Forwarded-For": "1.1.1.1"}).status_code == 429
    assert cliente.post(f"{API}/auth/ingreso", json={"correo": "b@correo.com", "clave": "x"}, headers={"X-Forwarded-For": "2.2.2.2"}).status_code == 401


def test_error_de_formato_es_400_no_422(cliente, cabecera):
    r = cliente.post(f"{API}/sync/push", headers=cabecera, content="no es json", )
    assert r.status_code == 400 and r.json()["error"]["codigo"] == "E-03"
    r = cliente.post(f"{API}/auth/ingreso", content='{"correo": 5}', headers={"Content-Type": "application/json"})
    assert r.status_code == 400


def test_ruta_inexistente_E07(cliente):
    r = cliente.get(f"{API}/no-existe")
    assert r.status_code == 404 and r.json()["error"]["codigo"] == "E-07"


def test_la_api_tiene_los_16_servicios_y_no_publica_paginas_de_documentacion(cliente):
    from app.main import app
    rutas = {(m, r.path) for r in app.routes if getattr(r, "methods", None) for m in r.methods if r.path.startswith(f"{API}/")}
    assert len(rutas) == 16  # los 16 servicios del documento 18
    for ruta in ("/docs", "/redoc", "/openapi.json"):
        assert cliente.get(ruta).status_code == 404


def test_cabeceras_de_seguridad(cliente):
    r = cliente.get(f"{API}/salud")
    assert "max-age" in r.headers["strict-transport-security"] and r.headers["x-content-type-options"] == "nosniff"
    assert r.headers["cache-control"] == "no-store"


def test_la_clave_no_aparece_en_los_registros(cliente, caplog):
    caplog.set_level("DEBUG")
    cliente.post(f"{API}/auth/ingreso", json={"correo": "a@correo.com", "clave": "ClaveSecreta#99"})
    assert "ClaveSecreta#99" not in caplog.text


def test_csp_en_todas_las_respuestas(cliente):
    assert "default-src 'self'" in cliente.get(f"{API}/salud").headers["content-security-policy"]
