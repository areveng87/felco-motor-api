"""Modelos de base de datos."""
import uuid
from datetime import datetime
from sqlalchemy import Column, String, Integer, Float, Text, DateTime, JSON
from database import Base


def new_id() -> str:
    return uuid.uuid4().hex


class Car(Base):
    __tablename__ = "cars"

    id = Column(String(32), primary_key=True, default=new_id)
    vin = Column(String(32), unique=True, index=True)   # identificador unico del coche
    make = Column(String(80), nullable=False)
    model = Column(String(120), nullable=False)
    version = Column(String(200))
    year = Column(Integer, nullable=False)
    price = Column(Float, default=0)
    mileage = Column(Integer, default=0)
    fuel = Column(String(40), default="")
    transmission = Column(String(40), default="")
    power = Column(Integer, default=0)
    doors = Column(Integer, default=0)
    color = Column(String(80))
    body = Column(String(60))
    location = Column(String(120))
    description = Column(Text)
    images = Column(JSON, default=list)
    status = Column(String(20), default="available")    # available | sold
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class ContactMessage(Base):
    __tablename__ = "contact_messages"

    id = Column(String(32), primary_key=True, default=new_id)
    car_id = Column(String(64))
    car_title = Column(String(200))
    name = Column(String(120), nullable=False)
    email = Column(String(160), nullable=False)
    phone = Column(String(60))
    message = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
