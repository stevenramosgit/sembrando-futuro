"""Esquema inicial: 12 tablas del documento 12 (sin LOTE; con CICLO_CULTIVO y FICHA_TECNICA) con llaves foráneas, únicos y CHECK escritos de forma explícita.

Revision ID: 0001
Revises:
Create Date: 2026-10-27
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None

# DATETIME con fracciones de segundo en MariaDB/MySQL (los registros sincronizables comparan updated_at al milisegundo)
FECHA_HORA_6 = sa.DateTime().with_variant(mysql.DATETIME(fsp=6), "mysql", "mariadb")
CASCADA = dict(ondelete="CASCADE", onupdate="RESTRICT")
RESTRINGIR = dict(ondelete="RESTRICT", onupdate="RESTRICT")


def upgrade() -> None:
    op.create_table(
        "usuario",
        sa.Column("id_usuario", sa.String(36), primary_key=True),
        sa.Column("nombre", sa.String(60), nullable=False),
        sa.Column("ubicacion", sa.String(60), nullable=False),
        sa.Column("correo", sa.String(254), nullable=False),
        sa.Column("hash_clave", sa.String(255), nullable=False),
        sa.Column("rol", sa.Enum("AGRICULTOR", "ADMIN", name="rol_usuario"), nullable=False),
        sa.Column("estado", sa.Enum("PENDIENTE", "ACTIVA", name="estado_usuario"), nullable=False),
        sa.Column("intentos_fallidos", sa.Integer, nullable=False, server_default="0"),
        sa.Column("bloqueado_hasta", sa.DateTime, nullable=True),
        sa.Column("consentimiento_ley1581", sa.Boolean, nullable=False, server_default=sa.false()),
        sa.Column("creado_en", sa.DateTime, nullable=False),
        # Columna generada: vale 1 solo para el administrador y NULL para los demás; el UNIQUE impide un segundo ADMIN.
        sa.Column("solo_admin", sa.Integer, sa.Computed("CASE WHEN rol = 'ADMIN' THEN 1 ELSE NULL END", persisted=True), nullable=True),
        sa.UniqueConstraint("correo", name="uq_usuario_correo"),
        sa.UniqueConstraint("solo_admin", name="uq_usuario_un_solo_admin"),
        mysql_engine="InnoDB", mysql_charset="utf8mb4",
    )
    op.create_table(
        "otp",
        sa.Column("id_otp", sa.String(36), primary_key=True),
        sa.Column("id_usuario", sa.String(36), sa.ForeignKey("usuario.id_usuario", name="fk_otp_usuario", **CASCADA), nullable=False),
        sa.Column("codigo_hash", sa.String(64), nullable=False),
        sa.Column("enviado_en", sa.DateTime, nullable=False),
        sa.Column("expira_en", sa.DateTime, nullable=False),
        sa.Column("intentos_fallidos", sa.Integer, nullable=False, server_default="0"),
        sa.Column("reenvios", sa.Integer, nullable=False, server_default="0"),
        sa.Column("usado", sa.Boolean, nullable=False, server_default=sa.false()),
        mysql_engine="InnoDB", mysql_charset="utf8mb4",
    )
    op.create_index("ix_otp_id_usuario", "otp", ["id_usuario"])
    op.create_table(
        "token",
        sa.Column("id_token", sa.String(36), primary_key=True),
        sa.Column("id_usuario", sa.String(36), sa.ForeignKey("usuario.id_usuario", name="fk_token_usuario", **CASCADA), nullable=False),
        sa.Column("token_hash", sa.String(64), nullable=False),
        sa.Column("tipo", sa.Enum("SESION", "ACTIVACION", name="tipo_token"), nullable=False),
        sa.Column("creado_en", sa.DateTime, nullable=False),
        sa.Column("expira_en", sa.DateTime, nullable=False),
        sa.Column("revocado", sa.Boolean, nullable=False, server_default=sa.false()),
        sa.UniqueConstraint("token_hash", name="uq_token_hash"),
        mysql_engine="InnoDB", mysql_charset="utf8mb4",
    )
    op.create_index("ix_token_id_usuario", "token", ["id_usuario"])
    op.create_table(
        "intento_ingreso",
        sa.Column("correo", sa.String(254), primary_key=True),
        sa.Column("intentos_fallidos", sa.Integer, nullable=False, server_default="0"),
        sa.Column("bloqueado_hasta", sa.DateTime, nullable=True),
        sa.Column("actualizado_en", sa.DateTime, nullable=False),
        mysql_engine="InnoDB", mysql_charset="utf8mb4",
    )
    op.create_table(
        "cultivo",
        sa.Column("id_cultivo", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("codigo", sa.String(20), nullable=False),
        sa.Column("nombre", sa.String(60), nullable=False),
        sa.Column("distancia_min_m", sa.Numeric(5, 2), nullable=False),
        sa.Column("distancia_max_m", sa.Numeric(5, 2), nullable=False),
        sa.Column("marcos_permitidos", sa.JSON, nullable=False),
        sa.Column("unidad_comercial", sa.String(80), nullable=False),
        sa.Column("fuente_tecnica", sa.String(300), nullable=False),
        sa.Column("actualizado_en", sa.DateTime, nullable=False),
        sa.UniqueConstraint("codigo", name="uq_cultivo_codigo"),
        sa.CheckConstraint("distancia_min_m >= 0.01 AND distancia_min_m <= 10", name="ck_cultivo_min"),
        sa.CheckConstraint("distancia_max_m >= distancia_min_m AND distancia_max_m <= 10", name="ck_cultivo_max"),
        mysql_engine="InnoDB", mysql_charset="utf8mb4",
    )
    op.create_table(
        "finca",
        sa.Column("id_finca", sa.String(36), primary_key=True),
        sa.Column("id_usuario", sa.String(36), sa.ForeignKey("usuario.id_usuario", name="fk_finca_usuario", **CASCADA), nullable=False),
        sa.Column("nombre", sa.String(60), nullable=False),
        sa.Column("updated_at", FECHA_HORA_6, nullable=False),
        mysql_engine="InnoDB", mysql_charset="utf8mb4",
    )
    op.create_index("ix_finca_id_usuario", "finca", ["id_usuario"])
    op.create_index("ix_finca_updated_at", "finca", ["updated_at"])
    op.create_table(
        "ficha_tecnica",
        sa.Column("id_ficha", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("id_cultivo", sa.Integer, sa.ForeignKey("cultivo.id_cultivo", name="fk_ficha_cultivo", **CASCADA), nullable=False),
        sa.Column("base_plantas", sa.Integer, nullable=False, server_default="1000"),
        sa.Column("costo_hoyado_cop", sa.BigInteger, nullable=False),
        sa.Column("costo_colino_cop", sa.BigInteger, nullable=False),
        sa.Column("insumo_anual_cop", sa.BigInteger, nullable=False),
        sa.Column("jornales_limpieza_anio", sa.Numeric(5, 1), nullable=False),
        sa.Column("jornales_riego_anio", sa.Numeric(5, 1), nullable=False),
        sa.Column("datos_extra", sa.JSON, nullable=True),
        sa.Column("actualizado_en", sa.DateTime, nullable=False),
        sa.UniqueConstraint("id_cultivo", name="uq_ficha_cultivo"),
        sa.CheckConstraint("base_plantas >= 1 AND base_plantas <= 100000", name="ck_ficha_base"),
        sa.CheckConstraint("costo_hoyado_cop >= 0 AND costo_hoyado_cop <= 50000000", name="ck_ficha_hoyado"),
        sa.CheckConstraint("costo_colino_cop >= 0 AND costo_colino_cop <= 50000000", name="ck_ficha_colino"),
        sa.CheckConstraint("insumo_anual_cop >= 0 AND insumo_anual_cop <= 50000000", name="ck_ficha_insumo"),
        sa.CheckConstraint("jornales_limpieza_anio >= 0 AND jornales_limpieza_anio <= 999", name="ck_ficha_limpieza"),
        sa.CheckConstraint("jornales_riego_anio >= 0 AND jornales_riego_anio <= 999", name="ck_ficha_riego"),
        mysql_engine="InnoDB", mysql_charset="utf8mb4",
    )
    op.create_table(
        "ciclo",
        sa.Column("id_ciclo", sa.String(36), primary_key=True),
        sa.Column("id_finca", sa.String(36), sa.ForeignKey("finca.id_finca", name="fk_ciclo_finca", **CASCADA), nullable=False),
        sa.Column("nombre_lote", sa.String(60), nullable=True),
        sa.Column("pendiente_pct", sa.Numeric(5, 2), nullable=False),
        sa.Column("area_bruta_ha", sa.Numeric(10, 4), nullable=False),
        sa.Column("area_no_sembrable_ha", sa.Numeric(10, 4), nullable=False),
        sa.Column("area_efectiva_ha", sa.Numeric(10, 4), nullable=False),
        sa.Column("fecha_siembra", sa.Date, nullable=False),
        sa.Column("vigencia_anios", sa.SmallInteger, nullable=True),
        sa.Column("estado", sa.Enum("ACTIVO", "CERRADO", name="estado_ciclo"), nullable=False),
        sa.Column("fecha_cierre", sa.Date, nullable=True),
        sa.Column("updated_at", FECHA_HORA_6, nullable=False),
        sa.CheckConstraint("pendiente_pct >= 0 AND pendiente_pct <= 100", name="ck_ciclo_pendiente"),
        sa.CheckConstraint("area_bruta_ha >= 0.0001 AND area_bruta_ha <= 10000", name="ck_ciclo_bruta"),
        sa.CheckConstraint("area_no_sembrable_ha >= 0 AND area_no_sembrable_ha < area_bruta_ha", name="ck_ciclo_no_sembrable"),
        sa.CheckConstraint("ABS(area_efectiva_ha - (area_bruta_ha - area_no_sembrable_ha)) < 0.00005", name="ck_ciclo_efectiva"),
        sa.CheckConstraint("vigencia_anios IS NULL OR (vigencia_anios >= 1 AND vigencia_anios <= 50)", name="ck_ciclo_vigencia"),
        mysql_engine="InnoDB", mysql_charset="utf8mb4",
    )
    op.create_index("ix_ciclo_id_finca", "ciclo", ["id_finca"])
    op.create_index("ix_ciclo_updated_at", "ciclo", ["updated_at"])
    op.create_table(
        "ciclo_cultivo",
        sa.Column("id_ciclo_cultivo", sa.String(36), primary_key=True),
        sa.Column("id_ciclo", sa.String(36), sa.ForeignKey("ciclo.id_ciclo", name="fk_ciclo_cultivo_ciclo", **CASCADA), nullable=False),
        sa.Column("id_cultivo", sa.Integer, sa.ForeignKey("cultivo.id_cultivo", name="fk_ciclo_cultivo_cultivo", **RESTRINGIR), nullable=False),
        sa.Column("marco", sa.Enum("cuadrado", "rectangular", "tresbolillo", name="marco_siembra"), nullable=True),
        sa.Column("dist_a_m", sa.Numeric(5, 2), nullable=True),
        sa.Column("dist_b_m", sa.Numeric(5, 2), nullable=True),
        sa.Column("updated_at", FECHA_HORA_6, nullable=False),
        sa.UniqueConstraint("id_ciclo", "id_cultivo", name="uq_ciclo_cultivo"),
        mysql_engine="InnoDB", mysql_charset="utf8mb4",
    )
    op.create_index("ix_ciclo_cultivo_id_ciclo", "ciclo_cultivo", ["id_ciclo"])
    op.create_index("ix_ciclo_cultivo_updated_at", "ciclo_cultivo", ["updated_at"])
    op.create_table(
        "gasto",
        sa.Column("id_gasto", sa.String(36), primary_key=True),
        sa.Column("id_ciclo", sa.String(36), sa.ForeignKey("ciclo.id_ciclo", name="fk_gasto_ciclo", **CASCADA), nullable=False),
        sa.Column("categoria", sa.Enum("semillas", "abonos", "agroquimicos", "herramientas", "transporte", "otros", name="categoria_gasto"), nullable=False),
        sa.Column("observaciones", sa.String(150), nullable=True),
        sa.Column("valor_cop", sa.BigInteger, nullable=False),
        sa.Column("fecha", sa.Date, nullable=False),
        sa.Column("updated_at", FECHA_HORA_6, nullable=False),
        sa.Column("eliminado", sa.Boolean, nullable=False, server_default=sa.false()),
        sa.CheckConstraint("valor_cop >= 1 AND valor_cop <= 50000000", name="ck_gasto_valor"),
        mysql_engine="InnoDB", mysql_charset="utf8mb4",
    )
    op.create_index("ix_gasto_id_ciclo", "gasto", ["id_ciclo"])
    op.create_index("ix_gasto_updated_at", "gasto", ["updated_at"])
    op.create_table(
        "jornal",
        sa.Column("id_jornal", sa.String(36), primary_key=True),
        sa.Column("id_ciclo", sa.String(36), sa.ForeignKey("ciclo.id_ciclo", name="fk_jornal_ciclo", **CASCADA), nullable=False),
        sa.Column("cantidad_jornales", sa.Numeric(5, 1), nullable=False),
        sa.Column("valor_jornal_cop", sa.BigInteger, nullable=False),
        sa.Column("fecha", sa.Date, nullable=False),
        sa.Column("updated_at", FECHA_HORA_6, nullable=False),
        sa.Column("eliminado", sa.Boolean, nullable=False, server_default=sa.false()),
        sa.CheckConstraint("cantidad_jornales >= 0.5 AND cantidad_jornales <= 999", name="ck_jornal_cantidad"),
        sa.CheckConstraint("valor_jornal_cop >= 1 AND valor_jornal_cop <= 50000000", name="ck_jornal_valor"),
        mysql_engine="InnoDB", mysql_charset="utf8mb4",
    )
    op.create_index("ix_jornal_id_ciclo", "jornal", ["id_ciclo"])
    op.create_index("ix_jornal_updated_at", "jornal", ["updated_at"])
    op.create_table(
        "ingreso",
        sa.Column("id_ingreso", sa.String(36), primary_key=True),
        sa.Column("id_ciclo", sa.String(36), sa.ForeignKey("ciclo.id_ciclo", name="fk_ingreso_ciclo", **CASCADA), nullable=False),
        sa.Column("id_cultivo", sa.Integer, sa.ForeignKey("cultivo.id_cultivo", name="fk_ingreso_cultivo", **RESTRINGIR), nullable=False),
        sa.Column("cantidad", sa.Numeric(10, 4), nullable=False),
        sa.Column("unidad_comercial", sa.String(80), nullable=False),
        sa.Column("precio_unitario_cop", sa.BigInteger, nullable=False),
        sa.Column("fecha", sa.Date, nullable=False),
        sa.Column("updated_at", FECHA_HORA_6, nullable=False),
        sa.Column("eliminado", sa.Boolean, nullable=False, server_default=sa.false()),
        sa.CheckConstraint("cantidad >= 0.1 AND cantidad <= 10000", name="ck_ingreso_cantidad"),
        sa.CheckConstraint("precio_unitario_cop >= 1 AND precio_unitario_cop <= 50000000", name="ck_ingreso_precio"),
        mysql_engine="InnoDB", mysql_charset="utf8mb4",
    )
    op.create_index("ix_ingreso_id_ciclo", "ingreso", ["id_ciclo"])
    op.create_index("ix_ingreso_updated_at", "ingreso", ["updated_at"])


def downgrade() -> None:
    for tabla in ("ingreso", "jornal", "gasto", "ciclo_cultivo", "ciclo", "ficha_tecnica", "finca", "cultivo", "intento_ingreso", "token", "otp", "usuario"):
        op.drop_table(tabla)
