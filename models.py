"""Modelos de base de datos."""
import uuid
from datetime import datetime
from sqlalchemy import Column, String, Integer, Float, Text, DateTime, JSON, UniqueConstraint
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
    monthly_payment = Column(Float, default=0)          # cuota de financiacion ($/mes), 0 si no tiene
    mileage = Column(Integer, default=0)
    fuel = Column(String(40), default="")
    transmission = Column(String(40), default="")
    power = Column(Integer, default=0)
    doors = Column(Integer, default=0)
    color = Column(String(80))
    body = Column(String(60))
    location = Column(String(120))
    description = Column(Text)                            # descripcion original (EN)
    description_es = Column(Text)                         # descripcion traducida (ES)
    images = Column(JSON, default=list)
    details = Column(JSON, default=dict)                 # todas las specs de la ficha (clave->valor)
    features = Column(JSON, default=list)                # equipamiento / opciones (EN)
    features_es = Column(JSON, default=list)             # equipamiento traducido (ES)
    status = Column(String(20), default="available")    # available | sold
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class Favorite(Base):
    __tablename__ = "favorites"

    id = Column(String(32), primary_key=True, default=new_id)
    user_uid = Column(String(128), index=True, nullable=False)   # UID de Firebase
    car_id = Column(String(32), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (UniqueConstraint("user_uid", "car_id", name="uq_fav_user_car"),)


class Device(Base):
    __tablename__ = "devices"

    id = Column(String(32), primary_key=True, default=new_id)
    user_uid = Column(String(128), index=True, nullable=False)   # UID de Firebase
    token = Column(String(400), unique=True, nullable=False)     # token FCM del dispositivo
    platform = Column(String(20), default="android")
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


class Alert(Base):
    __tablename__ = "alerts"

    id = Column(String(32), primary_key=True, default=new_id)
    user_uid = Column(String(128), index=True, nullable=False)
    email = Column(String(160), nullable=False)          # a donde se envian las propuestas
    name = Column(String(120), nullable=False)
    criteria = Column(JSON, default=dict)                # q, make, model, year, body, minPrice, maxPrice
    created_at = Column(DateTime, default=datetime.utcnow)


class AlertSent(Base):
    __tablename__ = "alert_sent"

    id = Column(String(32), primary_key=True, default=new_id)
    alert_id = Column(String(32), index=True, nullable=False)
    car_id = Column(String(32), nullable=False)
    sent_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (UniqueConstraint("alert_id", "car_id", name="uq_alert_car"),)
