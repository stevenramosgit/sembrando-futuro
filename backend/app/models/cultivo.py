"""CULTIVO: catálogo de cultivos (documento 12). Nunca se borra: CICLO_CULTIVO e INGRESO lo referencian con RESTRICT."""
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, Integer, JSON, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.connection import Base


class Cultivo(Base):
    __tablename__ = "cultivo"
    __table_args__ = (
        CheckConstraint("distancia_min_m >= 0.01 AND distancia_min_m <= 10", name="ck_cultivo_min"),
        CheckConstraint("distancia_max_m >= distancia_min_m AND distancia_max_m <= 10", name="ck_cultivo_max"),
    )

    id_cultivo: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    codigo: Mapped[str] = mapped_column(String(20), nullable=False, unique=True)
    nombre: Mapped[str] = mapped_column(String(60), nullable=False)
    distancia_min_m: Mapped[float] = mapped_column(Numeric(5, 2), nullable=False)
    distancia_max_m: Mapped[float] = mapped_column(Numeric(5, 2), nullable=False)
    marcos_permitidos: Mapped[list] = mapped_column(JSON, nullable=False)
    unidad_comercial: Mapped[str] = mapped_column(String(80), nullable=False)
    fuente_tecnica: Mapped[str] = mapped_column(String(300), nullable=False)
    actualizado_en: Mapped[datetime] = mapped_column(DateTime, nullable=False)

    ficha = relationship("FichaTecnica", back_populates="cultivo", uselist=False, passive_deletes=True)
