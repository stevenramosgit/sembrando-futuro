"""Catálogo de cultivos (C-01) y su edición por el administrador (AD-04)."""
import json

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errores import ErrorApi, ErroresDeCampos
from app.core.seguridad import ahora
from app.domain import validaciones as v
from app.domain.fechas import a_iso, leer_fecha_hora
from app.models.cultivo import Cultivo
from app.models.ficha_tecnica import FichaTecnica

CAMPOS_ENTEROS = ("costo_hoyado_cop", "costo_colino_cop", "insumo_anual_cop")
CAMPOS_JORNALES = ("jornales_limpieza_anio", "jornales_riego_anio")


def ficha_a_dict(f: FichaTecnica | None) -> dict | None:
    if f is None:
        return None
    return {"base_plantas": f.base_plantas, "costo_hoyado_cop": int(f.costo_hoyado_cop),
            "costo_colino_cop": int(f.costo_colino_cop), "insumo_anual_cop": int(f.insumo_anual_cop),
            "jornales_limpieza_anio": float(f.jornales_limpieza_anio), "jornales_riego_anio": float(f.jornales_riego_anio),
            "datos_extra": f.datos_extra}


def a_dict(c: Cultivo) -> dict:
    return {"codigo": c.codigo, "nombre": c.nombre, "unidad_comercial": c.unidad_comercial,
            "distancia_min_m": float(c.distancia_min_m), "distancia_max_m": float(c.distancia_max_m),
            "marcos_permitidos": list(c.marcos_permitidos), "fuente_tecnica": c.fuente_tecnica,
            "ficha_tecnica": ficha_a_dict(c.ficha), "actualizado_en": a_iso(c.actualizado_en)}


def consultar(db: Session, desde: str | None) -> dict | None:
    """None significa «sin cambios» (la ruta responde 304)."""
    consulta = select(Cultivo).order_by(Cultivo.codigo)
    if desde is not None:
        momento = leer_fecha_hora(desde)
        if momento is None:
            raise ErrorApi(400, "E-03")
        consulta = consulta.where(Cultivo.actualizado_en > momento)
    cultivos = list(db.scalars(consulta))
    if desde is not None and not cultivos:
        return None
    todos = cultivos if desde is None else list(db.scalars(select(Cultivo)))
    ultimo = max((c.actualizado_en for c in todos), default=ahora())
    return {"version": 1, "actualizado_en": a_iso(ultimo), "cultivos": [a_dict(c) for c in cultivos]}


def _largo(valor, minimo, maximo) -> bool:
    return isinstance(valor, str) and minimo <= len(valor.strip()) <= maximo


def _validar_ficha(ficha, fallo) -> dict | None:
    """Valida la ficha técnica recibida en AD-04; los errores se informan como 'ficha_tecnica.<campo>' (E-08)."""
    if not isinstance(ficha, dict):
        fallo("ficha_tecnica", "La ficha técnica debe ser un objeto con sus campos.")
        return None
    valores: dict = {}
    base = v.entero_de(ficha.get("base_plantas", 1000))
    if base is None or not 1 <= base <= 100000:
        fallo("ficha_tecnica.base_plantas", "La base de plantas debe ser un entero entre 1 y 100.000.")
    valores["base_plantas"] = base
    for campo in CAMPOS_ENTEROS:
        n = v.entero_de(ficha.get(campo))
        if n is None or not 0 <= n <= 50_000_000:
            fallo("ficha_tecnica." + campo, "Escriba un valor entero entre $0 y $50.000.000.")
        valores[campo] = n
    for campo in CAMPOS_JORNALES:
        n = v.decimal_de(ficha.get(campo), 1)
        if n is None or not 0 <= n <= 999:
            fallo("ficha_tecnica." + campo, "Escriba los jornales por año, de 0 a 999, con un decimal como máximo.")
        valores[campo] = n
    extra = ficha.get("datos_extra")
    if extra is not None and not (isinstance(extra, dict) and len(json.dumps(extra, ensure_ascii=False)) <= 2000):
        fallo("ficha_tecnica.datos_extra", "Los datos extra deben ser un objeto JSON de hasta 2.000 caracteres.")
    valores["datos_extra"] = extra
    return valores


def _validar_distancias(d, fallo):
    minimo = v.decimal_de(d.distancia_min_m, 2)
    maximo = v.decimal_de(d.distancia_max_m, 2)
    if v.v_distancia(d.distancia_min_m):
        fallo("distancia_min_m", "La distancia mínima debe estar entre 0,01 y 10 metros.")
    if v.v_distancia(d.distancia_max_m) or (minimo is not None and maximo is not None and maximo < minimo):
        fallo("distancia_max_m", "La distancia máxima debe estar entre la mínima y 10 metros.")
    return minimo, maximo


def _marcos_validos(marcos) -> bool:
    return bool(isinstance(marcos, list) and marcos and len(set(marcos)) == len(marcos)
                and all(m in v.MARCOS for m in marcos))


def _validar_cultivo(d, fallo):
    """Valida los datos del cultivo; devuelve (mínimo, máximo, valores de la ficha o None)."""
    if not _largo(d.nombre, 2, 60):
        fallo("nombre", "Escriba un nombre de 2 a 60 caracteres.")
    if not _largo(d.unidad_comercial, 3, 80):
        fallo("unidad_comercial", "Escriba la unidad comercial (3 a 80 caracteres).")
    minimo, maximo = _validar_distancias(d, fallo)
    if not _marcos_validos(d.marcos_permitidos):
        fallo("marcos_permitidos", "Elija al menos un marco: cuadrado, rectangular o tresbolillo, sin repetir.")
    if not _largo(d.fuente_tecnica, 5, 300):
        fallo("fuente_tecnica", "Escriba la fuente técnica (5 a 300 caracteres).")
    valores_ficha = _validar_ficha(d.ficha_tecnica, fallo) if d.ficha_tecnica is not None else None
    return minimo, maximo, valores_ficha


def _guardar_ficha(cultivo: Cultivo, valores_ficha: dict) -> None:
    if cultivo.ficha is None:
        cultivo.ficha = FichaTecnica(**valores_ficha, actualizado_en=ahora().replace(microsecond=0))
        return
    for k, val in valores_ficha.items():
        setattr(cultivo.ficha, k, val)
    cultivo.ficha.actualizado_en = ahora().replace(microsecond=0)


def actualizar(db: Session, codigo: str, d) -> dict:
    cultivo = db.scalar(select(Cultivo).where(Cultivo.codigo == codigo.upper()))
    if cultivo is None:
        raise ErrorApi(404, "E-07")
    malos: dict[str, tuple[str, str]] = {}

    def fallo(campo: str, mensaje: str):
        malos[campo] = ("E-08", mensaje)

    minimo, maximo, valores_ficha = _validar_cultivo(d, fallo)
    if malos:
        raise ErroresDeCampos(malos, codigo="E-08")

    cultivo.nombre = d.nombre.strip()
    cultivo.unidad_comercial = d.unidad_comercial.strip()
    cultivo.distancia_min_m = minimo
    cultivo.distancia_max_m = maximo
    cultivo.marcos_permitidos = list(d.marcos_permitidos)
    cultivo.fuente_tecnica = d.fuente_tecnica.strip()
    if valores_ficha is not None:
        _guardar_ficha(cultivo, valores_ficha)
    cultivo.actualizado_en = ahora().replace(microsecond=0)
    db.commit()
    return a_dict(cultivo)
