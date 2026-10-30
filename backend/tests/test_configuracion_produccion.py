"""Configuración del despliegue (documento 20): validación al arrancar, varios dominios e IP real detrás del proxy de Render."""
from dataclasses import replace

import pytest
from fastapi.testclient import TestClient

from app.core import config as cfg
from app.core.config import validar_produccion
from tests.conftest import API

CLAVE_LARGA = "x" * 40


def produccion(**cambios):
    """Una configuración de producción completa y correcta; cada prueba cambia solo lo que quiere revisar."""
    base = replace(cfg.config, entorno="produccion", clave_secreta=CLAVE_LARGA, brevo_api_key="xkeysib-prueba",
                   correo_remitente="no-responder@sembrando.co", dominios=["sembrando.co"], database_url="mysql+pymysql://u:c@h/b",
                   db_ssl_ca="", proxy_saltos=1)
    return replace(base, **cambios)


def test_produccion_completa_no_tiene_problemas():
    assert validar_produccion(produccion()) == []


@pytest.mark.parametrize("cambio, texto", [
    ({"clave_secreta": cfg.CLAVE_DE_EJEMPLO}, "CLAVE_SECRETA"),
    ({"clave_secreta": "corta"}, "CLAVE_SECRETA"),
    ({"brevo_api_key": ""}, "BREVO_API_KEY"),
    ({"correo_remitente": ""}, "CORREO_REMITENTE"),
    ({"dominios": []}, "DOMINIO"),
    ({"database_url": None, "db_ssl_ca": ""}, "DB_SSL_CA"),
    ({"db_ssl_ca": "/no/existe/ca.pem"}, "ca.pem"),
    ({"entorno": "producción"}, "ENTORNO"),
    ({"proxy_saltos": 0}, "PROXY_SALTOS"),
])
def test_produccion_incompleta_dice_que_corregir(cambio, texto):
    problemas = validar_produccion(produccion(**cambio))
    assert problemas and any(texto in p for p in problemas)


def test_en_desarrollo_no_se_exigen_las_claves_de_produccion():
    assert validar_produccion(replace(cfg.config, entorno="desarrollo", brevo_api_key="", dominios=[], db_ssl_ca="")) == []


def test_la_aplicacion_no_arranca_con_la_configuracion_incompleta(monkeypatch):
    from app import main
    monkeypatch.setattr(main, "config", produccion(brevo_api_key=""))
    with pytest.raises(RuntimeError, match="BREVO_API_KEY"):
        main.crear_app()


def test_certificado_relativo_se_busca_en_la_carpeta_backend():
    assert cfg.ruta_certificado("ca.pem").endswith("backend/ca.pem") or cfg.ruta_certificado("ca.pem").endswith("backend\\ca.pem")
    assert cfg.ruta_certificado("") == ""
    assert cfg.lista(" a.com, ,b.com ") == ["a.com", "b.com"]


def test_varios_dominios_de_confianza(monkeypatch):
    from app import main
    monkeypatch.setattr(main, "config", replace(main.config, dominios=["sembrando.co", "sembrando-futuro.onrender.com"]))
    cliente = TestClient(main.crear_app())
    for host in ("sembrando.co", "sembrando-futuro.onrender.com", "localhost:10000"):
        assert cliente.get(f"{API}/salud", headers={"Host": host}).status_code == 200, host
    assert cliente.get(f"{API}/salud", headers={"Host": "sitio-falso.com"}).status_code == 400


def test_detras_del_proxy_no_sirve_inventar_la_ip(cliente, monkeypatch):
    """Con PROXY_SALTOS=2 (cliente → proxy 1 → proxy 2 → aplicación) se cuenta la IP que agregó el primer proxy.
    Un atacante que cambia en cada intento la dirección del principio de la lista sigue contando como la misma IP."""
    monkeypatch.setattr(cfg.config, "proxy_confiable", True)
    monkeypatch.setattr(cfg.config, "proxy_saltos", 2)
    # un correo distinto en cada intento, para que solo actúe el límite por IP (y no el bloqueo de la cuenta)
    estados = [cliente.post(f"{API}/auth/ingreso", json={"correo": f"u{i}@correo.com", "clave": "x"},
                            headers={"X-Forwarded-For": f"9.9.9.{i}, 5.5.5.5, 10.0.0.1"}).status_code for i in range(11)]
    assert estados[:10] == [401] * 10 and estados[10] == 429
    otro = cliente.post(f"{API}/auth/ingreso", json={"correo": "otro@correo.com", "clave": "x"}, headers={"X-Forwarded-For": "6.6.6.6, 10.0.0.1"})
    assert otro.status_code == 401  # otro visitante real (6.6.6.6) tiene su propio contador


def test_lista_corta_de_direcciones_usa_la_primera(cliente, monkeypatch):
    monkeypatch.setattr(cfg.config, "proxy_confiable", True)
    monkeypatch.setattr(cfg.config, "proxy_saltos", 3)
    from app.core.limites import ip_de

    class Pedido:
        headers = {"x-forwarded-for": "7.7.7.7"}
        client = None
    assert ip_de(Pedido()) == "7.7.7.7"
