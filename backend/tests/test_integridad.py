"""Integridad de la base de datos (documento 12): cascadas, RESTRICT, únicos y CHECK."""
import uuid
from datetime import date

import pytest
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from app import cli
from app.core.seguridad import ahora
from app.models import Ciclo, CicloCultivo, Cultivo, FichaTecnica, Finca, Gasto, Ingreso, Jornal, Usuario


def nid():
    return str(uuid.uuid4())


@pytest.fixture
def datos(db):
    cli.cargar_prueba(db)
    return db


def cuenta(db, modelo):
    return db.scalar(select(func.count()).select_from(modelo))


def test_cargar_prueba_es_idempotente(datos):
    cli.cargar_prueba(datos)
    assert cuenta(datos, Usuario) == 6 and cuenta(datos, Finca) == 2 and cuenta(datos, Gasto) == 2


def test_restablecer_vuelve_al_estado_inicial(datos):
    maria = datos.scalar(select(Usuario).where(Usuario.correo == "maria.perez@correo.com"))
    datos.add(Gasto(id_gasto=nid(), id_ciclo=datos.scalar(select(Ciclo.id_ciclo)), categoria="otros", valor_cop=5000,
                    fecha=date(2026, 5, 1), updated_at=ahora(), eliminado=False))
    maria.estado = "PENDIENTE"
    datos.commit()
    cli.cargar_prueba(datos, restablecer=True)
    datos.expire_all()
    maria = datos.scalar(select(Usuario).where(Usuario.correo == "maria.perez@correo.com"))
    assert maria.estado == "ACTIVA" and cuenta(datos, Gasto) == 2 and cuenta(datos, Usuario) == 6


def test_borrar_usuario_arrastra_todo(datos):
    maria = datos.scalar(select(Usuario).where(Usuario.correo == "maria.perez@correo.com"))
    datos.delete(maria)
    datos.commit()
    for modelo in (Finca, Ciclo, CicloCultivo, Gasto, Jornal, Ingreso):
        assert cuenta(datos, modelo) == 0, modelo
    assert cuenta(datos, Cultivo) == 3 and cuenta(datos, FichaTecnica) == 3  # el catálogo y sus fichas no se tocan


def test_borrar_finca_arrastra_ciclos_cultivos_y_movimientos(datos):
    finca = datos.scalar(select(Finca).where(Finca.nombre == "La Esperanza"))
    datos.delete(finca)
    datos.commit()
    assert cuenta(datos, Ciclo) == 1 and cuenta(datos, CicloCultivo) == 1
    assert cuenta(datos, Gasto) == 1 and cuenta(datos, Jornal) == 0 and cuenta(datos, Ingreso) == 1


def test_borrar_un_ciclo_arrastra_sus_cultivos(datos):
    ciclo = datos.scalar(select(Ciclo).where(Ciclo.nombre_lote == "Lote Bajo"))
    datos.delete(ciclo)
    datos.commit()
    assert cuenta(datos, Ciclo) == 2 and cuenta(datos, CicloCultivo) == 2


def test_no_se_borra_un_cultivo_con_ciclos(datos):
    cafe = datos.scalar(select(Cultivo).where(Cultivo.codigo == "CAFE"))
    datos.delete(cafe)
    with pytest.raises(IntegrityError):
        datos.commit()
    datos.rollback()
    assert cuenta(datos, Cultivo) == 3


def test_no_se_borra_un_cultivo_que_ya_tiene_ingresos_aunque_no_este_en_un_ciclo(datos):
    ingreso = datos.scalar(select(Ingreso))
    uso = datos.scalar(select(CicloCultivo).where(CicloCultivo.id_ciclo == ingreso.id_ciclo))
    datos.delete(uso)  # quitar el cultivo del ciclo es posible, pero el cultivo no se puede borrar mientras tenga ingresos
    datos.commit()
    datos.delete(datos.get(Cultivo, ingreso.id_cultivo))
    with pytest.raises(IntegrityError):
        datos.commit()
    datos.rollback()


def test_un_cultivo_no_se_repite_en_el_mismo_ciclo(datos):
    uso = datos.scalar(select(CicloCultivo))
    datos.add(CicloCultivo(id_ciclo_cultivo=nid(), id_ciclo=uso.id_ciclo, id_cultivo=uso.id_cultivo, updated_at=ahora()))
    with pytest.raises(IntegrityError):
        datos.commit()
    datos.rollback()


def test_una_ficha_tecnica_por_cultivo_y_checks(datos):
    cafe = datos.scalar(select(Cultivo).where(Cultivo.codigo == "CAFE"))
    base = dict(id_cultivo=cafe.id_cultivo, base_plantas=1000, costo_hoyado_cop=1, costo_colino_cop=1, insumo_anual_cop=1,
                jornales_limpieza_anio=1, jornales_riego_anio=1, actualizado_en=ahora())
    datos.add(FichaTecnica(**base))  # el café ya tiene su ficha (UNIQUE sobre id_cultivo)
    with pytest.raises(IntegrityError):
        datos.commit()
    datos.rollback()
    yuca = datos.scalar(select(Cultivo).where(Cultivo.codigo == "YUCA"))
    datos.delete(yuca.ficha)
    datos.commit()
    for cambio in ({"base_plantas": 0}, {"costo_hoyado_cop": -1}, {"jornales_riego_anio": 1000}):
        datos.add(FichaTecnica(**{**base, "id_cultivo": yuca.id_cultivo, **cambio}))
        with pytest.raises(IntegrityError):
            datos.commit()
        datos.rollback()


def test_solo_un_administrador(datos):
    datos.add(Usuario(id_usuario=nid(), nombre="Otro", ubicacion="-", correo="otro.admin@correo.com", hash_clave="x",
                      rol="ADMIN", estado="ACTIVA", intentos_fallidos=0, consentimiento_ley1581=True, creado_en=ahora()))
    with pytest.raises(IntegrityError):
        datos.commit()
    datos.rollback()


def test_correo_unico(datos):
    datos.add(Usuario(id_usuario=nid(), nombre="Copia", ubicacion="-", correo="maria.perez@correo.com", hash_clave="x",
                      rol="AGRICULTOR", estado="ACTIVA", intentos_fallidos=0, consentimiento_ley1581=True, creado_en=ahora()))
    with pytest.raises(IntegrityError):
        datos.commit()
    datos.rollback()


def test_hijo_sin_padre_se_rechaza(datos):
    datos.add(Gasto(id_gasto=nid(), id_ciclo=nid(), categoria="abonos", valor_cop=1000, fecha=date(2026, 4, 1), updated_at=ahora()))
    with pytest.raises(IntegrityError):
        datos.commit()
    datos.rollback()


def test_ciclo_checks(datos):
    finca = datos.scalar(select(Finca).where(Finca.nombre == "La Esperanza"))
    base = dict(id_finca=finca.id_finca, nombre_lote="Lote Alto", pendiente_pct=5, area_bruta_ha=1, area_no_sembrable_ha=0,
                area_efectiva_ha=1, fecha_siembra=date(2026, 3, 1), estado="ACTIVO", updated_at=ahora())
    for cambios in ({"pendiente_pct": 101}, {"area_bruta_ha": 0}, {"area_no_sembrable_ha": 1, "area_efectiva_ha": 0},
                    {"area_efectiva_ha": 2}, {"vigencia_anios": 0}, {"vigencia_anios": 51}):
        datos.add(Ciclo(id_ciclo=nid(), **{**base, **cambios}))
        with pytest.raises(IntegrityError):
            datos.commit()
        datos.rollback()
    # el nombre del lote ya no es único y la vigencia es opcional
    datos.add(Ciclo(id_ciclo=nid(), **base))
    datos.add(Ciclo(id_ciclo=nid(), **{**base, "vigencia_anios": 5}))
    datos.commit()


def test_checks_de_movimientos(datos):
    ciclo = datos.scalar(select(Ciclo))
    malos = [Gasto(id_gasto=nid(), id_ciclo=ciclo.id_ciclo, categoria="abonos", valor_cop=0, fecha=date(2026, 4, 1), updated_at=ahora()),
             Jornal(id_jornal=nid(), id_ciclo=ciclo.id_ciclo, cantidad_jornales=0.3, valor_jornal_cop=1000, fecha=date(2026, 4, 1), updated_at=ahora()),
             Ingreso(id_ingreso=nid(), id_ciclo=ciclo.id_ciclo, id_cultivo=datos.scalar(select(Cultivo.id_cultivo)), cantidad=0.01,
                     unidad_comercial="kilo", precio_unitario_cop=10, fecha=date(2026, 4, 1), updated_at=ahora())]
    for m in malos:
        datos.add(m)
        with pytest.raises(IntegrityError):
            datos.commit()
        datos.rollback()
