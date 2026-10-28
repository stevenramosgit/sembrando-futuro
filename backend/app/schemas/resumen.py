from pydantic import BaseModel


class ResumenCiclo(BaseModel):
    ciclo: dict
    cultivos: list[dict]
    total_matas: int | None
    gastos_cop: int
    jornales_cop: int
    costos_totales_cop: int
    ingresos_cop: int
    utilidad_neta_cop: int
    rentabilidad_pct: float
    utilidad_por_ha_cop: int
    registros: dict


class ResumenUsuario(BaseModel):
    usuario: dict
    fincas: list[dict]
    totales: dict
