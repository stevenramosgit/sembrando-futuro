"""CICLO: ciclo de cultivo de una finca. Absorbe los datos que antes tenía LOTE (modelo simplificado):
el nombre del lote es solo un texto informativo y no forma parte de ninguna relación."""
from datetime import date, datetime

from sqlalchemy import CheckConstraint, Date, Enum, ForeignKey, Numeric, SmallInteger, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.connection import Base
from app.models.tipos import FechaHora6


class Ciclo(Base):
    """Fila de la tabla CICLO: un ciclo de cultivo en una finca (antes llamado lote). Guarda el área bruta, el área
    no sembrable, el área efectiva calculada, la pendiente, la fecha de siembra, los años de vigencia y el estado (ACTIVO o CERRADO).
    """
    __tablename__ = "ciclo"
    __table_args__ = (
        CheckConstraint("pendiente_pct >= 0 AND pendiente_pct <= 100", name="ck_ciclo_pendiente"),
        CheckConstraint("area_bruta_ha >= 0.0001 AND area_bruta_ha <= 10000", name="ck_ciclo_bruta"),
        CheckConstraint("area_no_sembrable_ha >= 0 AND area_no_sembrable_ha < area_bruta_ha", name="ck_ciclo_no_sembrable"),
        CheckConstraint("ABS(area_efectiva_ha - (area_bruta_ha - area_no_sembrable_ha)) < 0.00005", name="ck_ciclo_efectiva"),
        CheckConstraint("vigencia_anios IS NULL OR (vigencia_anios >= 1 AND vigencia_anios <= 50)", name="ck_ciclo_vigencia"),
    )

    id_ciclo: Mapped[str] = mapped_column(String(36), primary_key=True)
    id_finca: Mapped[str] = mapped_column(
        ForeignKey("finca.id_finca", ondelete="CASCADE", onupdate="RESTRICT"), nullable=False, index=True)
    nombre_lote: Mapped[str | None] = mapped_column(String(60), nullable=True)
    pendiente_pct: Mapped[float] = mapped_column(Numeric(5, 2), nullable=False)
    area_bruta_ha: Mapped[float] = mapped_column(Numeric(10, 4), nullable=False)
    area_no_sembrable_ha: Mapped[float] = mapped_column(Numeric(10, 4), nullable=False)
    area_efectiva_ha: Mapped[float] = mapped_column(Numeric(10, 4), nullable=False)
    fecha_siembra: Mapped[date] = mapped_column(Date, nullable=False)
    vigencia_anios: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)
    estado: Mapped[str] = mapped_column(Enum("ACTIVO", "CERRADO", name="estado_ciclo"), nullable=False)
    fecha_cierre: Mapped[date | None] = mapped_column(Date, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(FechaHora6, nullable=False, index=True)

    finca = relationship("Finca", back_populates="ciclos")
    cultivos = relationship("CicloCultivo", back_populates="ciclo", passive_deletes=True)
    gastos = relationship("Gasto", back_populates="ciclo", passive_deletes=True)
    jornales = relationship("Jornal", back_populates="ciclo", passive_deletes=True)
    ingresos = relationship("Ingreso", back_populates="ciclo", passive_deletes=True)
