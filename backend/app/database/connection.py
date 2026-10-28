"""Conexión a la base de datos: lee el archivo .env (documento 20)."""
from collections.abc import Iterator

from sqlalchemy import create_engine, event
from sqlalchemy.engine import URL
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.core.config import config


def construir_url():
    if config.database_url:  # DATABASE_URL se usa en las pruebas (SQLite en memoria) y en alojamientos que la entregan
        return config.database_url
    return URL.create(
        "mysql+pymysql",
        username=config.db_user,
        password=config.db_password,
        host=config.db_host,
        port=config.db_port,
        database=config.db_name,
        query={"charset": "utf8mb4"},
    )


def crear_motor(url=None):
    url = url or construir_url()
    es_sqlite = str(url).startswith("sqlite")
    opciones = {"pool_pre_ping": True, "pool_recycle": 280}
    if config.db_ssl_ca:  # Aiven (demostración) exige TLS; DB_SSL_CA es la ruta del certificado de la autoridad
        opciones["connect_args"] = {"ssl": {"ca": config.db_ssl_ca}}
    if es_sqlite:
        from sqlalchemy.pool import StaticPool
        opciones = {"connect_args": {"check_same_thread": False}, "poolclass": StaticPool}
    motor = create_engine(url, **opciones)
    if es_sqlite:
        @event.listens_for(motor, "connect")
        def _activar_llaves_foraneas(conexion, _):
            conexion.execute("PRAGMA foreign_keys=ON")  # SQLite las ignora si no se activan
    return motor


engine = crear_motor()
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


def get_db() -> Iterator[Session]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
