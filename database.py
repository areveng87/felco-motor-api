"""Configuracion de la base de datos (SQLAlchemy)."""
import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

# Por defecto SQLite en un archivo local (cero configuracion).
# Para desplegar en otra BD, define DATABASE_URL, por ejemplo:
#   postgresql+psycopg://user:pass@host/dbname
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./ferco.db")

connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}
engine = create_engine(DATABASE_URL, connect_args=connect_args)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
Base = declarative_base()
