"""Las migraciones de Alembic (0001 y 0002) crean exactamente el esquema que describen los modelos."""
import os

from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.config import Config
from alembic.migration import MigrationContext
from sqlalchemy import inspect

from app.database.connection import Base, engine

RAIZ = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))


def test_migracion_inicial_coincide_con_los_modelos():
    Base.metadata.drop_all(engine)
    cfg = Config(os.path.join(RAIZ, "alembic.ini"))
    cfg.set_main_option("script_location", os.path.join(RAIZ, "alembic"))
    command.upgrade(cfg, "head")
    assert set(inspect(engine).get_table_names()) == {"alembic_version", "usuario", "otp", "token", "intento_ingreso", "cultivo",
                                                      "finca", "ficha_tecnica", "ciclo", "ciclo_cultivo", "gasto", "jornal", "ingreso"}
    with engine.connect() as c:
        assert compare_metadata(MigrationContext.configure(c), Base.metadata) == []
    command.downgrade(cfg, "base")
    assert inspect(engine).get_table_names() == ["alembic_version"]
