"""Servicios de administración AD-01 a AD-05 (solo rol ADMIN)."""
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.core import seguridad
from app.core.errores import ErrorApi, ErroresDeCampos, texto
from app.domain import validaciones as v
from app.domain.fechas import a_iso
from app.models.ciclo import Ciclo
from app.models.finca import Finca
from app.models.movimientos import Gasto, Ingreso, Jornal
from app.models.usuario import IntentoIngreso, Token, Usuario


def _agricultor(db: Session, id_usuario: str) -> Usuario:
    """Busca una cuenta de agricultor por su identificador; si no existe o es el administrador responde 404 (E-07)."""
    usuario = db.get(Usuario, id_usuario)
    if usuario is None or usuario.rol != "AGRICULTOR":
        raise ErrorApi(404, "E-07")
    return usuario


def listar(db: Session, estado: str | None, pagina: int, limite: int) -> dict:
    """Lista las cuentas de agricultores ordenadas por fecha de creación, con filtro de estado y paginación."""
    filtro = [Usuario.rol == "AGRICULTOR"]
    if estado:
        filtro.append(Usuario.estado == estado)
    total = db.scalar(select(func.count()).select_from(Usuario).where(*filtro))
    filas = db.scalars(select(Usuario).where(*filtro).order_by(Usuario.creado_en, Usuario.id_usuario)
                       .offset((pagina - 1) * limite).limit(limite))
    return {"total": total, "pagina": pagina,
            "usuarios": [{"id": u.id_usuario, "nombre": u.nombre, "ubicacion": u.ubicacion, "correo": u.correo,
                          "estado": u.estado, "rol": u.rol, "creado_en": a_iso(u.creado_en)} for u in filas]}


def cambiar_clave(db: Session, id_usuario: str, clave_nueva) -> None:
    """Valida y guarda la clave nueva, quita el bloqueo y revoca todas las sesiones de la cuenta."""
    usuario = _agricultor(db, id_usuario)
    if v.v_clave(clave_nueva, usuario.correo, usuario.nombre):
        raise ErroresDeCampos({"clave_nueva": ("V-07", texto("V-07"))})
    usuario.hash_clave = seguridad.hashear_clave(clave_nueva)
    usuario.intentos_fallidos = 0
    usuario.bloqueado_hasta = None
    for t in db.scalars(select(Token).where(Token.id_usuario == usuario.id_usuario)):
        t.revocado = True
    db.execute(delete(IntentoIngreso).where(IntentoIngreso.correo == usuario.correo))
    db.commit()


def eliminar(db: Session, id_usuario: str) -> None:
    """Borra la cuenta con todos sus datos (cascada en la base) y los intentos de ingreso de su correo. El administrador no se borra (E-09)."""
    usuario = db.get(Usuario, id_usuario)
    if usuario is None:
        raise ErrorApi(404, "E-07")
    if usuario.rol == "ADMIN":
        raise ErrorApi(409, "E-09")
    db.execute(delete(IntentoIngreso).where(IntentoIngreso.correo == usuario.correo))
    db.delete(usuario)  # la base de datos borra en cascada fincas, ciclos, cultivos de cada ciclo, movimientos, tokens y códigos
    db.commit()


def resumen(db: Session, id_usuario: str) -> dict:
    """Cuenta las fincas, ciclos y movimientos de una cuenta y lista sus fincas con los ciclos activos de cada una."""
    usuario = _agricultor(db, id_usuario)
    fincas = []
    totales = {"fincas": 0, "ciclos": 0, "gastos": 0, "jornales": 0, "ingresos": 0}
    for finca in db.scalars(select(Finca).where(Finca.id_usuario == id_usuario).order_by(Finca.nombre, Finca.id_finca)):
        activos = db.scalar(select(func.count()).select_from(Ciclo)
                            .where(Ciclo.id_finca == finca.id_finca, Ciclo.estado == "ACTIVO"))
        fincas.append({"id": finca.id_finca, "nombre": finca.nombre, "ciclos_activos": activos})
    base_ciclos = select(Ciclo.id_ciclo).join(Finca, Finca.id_finca == Ciclo.id_finca).where(Finca.id_usuario == id_usuario)
    totales["fincas"] = len(fincas)
    totales["ciclos"] = db.scalar(select(func.count()).select_from(base_ciclos.subquery()))
    for nombre, modelo in (("gastos", Gasto), ("jornales", Jornal), ("ingresos", Ingreso)):
        totales[nombre] = db.scalar(select(func.count()).select_from(modelo).where(modelo.id_ciclo.in_(base_ciclos)))
    return {"usuario": {"id": usuario.id_usuario, "nombre": usuario.nombre, "ubicacion": usuario.ubicacion,
                        "correo": usuario.correo, "estado": usuario.estado, "creado_en": a_iso(usuario.creado_en)},
            "fincas": fincas, "totales": totales}
