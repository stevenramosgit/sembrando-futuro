"""Comandos de administración (documento 20):  python -m app.cli <comando>

  crear_admin        crea la cuenta del administrador (pide correo y clave; solo puede existir una)
  cargar_semilla     carga o actualiza el catálogo de cultivos y sus fichas técnicas (datos/semilla_catalogo.json, o --archivo)
  listar_cuentas     lista las cuentas de agricultores (opcional --estado ACTIVA o PENDIENTE)
  resumen_cuenta     muestra las fincas y los conteos de una cuenta (--correo)
  cambiar_clave      cambia la clave de una cuenta (--correo; la clave nueva se pide o viene en CLAVE_NUEVA)
  eliminar_cuenta    elimina una cuenta y todos sus datos (--correo)
  cargar_prueba      carga los datos de prueba del documento 19 (solo fuera de producción); con --restablecer
                     borra antes las cuentas de prueba para volver al estado inicial
  limpiar_pendientes elimina las cuentas pendientes de más de 24 horas
  limpiar_bloqueos   quita los bloqueos de ingreso cumplidos
  limpiar_vencidos   borra códigos, tokens e intentos viejos
"""
import argparse
import getpass
import json
import os
import sys
import uuid
from datetime import date, timedelta

from sqlalchemy import select

from app.core import seguridad
from app.core.config import config
from app.core.errores import ErrorApi, ErroresDeCampos, texto
from app.database import connection
from app.domain import formulas, validaciones as v
from app.models import Ciclo, CicloCultivo, Cultivo, FichaTecnica, Finca, Gasto, Ingreso, Jornal, Otp, Usuario
from app.services import admin_service, limpieza_service

RAIZ = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "datos"))


def crear_admin(db, correo: str, clave: str) -> Usuario:
    correo = correo.strip().lower()
    if v.v_correo(correo):
        raise SystemExit(texto("V-03"))
    if v.v_clave(clave, correo, "Administrador"):
        raise SystemExit(texto("V-07"))
    if db.scalar(select(Usuario).where(Usuario.rol == "ADMIN")) is not None:
        raise SystemExit(texto("V-21"))
    if db.scalar(select(Usuario).where(Usuario.correo == correo)) is not None:
        raise SystemExit(texto("V-05"))
    admin = Usuario(id_usuario=str(uuid.uuid4()), nombre="Administrador", ubicacion="-", correo=correo,
                    hash_clave=seguridad.hashear_clave(clave), rol="ADMIN", estado="ACTIVA", intentos_fallidos=0,
                    consentimiento_ley1581=True, creado_en=seguridad.ahora())
    db.add(admin)
    db.commit()
    return admin


def cargar_semilla(db, ruta: str | None = None) -> int:
    ruta = ruta or os.path.join(RAIZ, "semilla_catalogo.json")
    with open(ruta, encoding="utf-8") as f:
        datos = json.load(f)
    lista = datos["cultivos"] if isinstance(datos, dict) else datos
    momento = seguridad.ahora().replace(microsecond=0)
    for c in lista:
        fila = db.scalar(select(Cultivo).where(Cultivo.codigo == c["codigo"]))
        valores = dict(nombre=c["nombre"], unidad_comercial=c["unidad_comercial"], distancia_min_m=c["distancia_min_m"],
                       distancia_max_m=c["distancia_max_m"], marcos_permitidos=c["marcos_permitidos"],
                       fuente_tecnica=c["fuente_tecnica"], actualizado_en=momento)
        if fila is None:
            fila = Cultivo(codigo=c["codigo"], **valores)
            db.add(fila)
        else:
            for k, val in valores.items():
                setattr(fila, k, val)
        ficha = c.get("ficha_tecnica")
        if ficha:
            campos = {k: ficha[k] for k in ("base_plantas", "costo_hoyado_cop", "costo_colino_cop", "insumo_anual_cop",
                                            "jornales_limpieza_anio", "jornales_riego_anio", "datos_extra")}
            if fila.ficha is None:
                fila.ficha = FichaTecnica(**campos, actualizado_en=momento)
            else:
                for k, val in campos.items():
                    setattr(fila.ficha, k, val)
                fila.ficha.actualizado_en = momento
    db.commit()
    return len(lista)


def _fecha(texto_fecha):
    return date.fromisoformat(texto_fecha) if texto_fecha else None


def _uid(clave):
    return str(uuid.uuid5(uuid.NAMESPACE_URL, "sembrando-futuro/" + clave))


def _cargar_usuarios(db, lista, ahora) -> dict:
    """Crea las cuentas de prueba que aún no existen; devuelve las creadas, por su identificador de la tabla."""
    usuarios = {}
    for u in lista:
        if db.scalar(select(Usuario).where(Usuario.correo == u["correo"])):
            continue
        es_admin = u["id"].startswith("ADM")
        if es_admin and db.scalar(select(Usuario).where(Usuario.rol == "ADMIN")):
            continue
        creado = ahora
        if u["id"] == "U-02":
            creado = ahora - timedelta(hours=2)
        elif u["id"] == "U-03":
            creado = ahora - timedelta(hours=25)
        fila = Usuario(id_usuario=_uid(u["id"]), nombre=u["nombre"], ubicacion=u["ubicacion"], correo=u["correo"],
                       hash_clave=seguridad.hashear_clave(u["clave"]), rol="ADMIN" if es_admin else "AGRICULTOR",
                       estado=u["estado"], intentos_fallidos=0, consentimiento_ley1581=True, creado_en=creado)
        if u["id"] == "U-04":
            fila.bloqueado_hasta = ahora + timedelta(minutes=15)
        db.add(fila)
        db.flush()
        usuarios[u["id"]] = fila
        if u["estado"] == "PENDIENTE":
            _agregar_otp(db, u["id"], fila, ahora, creado)
    return usuarios


def _agregar_otp(db, id_tabla, fila, ahora, creado) -> None:
    reenvios = 3 if id_tabla == "U-05" else 0
    # U-02: código vigente (enviado hace 1 minuto); U-05: enviado hace 5 minutos; U-03: enviado al crear la cuenta (hace 25 h)
    enviado = {"U-02": ahora - timedelta(minutes=1), "U-05": ahora - timedelta(minutes=5)}.get(id_tabla, creado)
    db.add(Otp(id_otp=_uid("otp-" + id_tabla), id_usuario=fila.id_usuario,
               codigo_hash=seguridad.hash_otp(config.otp_fijo_pruebas), enviado_en=enviado,
               expira_en=enviado + timedelta(minutes=15), intentos_fallidos=0, reenvios=reenvios, usado=False))


def _cargar_fincas_y_ciclos(db, d, usuarios, marca) -> None:
    for f in d["fincas"]:
        dueno = usuarios.get(f.get("usuario")) or db.get(Usuario, _uid(f.get("usuario", "U-01")))
        if dueno is None or db.get(Finca, _uid(f["id"])):
            continue
        db.add(Finca(id_finca=_uid(f["id"]), id_usuario=dueno.id_usuario, nombre=f["nombre"], updated_at=marca))
    db.flush()
    for c in d["ciclos"]:
        if db.get(Ciclo, _uid(c["id"])):
            continue
        db.add(Ciclo(id_ciclo=_uid(c["id"]), id_finca=_uid(c["finca"]), nombre_lote=c.get("nombre_lote"),
                     pendiente_pct=c["pendiente_pct"], area_bruta_ha=c["area_bruta_ha"],
                     area_no_sembrable_ha=c["area_no_sembrable_ha"],
                     area_efectiva_ha=formulas.area_efectiva(c["area_bruta_ha"], c["area_no_sembrable_ha"]),
                     fecha_siembra=_fecha(c["fecha_siembra"]), vigencia_anios=c.get("vigencia_anios"),
                     estado=c["estado"], fecha_cierre=_fecha(c.get("fecha_cierre")), updated_at=marca))
    db.flush()


def _cargar_ciclo_cultivos(db, lista, cultivos, marca) -> None:
    for k in lista:
        if not db.get(CicloCultivo, _uid(k["id"])):
            db.add(CicloCultivo(id_ciclo_cultivo=_uid(k["id"]), id_ciclo=_uid(k["ciclo"]),
                                id_cultivo=cultivos[k["cultivo"]].id_cultivo, marco=k.get("marco"), dist_a_m=k.get("dist_a_m"),
                                dist_b_m=k.get("dist_b_m"), updated_at=marca))
    db.flush()


def _cargar_movimientos(db, d, cultivos, marca) -> None:
    for g in d["gastos"]:
        if not db.get(Gasto, _uid(g["id"])):
            db.add(Gasto(id_gasto=_uid(g["id"]), id_ciclo=_uid(g["ciclo"]), categoria=g["categoria"],
                         observaciones=g.get("observaciones"), valor_cop=g["valor_cop"], fecha=_fecha(g["fecha"]),
                         updated_at=marca, eliminado=False))
    for j in d["jornales"]:
        if not db.get(Jornal, _uid(j["id"])):
            db.add(Jornal(id_jornal=_uid(j["id"]), id_ciclo=_uid(j["ciclo"]), cantidad_jornales=j["jornales"],
                          valor_jornal_cop=j["valor_diario_cop"], fecha=_fecha(j["fecha"]), updated_at=marca, eliminado=False))
    for i in d["ingresos"]:
        if not db.get(Ingreso, _uid(i["id"])):
            ciclo = db.get(Ciclo, _uid(i["ciclo"]))
            cultivo = cultivos[i["cultivo"]]
            db.add(Ingreso(id_ingreso=_uid(i["id"]), id_ciclo=ciclo.id_ciclo, id_cultivo=cultivo.id_cultivo,
                           cantidad=i["cantidad"], unidad_comercial=cultivo.unidad_comercial,
                           precio_unitario_cop=i["precio_unitario_cop"],
                           fecha=_fecha(i["fecha"]), updated_at=marca, eliminado=False))


def cargar_prueba(db, ruta: str | None = None, restablecer: bool = False) -> dict:
    """Carga datos_prueba.json (documento 19). Los identificadores de la tabla se convierten en UUID estables.
    Con restablecer=True borra antes las cuentas de prueba (y sus datos) para volver al estado inicial."""
    if config.entorno == "produccion":
        raise SystemExit("cargar_prueba no se usa en producción.")
    ruta = ruta or os.path.join(RAIZ, "datos_prueba.json")
    with open(ruta, encoding="utf-8") as f:
        d = json.load(f)
    if restablecer:
        for u in d["usuarios"]:
            cuenta = db.scalar(select(Usuario).where(Usuario.correo == u["correo"], Usuario.rol == "AGRICULTOR"))
            if cuenta:
                admin_service.eliminar(db, cuenta.id_usuario)
    cultivos = {c.codigo: c for c in db.scalars(select(Cultivo))}
    if not cultivos:
        raise SystemExit("Primero ejecute cargar_semilla.")
    ahora = seguridad.ahora()
    marca = ahora.replace(microsecond=0)
    usuarios = _cargar_usuarios(db, d["usuarios"], ahora)
    _cargar_fincas_y_ciclos(db, d, usuarios, marca)
    _cargar_ciclo_cultivos(db, d["ciclo_cultivos"], cultivos, marca)
    _cargar_movimientos(db, d, cultivos, marca)
    db.commit()
    return {k: len(val) for k, val in d.items()}


def _cuenta(db, correo: str | None) -> Usuario:
    """Busca la cuenta de un agricultor por correo; termina con el mensaje E-07 si no existe."""
    correo = (correo or input("Correo de la cuenta: ")).strip().lower()
    usuario = db.scalar(select(Usuario).where(Usuario.correo == correo))
    if usuario is None:
        raise SystemExit(texto("E-07"))
    return usuario


def _ejecutar(funcion, *args):
    """Ejecuta una operación del servicio de administración y traduce sus errores a un mensaje de consola."""
    try:
        return funcion(*args)
    except ErrorApi as e:
        raise SystemExit(e.mensaje)
    except ErroresDeCampos as e:
        raise SystemExit("; ".join(m for _, m in e.campos.values()))


def _cmd_crear_admin(db, a):
    correo = a.correo or input("Correo del administrador: ")
    clave = os.getenv("ADMIN_CLAVE") or getpass.getpass("Clave (no se muestra): ")
    crear_admin(db, correo, clave)
    print("Administrador creado.")


def _cmd_listar_cuentas(db, a):
    lista = admin_service.listar(db, a.estado, 1, 100)
    for u in lista["usuarios"]:
        print(f'{u["correo"]}\t{u["estado"]}\t{u["nombre"]}\t{u["creado_en"]}')
    print(f'{lista["total"]} cuentas.')


def _cmd_resumen_cuenta(db, a):
    r = _ejecutar(admin_service.resumen, db, _cuenta(db, a.correo).id_usuario)
    print(json.dumps(r, ensure_ascii=False, indent=2))


def _cmd_cambiar_clave(db, a):
    usuario = _cuenta(db, a.correo)
    clave = os.getenv("CLAVE_NUEVA") or getpass.getpass("Clave nueva (no se muestra): ")
    _ejecutar(admin_service.cambiar_clave, db, usuario.id_usuario, clave)
    print("Clave cambiada; se cerraron las sesiones de la cuenta.")


def _cmd_eliminar_cuenta(db, a):
    _ejecutar(admin_service.eliminar, db, _cuenta(db, a.correo).id_usuario)
    print("Cuenta eliminada con todos sus datos.")


COMANDOS = {
    "crear_admin": _cmd_crear_admin,
    "cargar_semilla": lambda db, a: print(f"{cargar_semilla(db, a.archivo)} cultivos cargados."),
    "cargar_prueba": lambda db, a: print("Datos de prueba cargados:", cargar_prueba(db, a.archivo, a.restablecer)),
    "listar_cuentas": _cmd_listar_cuentas,
    "resumen_cuenta": _cmd_resumen_cuenta,
    "cambiar_clave": _cmd_cambiar_clave,
    "eliminar_cuenta": _cmd_eliminar_cuenta,
    "limpiar_pendientes": lambda db, a: print(f"{limpieza_service.limpiar_pendientes(db)} cuentas pendientes eliminadas."),
    "limpiar_bloqueos": lambda db, a: print(f"{limpieza_service.limpiar_bloqueos(db)} bloqueos quitados."),
    "limpiar_vencidos": lambda db, a: print(f"{limpieza_service.limpiar_vencidos(db)} filas viejas eliminadas."),
}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="python -m app.cli", description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    ap.add_argument("comando", choices=list(COMANDOS))
    ap.add_argument("--correo")
    ap.add_argument("--estado", choices=["ACTIVA", "PENDIENTE"], help="filtro de listar_cuentas")
    ap.add_argument("--restablecer", action="store_true", help="con cargar_prueba: borra antes las cuentas de prueba")
    ap.add_argument("--archivo", help="ruta alterna del JSON para cargar_semilla o cargar_prueba")
    a = ap.parse_args(argv)
    with connection.SessionLocal() as db:
        COMANDOS[a.comando](db, a)
    return 0


if __name__ == "__main__":
    sys.exit(main())
