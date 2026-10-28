"""USUARIO, OTP, TOKEN e INTENTO_INGRESO (documento 12)."""
from datetime import datetime

from sqlalchemy import Boolean, Computed, DateTime, Enum, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.connection import Base


class Usuario(Base):
    __tablename__ = "usuario"
    __table_args__ = (UniqueConstraint("solo_admin", name="uq_usuario_un_solo_admin"),)

    id_usuario: Mapped[str] = mapped_column(String(36), primary_key=True)
    nombre: Mapped[str] = mapped_column(String(60), nullable=False)
    ubicacion: Mapped[str] = mapped_column(String(60), nullable=False)
    correo: Mapped[str] = mapped_column(String(254), nullable=False, unique=True)
    hash_clave: Mapped[str] = mapped_column(String(255), nullable=False)
    rol: Mapped[str] = mapped_column(Enum("AGRICULTOR", "ADMIN", name="rol_usuario"), nullable=False)
    estado: Mapped[str] = mapped_column(Enum("PENDIENTE", "ACTIVA", name="estado_usuario"), nullable=False)
    intentos_fallidos: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    bloqueado_hasta: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    consentimiento_ley1581: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    creado_en: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    # Columna generada: vale 1 solo para el administrador; el UNIQUE impide un segundo ADMIN.
    solo_admin: Mapped[int | None] = mapped_column(
        Integer, Computed("CASE WHEN rol = 'ADMIN' THEN 1 ELSE NULL END", persisted=True), nullable=True)

    otps: Mapped[list["Otp"]] = relationship(back_populates="usuario", passive_deletes=True)
    tokens: Mapped[list["Token"]] = relationship(back_populates="usuario", passive_deletes=True)
    fincas: Mapped[list["Finca"]] = relationship(back_populates="usuario", passive_deletes=True)  # noqa: F821


class Otp(Base):
    __tablename__ = "otp"

    id_otp: Mapped[str] = mapped_column(String(36), primary_key=True)
    id_usuario: Mapped[str] = mapped_column(
        ForeignKey("usuario.id_usuario", ondelete="CASCADE", onupdate="RESTRICT"), nullable=False, index=True)
    codigo_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    enviado_en: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    expira_en: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    intentos_fallidos: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    reenvios: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    usado: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    usuario: Mapped[Usuario] = relationship(back_populates="otps")


class Token(Base):
    __tablename__ = "token"

    id_token: Mapped[str] = mapped_column(String(36), primary_key=True)
    id_usuario: Mapped[str] = mapped_column(
        ForeignKey("usuario.id_usuario", ondelete="CASCADE", onupdate="RESTRICT"), nullable=False, index=True)
    token_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    tipo: Mapped[str] = mapped_column(Enum("SESION", "ACTIVACION", name="tipo_token"), nullable=False)
    creado_en: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    expira_en: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    revocado: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    usuario: Mapped[Usuario] = relationship(back_populates="tokens")


class IntentoIngreso(Base):
    """Fallos de ingreso por correo, exista o no la cuenta; no tiene llave foránea (documento 12)."""
    __tablename__ = "intento_ingreso"

    correo: Mapped[str] = mapped_column(String(254), primary_key=True)
    intentos_fallidos: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    bloqueado_hasta: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    actualizado_en: Mapped[datetime] = mapped_column(DateTime, nullable=False)
