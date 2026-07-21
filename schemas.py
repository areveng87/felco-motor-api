"""Esquemas Pydantic (contrato JSON que consume la app)."""
from typing import Dict, List, Optional
from pydantic import BaseModel, ConfigDict


class CarBase(BaseModel):
    model_config = ConfigDict(protected_namespaces=())

    make: str
    model: str
    version: Optional[str] = None
    year: int
    price: float = 0
    monthly_payment: float = 0
    mileage: int = 0
    fuel: str = ""
    transmission: str = ""
    power: int = 0
    doors: int = 0
    color: Optional[str] = None
    body: Optional[str] = None
    location: Optional[str] = None
    description: Optional[str] = None
    description_es: Optional[str] = None
    images: List[str] = []
    details: Dict[str, str] = {}
    features: List[str] = []
    features_es: List[str] = []


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


class DeviceIn(BaseModel):
    token: str
    platform: Optional[str] = "android"


class AlertIn(BaseModel):
    name: Optional[str] = None
    criteria: Dict[str, str] = {}     # q, make, model, year, body, minPrice, maxPrice


class AlertOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    name: str
    email: str
    criteria: Dict[str, str] = {}


class NotifyIn(BaseModel):
    title: str
    body: str
    data: Optional[Dict[str, str]] = None
    # Atajos de destino (se traducen a 'data' automaticamente):
    #  - car_id: abre la ficha de ese coche
    #  - route:  abre una seccion (catalog | favorites | contact | profile)
    car_id: Optional[str] = None
    route: Optional[str] = None
