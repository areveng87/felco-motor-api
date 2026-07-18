"""Configuracion de la base de datos (SQLAlchemy)."""
import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

# Por defecto SQLite en un archivo local (cero configuracion).
# En produccion define DATABASE_URL (p.ej. la de Postgres de Render).
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./ferco.db")

# Render (y otros) entregan la URL como "postgres://..." pero SQLAlchemy 2
# necesita el driver explicito. Se normaliza a psycopg (psycopg 3).
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql+psycopg://", 1)
elif DATABASE_URL.startswith("postgresql://") and "+psycopg" not in DATABASE_URL:
    DATABASE_URL = DATABASE_URL.replace("postgresql://", "postgresql+psycopg://", 1)

connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}
# En Postgres, pool_pre_ping evita errores por conexiones caidas tras inactividad.
_engine_kwargs = {} if DATABASE_URL.startswith("sqlite") else {"pool_pre_ping": True}
engine = create_engine(DATABASE_URL, connect_args=connect_args, **_engine_kwargs)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
Base = declarative_base()
