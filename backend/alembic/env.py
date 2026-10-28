"""Entorno de Alembic: usa la misma conexión que la aplicación (archivo .env)."""
from logging.config import fileConfig

from alembic import context

from app.database import connection
from app.database.connection import Base
import app.models  # noqa: F401  (registra las tablas para autogenerate)

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)
target_metadata = Base.metadata


def run_migrations_offline() -> None:
    context.configure(url=str(connection.construir_url()), target_metadata=target_metadata, literal_binds=True,
                      dialect_opts={"paramstyle": "named"})
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    with connection.engine.connect() as conexion:
        context.configure(connection=conexion, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
