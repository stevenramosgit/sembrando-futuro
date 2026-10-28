"""FICHA_TECNICA: costos e insumos aproximados de un cultivo, calculados sobre una base de plantas (1.000 por defecto).

Los tres costos son en pesos por planta (el de insumos, por planta y por año); los jornales son por cada
'base_plantas' plantas y por año. 'datos_extra' (JSON) guarda variables propias de un cultivo sin alterar la ficha.
"""
from datetime import datetime

from sqlalchemy import BigInteger, CheckConstraint, DateTime, ForeignKey, Integer, JSON, Numeric
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.connection import Base


class FichaTecnica(Base):
    __tablename__ = "ficha_tecnica"
    __table_args__ = (
        CheckConstraint("base_plantas >= 1 AND base_plantas <= 100000", name="ck_ficha_base"),
        CheckConstraint("costo_hoyado_cop >= 0 AND costo_hoyado_cop <= 50000000", name="ck_ficha_hoyado"),
        CheckConstraint("costo_colino_cop >= 0 AND costo_colino_cop <= 50000000", name="ck_ficha_colino"),
        CheckConstraint("insumo_anual_cop >= 0 AND insumo_anual_cop <= 50000000", name="ck_ficha_insumo"),
        CheckConstraint("jornales_limpieza_anio >= 0 AND jornales_limpieza_anio <= 999", name="ck_ficha_limpieza"),
        CheckConstraint("jornales_riego_anio >= 0 AND jornales_riego_anio <= 999", name="ck_ficha_riego"),
    )

    id_ficha: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    id_cultivo: Mapped[int] = mapped_column(
        ForeignKey("cultivo.id_cultivo", ondelete="CASCADE", onupdate="RESTRICT"), nullable=False, unique=True)
    base_plantas: Mapped[int] = mapped_column(Integer, nullable=False, default=1000)
    costo_hoyado_cop: Mapped[int] = mapped_column(BigInteger, nullable=False)
    costo_colino_cop: Mapped[int] = mapped_column(BigInteger, nullable=False)
    insumo_anual_cop: Mapped[int] = mapped_column(BigInteger, nullable=False)
    jornales_limpieza_anio: Mapped[float] = mapped_column(Numeric(5, 1), nullable=False)
    jornales_riego_anio: Mapped[float] = mapped_column(Numeric(5, 1), nullable=False)
    datos_extra: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    actualizado_en: Mapped[datetime] = mapped_column(DateTime, nullable=False)

    cultivo = relationship("Cultivo", back_populates="ficha")
