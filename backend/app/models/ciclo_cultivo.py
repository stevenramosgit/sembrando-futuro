"""CICLO_CULTIVO: tabla intermedia (muchos a muchos) entre CICLO y CULTIVO. Un ciclo puede tener varios cultivos y
cada uno guarda su propio marco de siembra y sus distancias."""
from datetime import datetime

from sqlalchemy import Enum, ForeignKey, Numeric, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.connection import Base
from app.models.tipos import FechaHora6


class CicloCultivo(Base):
    __tablename__ = "ciclo_cultivo"
    __table_args__ = (UniqueConstraint("id_ciclo", "id_cultivo", name="uq_ciclo_cultivo"),)

    id_ciclo_cultivo: Mapped[str] = mapped_column(String(36), primary_key=True)
    id_ciclo: Mapped[str] = mapped_column(
        ForeignKey("ciclo.id_ciclo", ondelete="CASCADE", onupdate="RESTRICT"), nullable=False, index=True)
    id_cultivo: Mapped[int] = mapped_column(
        ForeignKey("cultivo.id_cultivo", ondelete="RESTRICT", onupdate="RESTRICT"), nullable=False)
    marco: Mapped[str | None] = mapped_column(Enum("cuadrado", "rectangular", "tresbolillo", name="marco_siembra"), nullable=True)
    dist_a_m: Mapped[float | None] = mapped_column(Numeric(5, 2), nullable=True)
    dist_b_m: Mapped[float | None] = mapped_column(Numeric(5, 2), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(FechaHora6, nullable=False, index=True)

    ciclo = relationship("Ciclo", back_populates="cultivos")
    cultivo = relationship("Cultivo")
