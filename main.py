"""
FercoMotors API (FastAPI + SQLite)

Mismos endpoints y contrato que consume la app .NET MAUI:
  GET    /v1/cars            (filtros: q, fuel, maxPrice, minYear, maxMileage, body, sort)
  GET    /v1/cars/{id}
  POST   /v1/cars
  PUT    /v1/cars/{id}
  DELETE /v1/cars/{id}
  POST   /v1/contact

Arrancar:
  uvicorn main:app --host 0.0.0.0 --port 5080
Docs interactivas:  http://localhost:5080/docs
"""
import json
import os
from typing import List, Optional

from fastapi import Depends, FastAPI, Header, HTTPException, Query, status
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session

import models
import schemas
import sync as sync_module
from auth import get_current_user
from database import Base, SessionLocal, engine

# Configuracion de sincronizacion (via variables de entorno)
SYNC_TOKEN = os.getenv("SYNC_TOKEN", "")               # si se define, protege POST /v1/sync
SYNC_INTERVAL_HOURS = int(os.getenv("SYNC_INTERVAL_HOURS", "12"))  # 0 = desactivado

Base.metadata.create_all(bind=engine)

app = FastAPI(title="FercoMotors API", version="1.0")

# CORS abierto para desarrollo (restringe en produccion)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

CAR_FIELDS = [
    "vin", "make", "model", "version", "year", "price", "mileage", "fuel",
    "transmission", "power", "doors", "color", "body", "location",
    "description", "images",
]


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@app.on_event("startup")
def seed_inventory():
    """Si la tabla esta vacia, carga inventory.json (inventario real)."""
    db = SessionLocal()
    try:
        if db.query(models.Car).count() > 0:
            return
        path = os.path.join(os.path.dirname(__file__), "inventory.json")
        if not os.path.exists(path):
            return
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        for raw in data:
            low = {k.lower(): v for k, v in raw.items()}
            car = models.Car(**{f: low.get(f) for f in CAR_FIELDS if low.get(f) is not None})
            db.add(car)
        db.commit()
        print(f"Sembrados {len(data)} coches desde inventory.json")
    finally:
        db.close()


@app.get("/")
def root():
    """Raiz: util como comprobacion rapida y para keep-alive."""
    return {"service": "FercoMotors API", "status": "ok", "docs": "/docs"}


@app.get("/health")
def health():
    """Endpoint ligero para pings de keep-alive / monitorizacion."""
    return {"status": "ok"}


@app.get("/v1/cars", response_model=List[schemas.CarOut])
def list_cars(
    q: Optional[str] = None,
    fuel: Optional[str] = None,
    maxPrice: Optional[float] = None,
    minYear: Optional[int] = None,
    maxMileage: Optional[int] = None,
    body: Optional[str] = None,
    sort: Optional[str] = Query(None, description="priceAsc | priceDesc | make"),
    db: Session = Depends(get_db),
):
    query = db.query(models.Car)

    if q:
        like = f"%{q}%"
        query = query.filter(
            models.Car.make.ilike(like)
            | models.Car.model.ilike(like)
            | models.Car.version.ilike(like)
        )
    if fuel:
        query = query.filter(models.Car.fuel == fuel)
    if body:
        query = query.filter(models.Car.body == body)
    if maxPrice is not None:
        query = query.filter(models.Car.price <= maxPrice)
    if minYear is not None:
        query = query.filter(models.Car.year >= minYear)
    if maxMileage is not None:
        query = query.filter(models.Car.mileage <= maxMileage)

    if sort == "priceAsc":
        query = query.order_by(models.Car.price.asc())
    elif sort == "priceDesc":
        query = query.order_by(models.Car.price.desc())
    elif sort == "make":
        query = query.order_by(models.Car.make.asc(), models.Car.model.asc())
    else:
        query = query.order_by(models.Car.created_at.desc())

    return query.all()


@app.get("/v1/cars/{car_id}", response_model=schemas.CarOut)
def get_car(car_id: str, db: Session = Depends(get_db)):
    car = db.get(models.Car, car_id)
    if car is None:
        raise HTTPException(status_code=404, detail="Coche no encontrado")
    return car


@app.post("/v1/cars", response_model=schemas.CarOut, status_code=status.HTTP_201_CREATED)
def create_car(payload: schemas.CarIn, db: Session = Depends(get_db)):
    car = models.Car(**payload.model_dump())
    db.add(car)
    db.commit()
    db.refresh(car)
    return car


@app.put("/v1/cars/{car_id}", response_model=schemas.CarOut)
def update_car(car_id: str, payload: schemas.CarIn, db: Session = Depends(get_db)):
    car = db.get(models.Car, car_id)
    if car is None:
        raise HTTPException(status_code=404, detail="Coche no encontrado")
    for field, value in payload.model_dump().items():
        setattr(car, field, value)
    db.commit()
    db.refresh(car)
    return car


@app.delete("/v1/cars/{car_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_car(car_id: str, db: Session = Depends(get_db)):
    car = db.get(models.Car, car_id)
    if car is None:
        raise HTTPException(status_code=404, detail="Coche no encontrado")
    db.delete(car)
    db.commit()


@app.get("/v1/me")
def me(user=Depends(get_current_user)):
    """Devuelve el usuario autenticado (a partir del token de Firebase)."""
    return {"uid": user["uid"], "email": user["email"], "name": user.get("name"), "picture": user.get("picture")}


@app.get("/v1/favorites", response_model=List[schemas.CarOut])
def list_favorites(user=Depends(get_current_user), db: Session = Depends(get_db)):
    """Coches marcados como favoritos por el usuario autenticado."""
    ids = [f.car_id for f in db.query(models.Favorite).filter(models.Favorite.user_uid == user["uid"]).all()]
    if not ids:
        return []
    return db.query(models.Car).filter(models.Car.id.in_(ids)).all()


@app.post("/v1/favorites/{car_id}", status_code=status.HTTP_201_CREATED)
def add_favorite(car_id: str, user=Depends(get_current_user), db: Session = Depends(get_db)):
    """Marca un coche como favorito para el usuario."""
    if db.get(models.Car, car_id) is None:
        raise HTTPException(status_code=404, detail="Coche no encontrado")
    exists = db.query(models.Favorite).filter_by(user_uid=user["uid"], car_id=car_id).first()
    if exists is None:
        db.add(models.Favorite(user_uid=user["uid"], car_id=car_id))
        db.commit()
    return {"status": "ok", "carId": car_id}


@app.delete("/v1/favorites/{car_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_favorite(car_id: str, user=Depends(get_current_user), db: Session = Depends(get_db)):
    """Quita un coche de favoritos del usuario."""
    fav = db.query(models.Favorite).filter_by(user_uid=user["uid"], car_id=car_id).first()
    if fav is not None:
        db.delete(fav)
        db.commit()


@app.post("/v1/contact", status_code=status.HTTP_202_ACCEPTED)
def send_contact(payload: schemas.ContactIn, db: Session = Depends(get_db)):
    msg = models.ContactMessage(
        car_id=payload.carId,
        car_title=payload.carTitle,
        name=payload.name,
        email=payload.email,
        phone=payload.phone,
        message=payload.message,
    )
    db.add(msg)
    db.commit()
    return {"id": msg.id}


@app.post("/v1/sync")
def trigger_sync(
    maxPages: Optional[int] = Query(None, description="Limitar nº de páginas (para probar; p.ej. 1)"),
    maxCars: Optional[int] = Query(None, description="Limitar nº de coches (para probar)"),
    x_sync_token: Optional[str] = Header(None),
):
    """
    Lanza la sincronizacion con la web (upsert por VIN, marca vendidos).
    Es sincrono: con el inventario completo puede tardar 1-2 minutos.
    Para probar rapido usa ?maxPages=1 o ?maxCars=5.
    """
    if SYNC_TOKEN and x_sync_token != SYNC_TOKEN:
        raise HTTPException(status_code=401, detail="Token de sincronizacion invalido")
    stats = sync_module.run(max_pages=maxPages, max_cars=maxCars)
    return stats


# ---- Programador: sincroniza cada SYNC_INTERVAL_HOURS horas ----
_scheduler = None


@app.on_event("startup")
def start_scheduler():
    global _scheduler
    if SYNC_INTERVAL_HOURS <= 0:
        print("Sincronizacion automatica desactivada (SYNC_INTERVAL_HOURS=0).")
        return
    try:
        from apscheduler.schedulers.background import BackgroundScheduler
    except ImportError:
        print("apscheduler no instalado; sincronizacion automatica desactivada.")
        return

    def job():
        try:
            print("Sync automatica:", sync_module.run())
        except Exception as e:  # noqa: BLE001
            print("Error en sync automatica:", e)

    _scheduler = BackgroundScheduler(daemon=True)
    _scheduler.add_job(job, "interval", hours=SYNC_INTERVAL_HOURS, id="ferco_sync")
    _scheduler.start()
    print(f"Sincronizacion automatica cada {SYNC_INTERVAL_HOURS} h activada.")


@app.on_event("shutdown")
def stop_scheduler():
    if _scheduler:
        _scheduler.shutdown(wait=False)


@app.get("/")
def root():
    return {
        "ok": True,
        "service": "FercoMotors API",
        "docs": "/docs",
    }


@app.get("/health")
def health():
    return {"status": "healthy"}