"""FINCA: predio de un agricultor. Agrupa sus ciclos de cultivo; si se elimina la cuenta, se borran en cascada la finca y sus ciclos."""
from datetime import datetime

from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.connection import Base
from app.models.tipos import FechaHora6


class Finca(Base):
    """Fila de la tabla FINCA: identificador UUID creado en el teléfono, dueño (USUARIO), nombre y fecha de la última modificación
    (updated_at), que la sincronización usa para decidir qué versión es la más nueva.
    """
    __tablename__ = "finca"

    id_finca: Mapped[str] = mapped_column(String(36), primary_key=True)
    id_usuario: Mapped[str] = mapped_column(
        ForeignKey("usuario.id_usuario", ondelete="CASCADE", onupdate="RESTRICT"), nullable=False, index=True)
    nombre: Mapped[str] = mapped_column(String(60), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(FechaHora6, nullable=False, index=True)

    usuario = relationship("Usuario", back_populates="fincas")
    ciclos = relationship("Ciclo", back_populates="finca", passive_deletes=True)
