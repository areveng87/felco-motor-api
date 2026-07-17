"""Esquemas Pydantic (contrato JSON que consume la app)."""
from typing import List, Optional
from pydantic import BaseModel, ConfigDict


class CarBase(BaseModel):
    model_config = ConfigDict(protected_namespaces=())

    make: str
    model: str
    version: Optional[str] = None
    year: int
    price: float = 0
    mileage: int = 0
    fuel: str = ""
    transmission: str = ""
    power: int = 0
    doors: int = 0
    color: Optional[str] = None
    body: Optional[str] = None
    location: Optional[str] = None
    description: Optional[str] = None
    images: List[str] = []


class CarIn(CarBase):
    """Datos para crear o actualizar un coche (sin id)."""
    pass


class CarOut(CarBase):
    """Coche devuelto por la API (con id como string)."""
    model_config = ConfigDict(from_attributes=True, protected_namespaces=())
    id: str
    vin: Optional[str] = None
    status: str = "available"


class ContactIn(BaseModel):
    carId: Optional[str] = None
    carTitle: Optional[str] = None
    name: str
    email: str
    phone: Optional[str] = None
    message: str
