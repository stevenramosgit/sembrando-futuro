"""GASTO, JORNAL e INGRESO: los únicos registros que el agricultor elimina (eliminación lógica)."""
from datetime import date, datetime

from sqlalchemy import BigInteger, Boolean, CheckConstraint, Date, Enum, ForeignKey, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.connection import Base
from app.models.tipos import FechaHora6

CATEGORIAS = ("semillas", "abonos", "agroquimicos", "herramientas", "transporte", "otros")


def _ciclo_fk():
    """Llave foránea al ciclo: si se borra el ciclo se borran sus movimientos (cascada)."""
    return mapped_column(ForeignKey("ciclo.id_ciclo", ondelete="CASCADE", onupdate="RESTRICT"), nullable=False, index=True)


class Gasto(Base):
    """Fila de la tabla GASTO: un gasto del ciclo con categoría, valor en pesos, fecha y observaciones opcionales.
    No se borra de verdad: se marca 'eliminado' para que el borrado también llegue a los otros dispositivos.
    """
    __tablename__ = "gasto"
    __table_args__ = (CheckConstraint("valor_cop >= 1 AND valor_cop <= 50000000", name="ck_gasto_valor"),)

    id_gasto: Mapped[str] = mapped_column(String(36), primary_key=True)
    id_ciclo: Mapped[str] = _ciclo_fk()
    categoria: Mapped[str] = mapped_column(Enum(*CATEGORIAS, name="categoria_gasto"), nullable=False)
    observaciones: Mapped[str | None] = mapped_column(String(150), nullable=True)
    valor_cop: Mapped[int] = mapped_column(BigInteger, nullable=False)
    fecha: Mapped[date] = mapped_column(Date, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(FechaHora6, nullable=False, index=True)
    eliminado: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    ciclo = relationship("Ciclo", back_populates="gastos")


class Jornal(Base):
    """Fila de la tabla JORNAL: días de trabajo pagados en el ciclo (cantidad de jornales y valor diario en pesos)."""
    __tablename__ = "jornal"
    __table_args__ = (
        CheckConstraint("cantidad_jornales >= 0.5 AND cantidad_jornales <= 999", name="ck_jornal_cantidad"),
        CheckConstraint("valor_jornal_cop >= 1 AND valor_jornal_cop <= 50000000", name="ck_jornal_valor"),
    )

    id_jornal: Mapped[str] = mapped_column(String(36), primary_key=True)
    id_ciclo: Mapped[str] = _ciclo_fk()
    cantidad_jornales: Mapped[float] = mapped_column(Numeric(5, 1), nullable=False)
    valor_jornal_cop: Mapped[int] = mapped_column(BigInteger, nullable=False)
    fecha: Mapped[date] = mapped_column(Date, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(FechaHora6, nullable=False, index=True)
    eliminado: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    ciclo = relationship("Ciclo", back_populates="jornales")


class Ingreso(Base):
    """Fila de la tabla INGRESO: una venta de cosecha (cultivo, cantidad en su unidad comercial y precio unitario en pesos)."""
    __tablename__ = "ingreso"
    __table_args__ = (
        CheckConstraint("cantidad >= 0.1 AND cantidad <= 10000", name="ck_ingreso_cantidad"),
        CheckConstraint("precio_unitario_cop >= 1 AND precio_unitario_cop <= 50000000", name="ck_ingreso_precio"),
    )

    id_ingreso: Mapped[str] = mapped_column(String(36), primary_key=True)
    id_ciclo: Mapped[str] = _ciclo_fk()
    id_cultivo: Mapped[int] = mapped_column(
        ForeignKey("cultivo.id_cultivo", ondelete="RESTRICT", onupdate="RESTRICT"), nullable=False)
    cantidad: Mapped[float] = mapped_column(Numeric(10, 4), nullable=False)
    unidad_comercial: Mapped[str] = mapped_column(String(80), nullable=False)
    precio_unitario_cop: Mapped[int] = mapped_column(BigInteger, nullable=False)
    fecha: Mapped[date] = mapped_column(Date, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(FechaHora6, nullable=False, index=True)
    eliminado: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    ciclo = relationship("Ciclo", back_populates="ingresos")
    cultivo = relationship("Cultivo")
