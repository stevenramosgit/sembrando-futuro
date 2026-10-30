"""FICHA_TECNICA: costos e insumos aproximados de un cultivo, calculados sobre una base de plantas (1.000 por defecto).

Los tres costos son en pesos por planta (el de insumos, por planta y por año); los jornales son por cada
'base_plantas' plantas y por año. 'datos_extra' (JSON) guarda variables propias de un cultivo sin alterar la ficha.

Proyección de cosecha (opcional): meses_primera_cosecha (desde la siembra), meses_cosecha (temporadas del año, 1 a 12),
cosecha_unica (se cosecha una sola vez por siembra, como yuca y plátano; si es falso, produce cada año),
produccion_base (unidades comerciales por 'base_plantas' plantas, por año o por cosecha única) y precio_ref_cop con su fecha
(pesos por unidad comercial). Lo que se puede calcular (fecha de la primera cosecha, producción e ingreso estimados) no se guarda.
"""
from datetime import date, datetime

from sqlalchemy import BigInteger, Boolean, CheckConstraint, Date, DateTime, ForeignKey, Integer, JSON, Numeric, SmallInteger
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.connection import Base


class FichaTecnica(Base):
    """Fila de la tabla FICHA_TECNICA (una por cultivo). Ver la explicación de cada campo al inicio del módulo."""
    __tablename__ = "ficha_tecnica"
    __table_args__ = (
        CheckConstraint("base_plantas >= 1 AND base_plantas <= 100000", name="ck_ficha_base"),
        CheckConstraint("costo_hoyado_cop >= 0 AND costo_hoyado_cop <= 50000000", name="ck_ficha_hoyado"),
        CheckConstraint("costo_colino_cop >= 0 AND costo_colino_cop <= 50000000", name="ck_ficha_colino"),
        CheckConstraint("insumo_anual_cop >= 0 AND insumo_anual_cop <= 50000000", name="ck_ficha_insumo"),
        CheckConstraint("jornales_limpieza_anio >= 0 AND jornales_limpieza_anio <= 999", name="ck_ficha_limpieza"),
        CheckConstraint("jornales_riego_anio >= 0 AND jornales_riego_anio <= 999", name="ck_ficha_riego"),
        CheckConstraint("meses_primera_cosecha IS NULL OR (meses_primera_cosecha >= 1 AND meses_primera_cosecha <= 120)", name="ck_ficha_meses"),
        CheckConstraint("produccion_base IS NULL OR (produccion_base > 0 AND produccion_base <= 1000000)", name="ck_ficha_produccion"),
        CheckConstraint("precio_ref_cop IS NULL OR (precio_ref_cop >= 0 AND precio_ref_cop <= 50000000)", name="ck_ficha_precio"),
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
    meses_primera_cosecha: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)
    meses_cosecha: Mapped[list | None] = mapped_column(JSON, nullable=True)
    cosecha_unica: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="0")
    produccion_base: Mapped[float | None] = mapped_column(Numeric(10, 2), nullable=True)
    precio_ref_cop: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    precio_ref_fecha: Mapped[date | None] = mapped_column(Date, nullable=True)
    datos_extra: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    actualizado_en: Mapped[datetime] = mapped_column(DateTime, nullable=False)

    cultivo = relationship("Cultivo", back_populates="ficha")
