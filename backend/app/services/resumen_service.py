"""R-01: resumen de un ciclo con los mismos totales que muestra el panel de la PWA."""
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errores import ErrorApi
from app.domain import fechas, formulas
from app.models.ciclo import Ciclo
from app.models.ciclo_cultivo import CicloCultivo
from app.models.cultivo import Cultivo
from app.models.finca import Finca
from app.models.movimientos import Gasto, Ingreso, Jornal
from app.models.usuario import Usuario


def _num(x):
    """Convierte un decimal de la base en número JSON (o None)."""
    return None if x is None else float(x)


def _ficha(cultivo):
    """Ficha técnica del cultivo como diccionario, para las fórmulas de costos y de proyección."""
    f = cultivo.ficha
    if f is None:
        return None
    return {"base_plantas": f.base_plantas, "costo_hoyado_cop": int(f.costo_hoyado_cop),
            "costo_colino_cop": int(f.costo_colino_cop), "insumo_anual_cop": int(f.insumo_anual_cop),
            "jornales_limpieza_anio": float(f.jornales_limpieza_anio), "jornales_riego_anio": float(f.jornales_riego_anio),
            "meses_primera_cosecha": f.meses_primera_cosecha, "meses_cosecha": f.meses_cosecha, "cosecha_unica": bool(f.cosecha_unica),
            "produccion_base": None if f.produccion_base is None else float(f.produccion_base),
            "precio_ref_cop": None if f.precio_ref_cop is None else int(f.precio_ref_cop),
            "precio_ref_fecha": f.precio_ref_fecha.isoformat() if f.precio_ref_fecha else None}


def resumen_ciclo(db: Session, usuario: Usuario, id_ciclo: str) -> dict:
    """R-01: comprueba que el ciclo sea del usuario (si no, 403 E-02), suma gastos, jornales e ingresos no eliminados
    y calcula matas, utilidad, rentabilidad, utilidad por hectárea y la proyección de cosecha de cada cultivo.
    """
    ciclo = db.get(Ciclo, id_ciclo)
    if ciclo is None:
        raise ErrorApi(404, "E-07")
    finca = db.get(Finca, ciclo.id_finca)
    if finca.id_usuario != usuario.id_usuario:
        raise ErrorApi(403, "E-02")
    gastos = list(db.scalars(select(Gasto).where(Gasto.id_ciclo == id_ciclo, Gasto.eliminado.is_(False))))
    jornales = list(db.scalars(select(Jornal).where(Jornal.id_ciclo == id_ciclo, Jornal.eliminado.is_(False))))
    ingresos = list(db.scalars(select(Ingreso).where(Ingreso.id_ciclo == id_ciclo, Ingreso.eliminado.is_(False))))

    valores_gasto = [int(g.valor_cop) for g in gastos]
    valores_jornal = [formulas.costo_jornal(j.cantidad_jornales, j.valor_jornal_cop) for j in jornales]
    valores_ingreso = [formulas.total_ingreso(i.cantidad, i.precio_unitario_cop) for i in ingresos]
    _, costos, total_ingresos, utilidad, rentabilidad, por_ha = formulas.calcular_utilidad(
        valores_gasto + valores_jornal, valores_ingreso, ciclo.area_efectiva_ha)

    cultivos, total_matas = [], None
    filas = list(db.scalars(select(CicloCultivo).join(Cultivo, Cultivo.id_cultivo == CicloCultivo.id_cultivo)
                            .where(CicloCultivo.id_ciclo == id_ciclo)
                            .order_by(Cultivo.codigo)))
    for cc in filas:
        matas = None
        if cc.marco and cc.dist_a_m is not None:
            r = formulas.matas_por_hectarea(cc.marco, float(cc.dist_a_m), float(cc.dist_b_m) if cc.dist_b_m is not None else 0, None)
            if r[0] == "ok":
                matas = formulas.matas_del_ciclo(cc.marco, float(cc.dist_a_m), float(cc.dist_b_m) if cc.dist_b_m is not None else 0, ciclo.area_efectiva_ha)
                total_matas = (total_matas or 0) + matas
        ficha = _ficha(cc.cultivo)
        estimado = formulas.estimar_costos(ficha, matas) if ficha and matas is not None else None
        proyeccion = formulas.proyectar_cosecha(ficha, matas, ciclo.fecha_siembra) if ficha and matas is not None else None
        if proyeccion:
            proyeccion["primera_cosecha"] = proyeccion["primera_cosecha"].isoformat()
        cultivos.append({"codigo": cc.cultivo.codigo, "nombre": cc.cultivo.nombre,
                         "unidad_comercial": cc.cultivo.unidad_comercial, "marco": cc.marco,
                         "dist_a_m": _num(cc.dist_a_m), "dist_b_m": _num(cc.dist_b_m), "matas": matas,
                         "estimado_ficha": estimado, "proyeccion": proyeccion})

    fin, restantes, semaforo = formulas.semaforo_vigencia(ciclo.fecha_siembra, ciclo.vigencia_anios, fechas.hoy())
    ciclo_datos = {"id": ciclo.id_ciclo, "estado": ciclo.estado, "nombre_lote": ciclo.nombre_lote,
                   "area_efectiva_ha": _num(ciclo.area_efectiva_ha), "fecha_siembra": ciclo.fecha_siembra.isoformat(),
                   "fecha_cierre": ciclo.fecha_cierre.isoformat() if ciclo.fecha_cierre else None,
                   "vigencia_anios": ciclo.vigencia_anios,
                   "fecha_fin_estimada": fin.isoformat() if fin else None, "anios_restantes": restantes,
                   "semaforo": semaforo}
    return {"ciclo": ciclo_datos, "cultivos": cultivos,
            "total_matas": total_matas, "gastos_cop": sum(valores_gasto), "jornales_cop": sum(valores_jornal),
            "costos_totales_cop": costos, "ingresos_cop": total_ingresos, "utilidad_neta_cop": utilidad,
            "rentabilidad_pct": rentabilidad, "utilidad_por_ha_cop": por_ha,
            "registros": {"gastos": len(gastos), "jornales": len(jornales), "ingresos": len(ingresos)}}
