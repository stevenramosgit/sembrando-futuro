"""Tipos de columna compartidos."""
from sqlalchemy import DateTime
from sqlalchemy.dialects import mysql

# Fecha y hora con 6 decimales de segundo (en MySQL, DATETIME(6)): se usa para updated_at, que decide la última escritura.
FechaHora6 = DateTime().with_variant(mysql.DATETIME(fsp=6), "mysql")
