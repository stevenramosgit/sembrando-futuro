"""Sincronización: S-01 (push) y S-02 (pull). Regla de conflictos: última escritura gana (LWW) por updated_at."""
import re
from datetime import date, datetime

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.errores import ErrorApi, texto
from app.core.seguridad import ahora
from app.domain import fechas, formulas, validaciones as v
from app.domain.fechas import a_iso, leer_fecha, leer_fecha_hora
from app.models.ciclo import Ciclo
from app.models.ciclo_cultivo import CicloCultivo
from app.models.cultivo import Cultivo
from app.models.finca import Finca
from app.models.movimientos import Gasto, Ingreso, Jornal
from app.models.usuario import Usuario

MAX_REGISTROS = 500
ORDEN = ("finca", "ciclo", "ciclo_cultivo", "gasto", "jornal", "ingreso")
MODELOS = {"finca": Finca, "ciclo": Ciclo, "ciclo_cultivo": CicloCultivo, "gasto": Gasto, "jornal": Jornal,
           "ingreso": Ingreso}
PK = {"finca": "id_finca", "ciclo": "id_ciclo", "ciclo_cultivo": "id_ciclo_cultivo", "gasto": "id_gasto",
      "jornal": "id_jornal", "ingreso": "id_ingreso"}
PADRE = {"ciclo": ("finca_id", "id_finca", Finca), "ciclo_cultivo": ("ciclo_id", "id_ciclo", Ciclo),
         "gasto": ("ciclo_id", "id_ciclo", Ciclo), "jornal": ("ciclo_id", "id_ciclo", Ciclo),
         "ingreso": ("ciclo_id", "id_ciclo", Ciclo)}
MOVIMIENTOS = ("gasto", "jornal", "ingreso")
NO_ELIMINABLES = ("finca", "ciclo", "ciclo_cultivo")
_ID = re.compile(r"^[A-Za-z0-9_-]{1,36}$")


class Rechazo(Exception):
    """Un registro de la sincronización no cumple una regla: se rechaza solo ese registro, los demás siguen."""
    def __init__(self, codigo: str, **valores):
        """codigo: regla incumplida (V-xx o E-xx); valores: datos para completar el mensaje."""
        self.codigo = codigo
        self.valores = valores


# ---------------------------------------------------------------------------- propietario
def _dueno(db: Session, tipo: str, id_: str) -> str | None:
    """id_usuario dueño del registro o None si el registro no existe."""
    modelo = MODELOS[tipo]
    fila = db.get(modelo, id_)
    if fila is None:
        return None
    return _dueno_de_fila(db, tipo, fila)


def _dueno_de_fila(db: Session, tipo: str, fila) -> str:
    """Sube por los padres (movimiento → ciclo → finca) hasta llegar a la finca y devuelve su dueño."""
    while tipo != "finca":
        _, _, modelo_padre = PADRE[tipo]
        fila = db.get(modelo_padre, getattr(fila, _fk(tipo)))
        tipo = _tipo_padre(tipo)
    return fila.id_usuario


def _fk(tipo: str) -> str:
    """Nombre de la columna que apunta al padre de cada tipo de registro."""
    return {"ciclo": "id_finca", "ciclo_cultivo": "id_ciclo", "gasto": "id_ciclo", "jornal": "id_ciclo",
            "ingreso": "id_ciclo"}[tipo]


def _tipo_padre(tipo: str) -> str:
    """Tipo del padre de cada tipo de registro (el ciclo es hijo de la finca; los demás, del ciclo)."""
    return {"ciclo": "finca", "ciclo_cultivo": "ciclo", "gasto": "ciclo", "jornal": "ciclo", "ingreso": "ciclo"}[tipo]


# ---------------------------------------------------------------------------- serialización
def _num(valor):
    """Convierte un decimal en número JSON (o None)."""
    return None if valor is None else float(valor)


def a_registro(tipo: str, fila) -> dict:
    """Registro en el formato de S-01/S-02."""
    if tipo == "finca":
        datos = {"nombre": fila.nombre}
    elif tipo == "ciclo":
        datos = {"finca_id": fila.id_finca, "nombre_lote": fila.nombre_lote, "pendiente_pct": _num(fila.pendiente_pct),
                 "area_bruta_ha": _num(fila.area_bruta_ha), "area_no_sembrable_ha": _num(fila.area_no_sembrable_ha),
                 "area_efectiva_ha": _num(fila.area_efectiva_ha), "fecha_siembra": fila.fecha_siembra.isoformat(),
                 "vigencia_anios": fila.vigencia_anios, "estado": fila.estado,
                 "fecha_cierre": fila.fecha_cierre.isoformat() if fila.fecha_cierre else None}
    elif tipo == "ciclo_cultivo":
        datos = {"ciclo_id": fila.id_ciclo, "cultivo_codigo": fila.cultivo.codigo, "marco": fila.marco,
                 "dist_a_m": _num(fila.dist_a_m), "dist_b_m": _num(fila.dist_b_m)}
    elif tipo == "gasto":
        datos = {"ciclo_id": fila.id_ciclo, "fecha": fila.fecha.isoformat(), "categoria": fila.categoria,
                 "valor_cop": int(fila.valor_cop), "observaciones": fila.observaciones}
    elif tipo == "jornal":
        datos = {"ciclo_id": fila.id_ciclo, "fecha": fila.fecha.isoformat(), "jornales": _num(fila.cantidad_jornales),
                 "valor_diario_cop": int(fila.valor_jornal_cop)}
    else:
        datos = {"ciclo_id": fila.id_ciclo, "cultivo_codigo": fila.cultivo.codigo, "fecha": fila.fecha.isoformat(),
                 "cantidad": _num(fila.cantidad), "precio_unitario_cop": int(fila.precio_unitario_cop),
                 "unidad_comercial": fila.unidad_comercial}
    return {"tipo": tipo, "id": getattr(fila, PK[tipo]), "updated_at": a_iso(fila.updated_at),
            "eliminado": tipo in MOVIMIENTOS and fila.eliminado, "datos": datos}


# ---------------------------------------------------------------------------- validación por tipo
def _texto_o_none(valor):
    """Devuelve el valor si es texto; si no, None (así un número no pasa como nombre)."""
    return valor if isinstance(valor, str) else None


def _fecha(datos, campo="fecha"):
    """Lee una fecha AAAA-MM-DD de los datos; si no es válida rechaza el registro (V-28)."""
    f = leer_fecha(datos.get(campo))
    if f is None:
        raise Rechazo("V-28")
    return f


def _validar_finca(db, datos, existente, padre, usuario):
    """Valida el nombre de la finca (V-22) y devuelve los valores a guardar."""
    nombre = _texto_o_none(datos.get("nombre"))
    if v.v_nombre_lugar(nombre):
        raise Rechazo("V-22")
    return {"nombre": nombre.strip()}


def _validar_nombre_lote(datos):
    """El nombre del lote es un texto informativo y opcional; devuelve el texto limpio o None."""
    nombre_lote = datos.get("nombre_lote")
    if nombre_lote is not None and (not isinstance(nombre_lote, str) or nombre_lote.strip()):
        if v.v_nombre_lugar(nombre_lote):
            raise Rechazo("V-22")
    return nombre_lote.strip() if isinstance(nombre_lote, str) and nombre_lote.strip() else None


def _validar_estado_ciclo(datos, siembra, hoy):
    """Valida el estado del ciclo y, si está CERRADO, la fecha de cierre (entre la siembra y hoy)."""
    estado = datos.get("estado", "ACTIVO")
    if estado not in ("ACTIVO", "CERRADO"):
        raise Rechazo("E-03")
    cierre = None
    if estado == "CERRADO":
        cierre = _fecha(datos, "fecha_cierre")
        if v.v_cierre(cierre, siembra, hoy):
            raise Rechazo("V-29")
    return estado, cierre


def _validar_ciclo(db, datos, existente, padre, usuario):
    """CICLO absorbe los datos que antes tenía LOTE."""
    nombre_lote = _validar_nombre_lote(datos)
    bruta, pendiente, no_sembrable = datos.get("area_bruta_ha"), datos.get("pendiente_pct"), datos.get("area_no_sembrable_ha")
    if v.v_area_bruta(bruta):
        raise Rechazo("V-24")
    if v.v_pendiente(pendiente):
        raise Rechazo("V-25")
    if v.v_no_sembrable(no_sembrable, bruta):
        raise Rechazo("V-26")
    siembra = _fecha(datos, "fecha_siembra")
    hoy = fechas.hoy()
    if v.v_siembra(siembra, hoy):
        raise Rechazo("V-48")
    vigencia = datos.get("vigencia_anios")
    if v.v_vigencia(vigencia):
        raise Rechazo("V-49")
    estado, cierre = _validar_estado_ciclo(datos, siembra, hoy)
    b, n = v.decimal_de(bruta, 4), v.decimal_de(no_sembrable, 4)
    return {"nombre_lote": nombre_lote, "area_bruta_ha": b, "area_no_sembrable_ha": n,
            "area_efectiva_ha": formulas.area_efectiva(b, n), "pendiente_pct": v.decimal_de(pendiente, 2),
            "fecha_siembra": siembra, "vigencia_anios": v.entero_de(vigencia) if vigencia is not None else None,
            "estado": estado, "fecha_cierre": cierre}


def _cultivo_por_codigo(db, codigo):
    """Busca un cultivo del catálogo por su código (sin importar mayúsculas)."""
    return db.scalar(select(Cultivo).where(Cultivo.codigo == codigo.upper())) if isinstance(codigo, str) else None


def _validar_ciclo_cultivo(db, datos, existente, padre: Ciclo, usuario, updated_at=None):
    """Cultivo de un ciclo (tabla intermedia): cada cultivo trae su propio marco de siembra y distancias."""
    cultivo = _cultivo_por_codigo(db, datos.get("cultivo_codigo"))
    if cultivo is None:
        raise Rechazo("V-27")
    if existente is not None and existente.id_cultivo != cultivo.id_cultivo:
        raise Rechazo("E-03")
    _comprobar_ciclo_abierto(padre, updated_at)
    repetido = db.scalar(select(CicloCultivo.id_ciclo_cultivo).where(
        CicloCultivo.id_ciclo == padre.id_ciclo, CicloCultivo.id_cultivo == cultivo.id_cultivo,
        CicloCultivo.id_ciclo_cultivo != (existente.id_ciclo_cultivo if existente else "")))
    if repetido:
        raise Rechazo("V-50")
    marco = datos.get("marco")
    dist_a = dist_b = None
    if marco is not None:
        if marco not in v.MARCOS:
            raise Rechazo("V-32")
        if v.v_distancia(datos.get("dist_a_m")):
            raise Rechazo("V-33")
        dist_a = v.decimal_de(datos.get("dist_a_m"), 2)
        if marco == "rectangular":
            if v.v_distancia(datos.get("dist_b_m")):
                raise Rechazo("V-33")
            dist_b = v.decimal_de(datos.get("dist_b_m"), 2)
    return {"cultivo": cultivo, "id_cultivo": cultivo.id_cultivo, "marco": marco, "dist_a_m": dist_a, "dist_b_m": dist_b}


def _comprobar_ciclo_abierto(ciclo: Ciclo, updated_at: datetime):
    """V-31: un ciclo cerrado no admite registros nuevos; los anteriores al cierre (offline) sí se aceptan."""
    if ciclo.estado == "CERRADO" and updated_at > ciclo.updated_at:
        raise Rechazo("V-31")


def _fecha_registro(fecha: date, ciclo: Ciclo):
    """La fecha de un movimiento debe estar entre la siembra del ciclo y hoy (V-47)."""
    if v.v_fecha_registro(fecha, ciclo.fecha_siembra, fechas.hoy()):
        raise Rechazo("V-47")


def _validar_gasto(db, datos, existente, padre: Ciclo, usuario, updated_at=None):
    """Valida un gasto: fecha, ciclo abierto, categoría (V-37), valor y observaciones."""
    fecha = _fecha(datos)
    _comprobar_ciclo_abierto(padre, updated_at)
    if datos.get("categoria") not in v.CATEGORIAS:
        raise Rechazo("V-37")
    valor = v.v_valor_gasto(datos.get("valor_cop"))
    if valor:
        raise Rechazo(valor)
    obs = datos.get("observaciones")
    if v.v_observaciones(obs):
        raise Rechazo("V-38")
    _fecha_registro(fecha, padre)
    return {"fecha": fecha, "categoria": datos["categoria"], "valor_cop": v.entero_de(datos["valor_cop"]),
            "observaciones": obs.strip() if isinstance(obs, str) and obs.strip() else None}


def _validar_jornal(db, datos, existente, padre: Ciclo, usuario, updated_at=None):
    """Valida un jornal: fecha, ciclo abierto, cantidad en medios jornales (V-39) y valor diario (V-40)."""
    fecha = _fecha(datos)
    _comprobar_ciclo_abierto(padre, updated_at)
    if v.v_jornales(datos.get("jornales")):
        raise Rechazo("V-39")
    if v.v_valor_jornal(datos.get("valor_diario_cop")):
        raise Rechazo("V-40")
    _fecha_registro(fecha, padre)
    return {"fecha": fecha, "cantidad_jornales": v.decimal_de(datos["jornales"], 1),
            "valor_jornal_cop": v.entero_de(datos["valor_diario_cop"])}


def _cultivo_del_ingreso(db, datos, padre: Ciclo) -> Cultivo:
    """El ingreso es la venta de un cultivo del ciclo. Si el ciclo tiene un solo cultivo, puede omitirse el código."""
    propios = list(db.scalars(select(CicloCultivo).where(CicloCultivo.id_ciclo == padre.id_ciclo)))
    codigo = datos.get("cultivo_codigo")
    if codigo is None and len(propios) == 1:
        return propios[0].cultivo
    cultivo = _cultivo_por_codigo(db, codigo)
    if cultivo is None or cultivo.id_cultivo not in {c.id_cultivo for c in propios}:
        raise Rechazo("V-27")
    return cultivo


def _validar_ingreso(db, datos, existente, padre: Ciclo, usuario, updated_at=None):
    """Valida un ingreso: fecha, ciclo abierto, cultivo del ciclo, cantidad (V-41) y precio (V-42)."""
    fecha = _fecha(datos)
    _comprobar_ciclo_abierto(padre, updated_at)
    cultivo = _cultivo_del_ingreso(db, datos, padre)
    if v.v_cantidad(datos.get("cantidad")):
        raise Rechazo("V-41")
    if v.v_precio(datos.get("precio_unitario_cop")):
        raise Rechazo("V-42")
    _fecha_registro(fecha, padre)
    return {"fecha": fecha, "cantidad": v.decimal_de(datos["cantidad"], 4),
            "precio_unitario_cop": v.entero_de(datos["precio_unitario_cop"]),
            "unidad_comercial": cultivo.unidad_comercial, "cultivo": cultivo, "id_cultivo": cultivo.id_cultivo}


VALIDADORES = {"finca": _validar_finca, "ciclo": _validar_ciclo, "ciclo_cultivo": _validar_ciclo_cultivo,
               "gasto": _validar_gasto, "jornal": _validar_jornal, "ingreso": _validar_ingreso}
CON_MARCA_DE_TIEMPO = MOVIMIENTOS + ("ciclo_cultivo",)  # su validador comprueba V-31 con el updated_at recibido


# ---------------------------------------------------------------------------- S-01
def _prevalidar(registros) -> list[tuple[str, str, datetime]]:
    """Revisa el lote completo antes de aplicar nada: máximo 500 registros (E-04), identificadores UUID, fechas de
    modificación ISO 8601 y tipos conocidos.
    """
    if len(registros) > MAX_REGISTROS:
        raise ErrorApi(400, "E-04")
    leidos = []
    for r in registros:
        momento = leer_fecha_hora(r.updated_at)
        if momento is None or not _ID.match(r.id) or not isinstance(r.datos, dict):
            raise ErrorApi(400, "E-03")
        leidos.append((r.tipo, r.id, momento))
    return leidos


def _comprobar_propiedad(db: Session, usuario: Usuario, registros) -> None:
    """Si algún id (o el padre que cita) pertenece a otra cuenta, se rechaza toda la petición (403, E-02)."""
    for r in registros:
        if r.tipo not in MODELOS:
            continue
        dueno = _dueno(db, r.tipo, r.id)
        if dueno is not None and dueno != usuario.id_usuario:
            raise ErrorApi(403, "E-02")
        if r.tipo in PADRE:
            campo, _, _ = PADRE[r.tipo]
            id_padre = r.datos.get(campo)
            if isinstance(id_padre, str):
                dueno_padre = _dueno(db, _tipo_padre(r.tipo), id_padre)
                if dueno_padre is not None and dueno_padre != usuario.id_usuario:
                    raise ErrorApi(403, "E-02")


def _resolver_padre(db: Session, usuario: Usuario, tipo: str, r, existente):
    """Devuelve el registro padre (None en la finca) y comprueba que el registro pertenece a quien lo envía."""
    if tipo not in PADRE:
        if existente is not None and existente.id_usuario != usuario.id_usuario:
            raise ErrorApi(403, "E-02")
        return None
    campo, _, modelo_padre = PADRE[tipo]
    id_padre = r.datos.get(campo)
    padre = db.get(modelo_padre, id_padre) if isinstance(id_padre, str) else None
    if padre is None:
        raise Rechazo("E-01")
    if existente is not None and getattr(existente, _fk(tipo)) != id_padre:
        raise Rechazo("E-03")
    return padre


def _crear_fila(db: Session, usuario: Usuario, tipo: str, r, valores: dict, padre, updated_at: datetime) -> None:
    """Crea la fila nueva con el UUID que generó el teléfono y la enlaza con su dueño o con su padre."""
    fila = MODELOS[tipo](**{PK[tipo]: r.id}, **valores, updated_at=updated_at)
    if tipo in MOVIMIENTOS:
        fila.eliminado = False
    if tipo == "finca":
        fila.id_usuario = usuario.id_usuario
    elif tipo in PADRE:
        setattr(fila, _fk(tipo), getattr(padre, PADRE[tipo][1]))
    db.add(fila)


def _actualizar_fila(tipo: str, existente, valores: dict, updated_at: datetime) -> None:
    """Copia los valores nuevos en la fila existente y su fecha de modificación."""
    for k, val in valores.items():
        setattr(existente, k, val)
    existente.updated_at = updated_at
    if tipo in MOVIMIENTOS:
        existente.eliminado = False  # un registro eliminado vuelve a la vida si llega una versión más nueva (deshacer)


def _aplicar(db: Session, usuario: Usuario, r, updated_at: datetime) -> dict:
    """Aplica un registro. Regla de conflictos: gana la versión con la fecha de modificación más reciente; si la del servidor
    es igual o más nueva, responde ACTUALIZADO_POR_SERVIDOR con su copia para que el teléfono la adopte.
    """
    tipo = r.tipo
    existente = db.get(MODELOS[tipo], r.id)
    if tipo in NO_ELIMINABLES and r.eliminado:
        raise Rechazo("E-11")
    if existente is not None and updated_at <= existente.updated_at:
        return {"id": r.id, "estado": "ACTUALIZADO_POR_SERVIDOR", "updated_at": a_iso(existente.updated_at),
                "registro": a_registro(tipo, existente)}

    padre = _resolver_padre(db, usuario, tipo, r, existente)
    aceptado = {"id": r.id, "estado": "ACEPTADO", "updated_at": a_iso(updated_at)}

    if tipo in MOVIMIENTOS and r.eliminado:
        if existente is not None:
            _comprobar_ciclo_abierto(padre, updated_at)
            existente.eliminado = True
            existente.updated_at = updated_at
        return aceptado

    if tipo in CON_MARCA_DE_TIEMPO:
        valores = VALIDADORES[tipo](db, r.datos, existente, padre, usuario, updated_at)
    else:
        valores = VALIDADORES[tipo](db, r.datos, existente, padre, usuario)
    valores.pop("cultivo", None)
    if existente is None:
        _crear_fila(db, usuario, tipo, r, valores, padre, updated_at)
    else:
        _actualizar_fila(tipo, existente, valores, updated_at)
    db.flush()
    return aceptado


def push(db: Session, usuario: Usuario, entrada) -> dict:
    """S-01: valida el lote y la propiedad de los registros, los aplica en orden de dependencia (finca, ciclo, cultivos,
    movimientos) y devuelve un resultado por registro. Un registro rechazado no impide guardar los demás.
    """
    leidos = _prevalidar(entrada.registros)
    _comprobar_propiedad(db, usuario, entrada.registros)
    resultados: dict[int, dict] = {}
    indices = sorted(range(len(entrada.registros)),
                     key=lambda i: (ORDEN.index(entrada.registros[i].tipo) if entrada.registros[i].tipo in ORDEN else 99, i))
    for i in indices:
        r = entrada.registros[i]
        if r.tipo not in MODELOS:
            resultados[i] = _rechazado(r.id, "E-05")
            continue
        try:
            with db.begin_nested():
                resultados[i] = _aplicar(db, usuario, r, leidos[i][2])
        except Rechazo as e:
            resultados[i] = _rechazado(r.id, e.codigo, **e.valores)
        except IntegrityError:
            resultados[i] = _rechazado(r.id, "E-03")
    db.commit()
    return {"resultados": [resultados[i] for i in range(len(entrada.registros))]}


def _rechazado(id_: str, codigo: str, **valores) -> dict:
    """Resultado RECHAZADO de un registro, con el código y el mensaje de la regla."""
    return {"id": id_, "estado": "RECHAZADO", "codigo": codigo, "mensaje": texto(codigo, **valores)}


# ---------------------------------------------------------------------------- S-02
def _consulta_usuario(tipo: str, usuario_id: str):
    """Consulta que filtra las filas de un tipo que pertenecen al usuario (siguiendo finca → ciclo)."""
    modelo = MODELOS[tipo]
    q = select(modelo)
    if tipo == "finca":
        return q.where(Finca.id_usuario == usuario_id)
    if tipo == "ciclo":
        return q.join(Finca, Finca.id_finca == Ciclo.id_finca).where(Finca.id_usuario == usuario_id)
    return (q.join(Ciclo, Ciclo.id_ciclo == modelo.id_ciclo).join(Finca, Finca.id_finca == Ciclo.id_finca)
            .where(Finca.id_usuario == usuario_id))


def _leer_tipo(db: Session, usuario: Usuario, tipo: str, corte, hasta=None, tope=None):
    """Lee las filas de un tipo del usuario modificadas entre 'corte' y 'hasta', ordenadas por fecha, con un tope."""
    modelo = MODELOS[tipo]
    q = _consulta_usuario(tipo, usuario.id_usuario)
    if corte is not None:
        q = q.where(modelo.updated_at > corte)
    if hasta is not None:
        q = q.where(modelo.updated_at <= hasta)
    q = q.order_by(modelo.updated_at, getattr(modelo, PK[tipo]))
    if tope:
        q = q.limit(tope)
    return list(db.scalars(q))


def _hay_mas_despues(db: Session, usuario: Usuario, hasta) -> bool:
    """Indica si quedan registros posteriores a la página entregada (para que el teléfono pida otra)."""
    return any(
        db.scalar(_consulta_usuario(tipo, usuario.id_usuario).where(MODELOS[tipo].updated_at > hasta).limit(1)) is not None
        for tipo in ORDEN)


def pull(db: Session, usuario: Usuario, desde: str | None, limite: int) -> dict:
    """S-02: valida 'desde' y 'limite', reúne los cambios del usuario en orden de dependencia y los entrega por páginas."""
    if limite < 1 or limite > MAX_REGISTROS:
        raise ErrorApi(400, "E-03")
    corte = None
    if desde is not None:
        corte = leer_fecha_hora(desde)
        if corte is None:
            raise ErrorApi(400, "E-03")
    servidor_ahora = ahora()

    primeras = []
    for tipo in ORDEN:
        primeras += [(f.updated_at, ORDEN.index(tipo), getattr(f, PK[tipo]))
                     for f in _leer_tipo(db, usuario, tipo, corte, tope=limite + 1)]
    primeras.sort()
    hasta = primeras[limite - 1][0] if len(primeras) > limite else None  # se incluyen todos los que comparten ese instante
    hay_mas = hasta is not None and _hay_mas_despues(db, usuario, hasta)
    filas = []
    for tipo in ORDEN:
        filas += [(f.updated_at, ORDEN.index(tipo), getattr(f, PK[tipo]), tipo, f)
                  for f in _leer_tipo(db, usuario, tipo, corte, hasta=hasta)]
    filas.sort(key=lambda x: x[:3])
    return {"servidor_ahora": a_iso(servidor_ahora), "hay_mas": hay_mas,
            "registros": [a_registro(t, f) for _, _, _, t, f in filas]}
