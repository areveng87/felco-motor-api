"""
Sincronizacion del inventario con fercomotors.com.

- Coches nuevos (VIN que no existe) -> se crean.
- Coches existentes (mismo VIN)      -> se actualizan (precio, km, etc.).
- Coches que ya no aparecen en la web -> se marcan como "sold".

Uso por linea de comandos (one-off / cron):
    python sync.py            # sincroniza todo el inventario
    python sync.py 1          # solo la primera pagina (para probar rapido)
"""
from typing import List, Optional

from sqlalchemy.orm import Session

import models
import scraper
from database import Base, SessionLocal, engine

# Campos que se actualizan de un coche existente (no tocamos id/created_at)
UPDATABLE = [
    "make", "model", "version", "year", "price", "mileage", "fuel",
    "transmission", "power", "doors", "color", "body", "location",
    "description", "images",
]


def sync_inventory(db: Session, cars: List[dict]) -> dict:
    """Aplica el upsert por VIN sobre una lista de coches ya scrapeados."""
    seen = set()
    created = updated = 0

    for c in cars:
        vin = (c.get("vin") or "").strip().upper()
        if not vin:
            continue
        seen.add(vin)

        existing = db.query(models.Car).filter(models.Car.vin == vin).first()
        if existing:
            for k in UPDATABLE:
                if k in c:
                    setattr(existing, k, c[k])
            existing.status = "available"
            updated += 1
        else:
            db.add(models.Car(vin=vin, status="available",
                              **{k: c.get(k) for k in UPDATABLE if c.get(k) is not None}))
            created += 1

    # Marcar como vendidos los que estaban disponibles y ya no aparecen
    sold = 0
    for car in db.query(models.Car).filter(models.Car.status == "available").all():
        if (car.vin or "").upper() not in seen:
            car.status = "sold"
            sold += 1

    db.commit()
    return {"created": created, "updated": updated, "sold": sold, "seen": len(seen)}


def run(max_pages: Optional[int] = None, max_cars: Optional[int] = None) -> dict:
    """Scrapea la web y sincroniza la BD. Devuelve estadisticas."""
    Base.metadata.create_all(bind=engine)
    cars = scraper.fetch_inventory(max_pages=max_pages, max_cars=max_cars)
    db = SessionLocal()
    try:
        stats = sync_inventory(db, cars)
    finally:
        db.close()
    stats["scraped"] = len(cars)
    return stats


if __name__ == "__main__":
    import sys
    mp = int(sys.argv[1]) if len(sys.argv) > 1 else None
    print("Sincronizando...", "(pagina 1)" if mp == 1 else "(inventario completo)")
    result = run(max_pages=mp)
    print("Resultado:", result)
