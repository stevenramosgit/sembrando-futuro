"""Esquemas de los resúmenes (R-01 y AD-05)."""
from pydantic import BaseModel


class ResumenCiclo(BaseModel):
    """Respuesta de R-01: totales en pesos enteros, rentabilidad en porcentaje y detalle por cultivo con su proyección."""
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
    """Respuesta de AD-05: datos de la cuenta, fincas y conteos."""
    usuario: dict
    fincas: list[dict]
    totales: dict
