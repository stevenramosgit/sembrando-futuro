"""Proyección de cosecha: la ficha técnica guarda temporada, producción y precio de referencia (en pesos).

Revision ID: 0002
Revises: 0001
Create Date: 2026-10-28
"""
from alembic import op
import sqlalchemy as sa

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("ficha_tecnica") as t:
        t.add_column(sa.Column("meses_primera_cosecha", sa.SmallInteger, nullable=True))
        t.add_column(sa.Column("meses_cosecha", sa.JSON, nullable=True))
        t.add_column(sa.Column("cosecha_unica", sa.Boolean, nullable=False, server_default="0"))
        t.add_column(sa.Column("produccion_base", sa.Numeric(10, 2), nullable=True))
        t.add_column(sa.Column("precio_ref_cop", sa.BigInteger, nullable=True))
        t.add_column(sa.Column("precio_ref_fecha", sa.Date, nullable=True))
        t.create_check_constraint("ck_ficha_meses", "meses_primera_cosecha IS NULL OR (meses_primera_cosecha >= 1 AND meses_primera_cosecha <= 120)")
        t.create_check_constraint("ck_ficha_produccion", "produccion_base IS NULL OR (produccion_base > 0 AND produccion_base <= 1000000)")
        t.create_check_constraint("ck_ficha_precio", "precio_ref_cop IS NULL OR (precio_ref_cop >= 0 AND precio_ref_cop <= 50000000)")


def downgrade() -> None:
    with op.batch_alter_table("ficha_tecnica") as t:
        t.drop_constraint("ck_ficha_precio", type_="check")
        t.drop_constraint("ck_ficha_produccion", type_="check")
        t.drop_constraint("ck_ficha_meses", type_="check")
        for col in ("precio_ref_fecha", "precio_ref_cop", "produccion_base", "cosecha_unica", "meses_cosecha", "meses_primera_cosecha"):
            t.drop_column(col)
