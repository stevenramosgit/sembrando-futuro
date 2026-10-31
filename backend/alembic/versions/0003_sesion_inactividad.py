"""Cierre de sesión por inactividad: la tabla TOKEN guarda la hora de la última petición hecha con cada token.

Revision ID: 0003
Revises: 0002
Create Date: 2026-10-30
"""
from alembic import op
import sqlalchemy as sa

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Agrega TOKEN.usado_en (puede ser nula: un token recién creado aún no se ha usado)."""
    with op.batch_alter_table("token") as t:
        t.add_column(sa.Column("usado_en", sa.DateTime, nullable=True))


def downgrade() -> None:
    """Quita la columna agregada."""
    with op.batch_alter_table("token") as t:
        t.drop_column("usado_en")
