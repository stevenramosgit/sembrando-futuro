"""Conexión a la base de datos: lee el archivo .env (documento 20)."""
import os
from collections.abc import Iterator

from sqlalchemy import create_engine, event
from sqlalchemy.engine import URL
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.core.config import config


def construir_url():
    """Dirección de conexión: DATABASE_URL si existe (pruebas con SQLite en memoria); si no, MySQL 8 con las variables DB_*."""
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
    """Crea el motor de SQLAlchemy. Con MySQL revisa la conexión antes de usarla (pre_ping) y la renueva cada 280 s,
    porque los servidores cierran las conexiones inactivas. Con SQLite activa las llaves foráneas, que vienen apagadas.
    """
    url = url or construir_url()
    es_sqlite = str(url).startswith("sqlite")
    opciones = {"pool_pre_ping": True, "pool_recycle": 280}
    if config.db_ssl_ca:  # Aiven exige TLS; DB_SSL_CA es la ruta del certificado de su autoridad (backend/ca.pem)
        if not es_sqlite and not os.path.isfile(config.db_ssl_ca):
            raise RuntimeError(f"No existe el certificado {config.db_ssl_ca}: descargue el CA certificate de Aiven "
                               "y guárdelo como backend/ca.pem antes de migrar o arrancar.")
        opciones["connect_args"] = {"ssl": {"ca": config.db_ssl_ca}}
    if es_sqlite:
        from sqlalchemy.pool import StaticPool
        opciones = {"connect_args": {"check_same_thread": False}, "poolclass": StaticPool}
    motor = create_engine(url, **opciones)
    if es_sqlite:
        @event.listens_for(motor, "connect")
        def _activar_llaves_foraneas(conexion, _):
            """SQLite ignora las llaves foráneas si no se activan en cada conexión; sin esto no se probarían las cascadas."""
            conexion.execute("PRAGMA foreign_keys=ON")  # SQLite las ignora si no se activan
    return motor


engine = crear_motor()
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)


class Base(DeclarativeBase):
    """Clase base de todos los modelos (tablas) de SQLAlchemy."""
    pass


def get_db() -> Iterator[Session]:
    """Dependencia de FastAPI: abre una sesión de base de datos por petición y la cierra al terminar, aunque haya error."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
